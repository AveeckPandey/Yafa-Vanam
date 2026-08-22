package commerce

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresStore is the durable CommerceStore backend. Carts and paid orders
// survive restarts and deploys; the catalogue still comes from Product.json,
// so item lines snapshot catalogue identifiers rather than database foreign
// keys. Behaviour mirrors Store exactly — handlers cannot tell them apart.
type PostgresStore struct {
	db      *pgxpool.Pool
	catalog *Catalog
	now     func() time.Time
}

// dbQuerier is satisfied by both *pgxpool.Pool and pgx.Tx, letting helpers
// run inside or outside a transaction.
type dbQuerier interface {
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

func NewPostgresStore(db *pgxpool.Pool, catalog *Catalog) *PostgresStore {
	return &PostgresStore{db: db, catalog: catalog, now: time.Now}
}

// postgresTimeout bounds every store operation. The CommerceStore interface
// carries no context, so each method derives its own bounded one; a slow or
// wedged database degrades to an error response instead of pinning handlers.
const postgresTimeout = 10 * time.Second

const orderSelectColumns = `o.id::text, o.order_number, COALESCE(o.user_id::text,''), o.customer_email, ` +
	`o.currency, o.subtotal::float8, o.discount_amount::float8, o.shipping_amount::float8, o.total_amount::float8, ` +
	`o.order_status, o.payment_status, o.fulfillment_status, o.shipping_address, ` +
	`COALESCE(o.razorpay_order_id,''), COALESCE(o.razorpay_payment_id,''), COALESCE(o.access_token,''), o.created_at`

// orderReturningColumns mirrors orderSelectColumns for UPDATE ... RETURNING,
// where the "orders o" alias does not exist.
const orderReturningColumns = `id::text, order_number, COALESCE(user_id::text,''), customer_email, ` +
	`currency, subtotal::float8, discount_amount::float8, shipping_amount::float8, total_amount::float8, ` +
	`order_status, payment_status, fulfillment_status, shipping_address, ` +
	`COALESCE(razorpay_order_id,''), COALESCE(razorpay_payment_id,''), COALESCE(access_token,''), created_at`

type orderRecord struct {
	order        Order
	accessToken  string
	addressBytes []byte
}

func (store *PostgresStore) ctx() (context.Context, context.CancelFunc) {
	return context.WithTimeout(context.Background(), postgresTimeout)
}

func scanOrderRecord(row pgx.Row) (orderRecord, error) {
	var record orderRecord
	err := row.Scan(&record.order.ID, &record.order.OrderNumber, &record.order.UserID, &record.order.CustomerEmail,
		&record.order.Currency, &record.order.Subtotal, &record.order.DiscountAmount, &record.order.ShippingAmount,
		&record.order.TotalAmount, &record.order.OrderStatus, &record.order.PaymentStatus, &record.order.FulfillmentStatus,
		&record.addressBytes, &record.order.RazorpayOrderID, &record.order.RazorpayPaymentID,
		&record.accessToken, &record.order.CreatedAt)
	return record, err
}

func (record *orderRecord) assemble() (Order, error) {
	order := record.order
	if len(record.addressBytes) > 0 {
		if err := json.Unmarshal(record.addressBytes, &order.ShippingAddress); err != nil {
			return Order{}, err
		}
	}
	order.AccessToken = record.accessToken
	return order, nil
}

func (store *PostgresStore) loadOrderItems(ctx context.Context, querier dbQuerier, orderID string) ([]CartLine, error) {
	rows, err := querier.Query(ctx,
		`SELECT line_key, product_id, variant_id, slug, product_type, currency, product_name, unit_price::float8,
		        quantity, size, shade_name, image
		 FROM order_items WHERE order_id=$1 ORDER BY line_key`, orderID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []CartLine{}
	for rows.Next() {
		var line CartLine
		var shade, size, image *string
		if err := rows.Scan(&line.Key, &line.ProductID, &line.VariantID, &line.Slug, &line.ProductType,
			&line.Currency, &line.Name, &line.UnitPrice, &line.Quantity, &size, &shade, &image); err != nil {
			return nil, err
		}
		line.Size, line.Shade, line.Image = size, shade, image
		items = append(items, line)
	}
	return items, rows.Err()
}

func (store *PostgresStore) loadOrderBy(ctx context.Context, querier dbQuerier, column, value string) (Order, error) {
	record, err := scanOrderRecord(querier.QueryRow(ctx,
		`SELECT `+orderSelectColumns+` FROM orders o WHERE o.`+column+`=$1`, value))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return Order{}, ErrOrderNotFound
		}
		return Order{}, err
	}
	order, err := record.assemble()
	if err != nil {
		return Order{}, err
	}
	items, err := store.loadOrderItems(ctx, querier, order.ID)
	if err != nil {
		return Order{}, err
	}
	order.Items = items
	return order, nil
}

// --- carts -----------------------------------------------------------------

func (store *PostgresStore) CreateCart() (CartView, error) {
	return store.CreateCartForUser("")
}

func (store *PostgresStore) CreateCartForUser(ownerID string) (CartView, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	var id string
	var updatedAt time.Time
	err := store.db.QueryRow(ctx,
		`INSERT INTO carts (user_id) VALUES (NULLIF($1,'')::uuid) RETURNING id::text, updated_at`,
		ownerID).Scan(&id, &updatedAt)
	if err != nil {
		return CartView{}, err
	}
	return buildCartView(store.catalog, id, map[string]int{}, updatedAt), nil
}

// cartLookupErr maps query failures on the user-controlled cart id: unknown
// carts and malformed (non-UUID) ids both report ErrCartNotFound so handlers
// answer 404 instead of leaking SQL errors as 500s.
func cartLookupErr(err error) error {
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrCartNotFound
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "22P02" {
		return ErrCartNotFound
	}
	return err
}

// ownedCart loads a cart row and applies the shared ownership rules: missing
// carts report ErrCartNotFound, and any caller other than the owning user is
// denied. Empty owner ids are always denied because user-scoped operations
// require an authenticated owner.
func (store *PostgresStore) ownedCart(ctx context.Context, querier dbQuerier, cartID, ownerID string) (string, time.Time, error) {
	var cartOwner string
	var updatedAt time.Time
	err := querier.QueryRow(ctx,
		`SELECT COALESCE(user_id::text,''), updated_at FROM carts WHERE id=$1`, cartID).
		Scan(&cartOwner, &updatedAt)
	if err != nil {
		return "", time.Time{}, cartLookupErr(err)
	}
	if ownerID == "" || cartOwner != ownerID {
		return "", time.Time{}, ErrCartAccessDenied
	}
	return cartOwner, updatedAt, nil
}

// guestCart enforces the guest-only rule: the cart must exist and be unclaimed.
func (store *PostgresStore) guestCart(ctx context.Context, querier dbQuerier, cartID string) (time.Time, error) {
	var cartOwner string
	var updatedAt time.Time
	err := querier.QueryRow(ctx,
		`SELECT COALESCE(user_id::text,''), updated_at FROM carts WHERE id=$1`, cartID).
		Scan(&cartOwner, &updatedAt)
	if err != nil {
		return time.Time{}, cartLookupErr(err)
	}
	if cartOwner != "" {
		return time.Time{}, ErrCartAccessDenied
	}
	return updatedAt, nil
}

func (store *PostgresStore) cartItems(ctx context.Context, querier dbQuerier, cartID string) (map[string]int, error) {
	rows, err := querier.Query(ctx, `SELECT variant_id, quantity FROM cart_items WHERE cart_id=$1`, cartID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := map[string]int{}
	for rows.Next() {
		var variantID string
		var quantity int
		if err := rows.Scan(&variantID, &quantity); err != nil {
			return nil, err
		}
		items[variantID] = quantity
	}
	return items, rows.Err()
}

func (store *PostgresStore) GetCartForUser(id, ownerID string) (CartView, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	if _, _, err := store.ownedCart(ctx, store.db, id, ownerID); err != nil {
		return CartView{}, err
	}
	items, err := store.cartItems(ctx, store.db, id)
	if err != nil {
		return CartView{}, err
	}
	view, err := store.viewFor(ctx, id, items)
	return view, err
}

// viewFor rebuilds a CartView and refreshes its timestamp from the cart row so
// responses match what is persisted.
func (store *PostgresStore) viewFor(ctx context.Context, cartID string, items map[string]int) (CartView, error) {
	var updatedAt time.Time
	err := store.db.QueryRow(ctx, `SELECT updated_at FROM carts WHERE id=$1`, cartID).Scan(&updatedAt)
	if err != nil {
		return CartView{}, err
	}
	return buildCartView(store.catalog, cartID, items, updatedAt), nil
}

func (store *PostgresStore) ClaimCartForUser(id, ownerID string) error {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	var cartOwner string
	err = tx.QueryRow(ctx,
		`SELECT COALESCE(user_id::text,'') FROM carts WHERE id=$1 FOR UPDATE`, id).Scan(&cartOwner)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrCartNotFound
		}
		return err
	}
	if ownerID == "" || (cartOwner != "" && cartOwner != ownerID) {
		return ErrCartAccessDenied
	}
	if _, err := tx.Exec(ctx,
		`UPDATE carts SET user_id=$2::uuid, updated_at=NOW() WHERE id=$1`, id, ownerID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (store *PostgresStore) AddCartItemForUser(ownerID, cartID, productID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	_, variant, err := store.catalog.SellableVariant(productID, variantID)
	if err != nil {
		return CartView{}, err
	}
	return store.mutateUserCart(cartID, ownerID, func(items map[string]int) error {
		updated := min(items[variantID]+quantity, maxLineQuantity)
		if variant.Stock != nil && updated > *variant.Stock {
			return ErrInsufficientStock
		}
		items[variantID] = updated
		return nil
	})
}

func (store *PostgresStore) SetCartItemForUser(ownerID, cartID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	return store.mutateUserCart(cartID, ownerID, func(items map[string]int) error {
		if _, ok := items[variantID]; !ok {
			return ErrVariantNotFound
		}
		ref, ok := store.catalog.variants[variantID]
		if !ok || !ref.variant.IsActive {
			return ErrVariantUnavailable
		}
		if ref.variant.Stock != nil && quantity > *ref.variant.Stock {
			return ErrInsufficientStock
		}
		items[variantID] = quantity
		return nil
	})
}

func (store *PostgresStore) RemoveCartItemForUser(ownerID, cartID, variantID string) (CartView, error) {
	return store.mutateUserCart(cartID, ownerID, func(items map[string]int) error {
		delete(items, variantID)
		return nil
	})
}

// mutateUserCart locks the cart row, verifies ownership, applies the mutation
// to the loaded item map, persists the diff, and returns the refreshed view.
// One transaction per mutation keeps concurrent browsers from losing updates.
func (store *PostgresStore) mutateUserCart(cartID, ownerID string, mutate func(map[string]int) error) (CartView, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return CartView{}, err
	}
	defer tx.Rollback(ctx)
	if _, _, err := store.ownedCart(ctx, tx, cartID, ownerID); err != nil {
		return CartView{}, err
	}
	items, err := store.cartItems(ctx, tx, cartID)
	if err != nil {
		return CartView{}, err
	}
	if err := mutate(items); err != nil {
		return CartView{}, err
	}
	if _, err := tx.Exec(ctx, `DELETE FROM cart_items WHERE cart_id=$1`, cartID); err != nil {
		return CartView{}, err
	}
	for variantID, quantity := range items {
		if _, err := tx.Exec(ctx,
			`INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES ($1, $2, $3)
			 ON CONFLICT (cart_id, variant_id) DO NOTHING`, cartID, variantID, quantity); err != nil {
			return CartView{}, err
		}
	}
	if _, err := tx.Exec(ctx, `UPDATE carts SET updated_at=NOW() WHERE id=$1`, cartID); err != nil {
		return CartView{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return CartView{}, err
	}
	view, err := store.viewFor(ctx, cartID, items)
	return view, err
}

func (store *PostgresStore) GetCart(id string) (CartView, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	if _, err := store.guestCart(ctx, store.db, id); err != nil {
		return CartView{}, err
	}
	items, err := store.cartItems(ctx, store.db, id)
	if err != nil {
		return CartView{}, err
	}
	view, err := store.viewFor(ctx, id, items)
	return view, err
}

func (store *PostgresStore) AddCartItem(cartID, productID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	_, variant, err := store.catalog.SellableVariant(productID, variantID)
	if err != nil {
		return CartView{}, err
	}
	return store.mutateGuestCart(cartID, func(items map[string]int) error {
		updated := min(items[variantID]+quantity, maxLineQuantity)
		if variant.Stock != nil && updated > *variant.Stock {
			return ErrInsufficientStock
		}
		items[variantID] = updated
		return nil
	})
}

func (store *PostgresStore) SetCartItem(cartID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	return store.mutateGuestCart(cartID, func(items map[string]int) error {
		if _, ok := items[variantID]; !ok {
			return ErrVariantNotFound
		}
		ref, ok := store.catalog.variants[variantID]
		if !ok || !ref.variant.IsActive {
			return ErrVariantUnavailable
		}
		if ref.variant.Stock != nil && quantity > *ref.variant.Stock {
			return ErrInsufficientStock
		}
		items[variantID] = quantity
		return nil
	})
}

func (store *PostgresStore) RemoveCartItem(cartID, variantID string) (CartView, error) {
	return store.mutateGuestCart(cartID, func(items map[string]int) error {
		delete(items, variantID)
		return nil
	})
}

// mutateGuestCart mirrors mutateUserCart but requires the cart to be unclaimed.
func (store *PostgresStore) mutateGuestCart(cartID string, mutate func(map[string]int) error) (CartView, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return CartView{}, err
	}
	defer tx.Rollback(ctx)
	if _, err := store.guestCart(ctx, tx, cartID); err != nil {
		return CartView{}, err
	}
	items, err := store.cartItems(ctx, tx, cartID)
	if err != nil {
		return CartView{}, err
	}
	if err := mutate(items); err != nil {
		return CartView{}, err
	}
	if _, err := tx.Exec(ctx, `DELETE FROM cart_items WHERE cart_id=$1`, cartID); err != nil {
		return CartView{}, err
	}
	for variantID, quantity := range items {
		if _, err := tx.Exec(ctx,
			`INSERT INTO cart_items (cart_id, variant_id, quantity) VALUES ($1, $2, $3)
			 ON CONFLICT (cart_id, variant_id) DO NOTHING`, cartID, variantID, quantity); err != nil {
			return CartView{}, err
		}
	}
	if _, err := tx.Exec(ctx, `UPDATE carts SET updated_at=NOW() WHERE id=$1`, cartID); err != nil {
		return CartView{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return CartView{}, err
	}
	view, err := store.viewFor(ctx, cartID, items)
	return view, err
}

// --- orders ------------------------------------------------------------------

func (store *PostgresStore) CreateOrder(input CreateOrderInput, idempotencyKey string) (Order, bool, error) {
	return store.createOrder("", input, idempotencyKey)
}

func (store *PostgresStore) CreateOrderForUser(ownerID string, input CreateOrderInput, idempotencyKey string) (Order, bool, error) {
	return store.createOrder(ownerID, input, idempotencyKey)
}

func validCreateOrderInput(input *CreateOrderInput) error {
	if !validEmail(input.CustomerEmail) {
		return ErrInvalidEmail
	}
	if input.ShippingAddress.CountryCode == "" {
		input.ShippingAddress.CountryCode = "IN"
	}
	input.ShippingAddress.CountryCode = strings.ToUpper(strings.TrimSpace(input.ShippingAddress.CountryCode))
	return validateAddress(input.ShippingAddress)
}

func (store *PostgresStore) findOrderIdempotent(ctx context.Context, idempotencyKey string) (Order, bool, error) {
	if idempotencyKey == "" {
		return Order{}, false, nil
	}
	order, err := store.loadOrderBy(ctx, store.db, "idempotency_key", idempotencyKey)
	if errors.Is(err, ErrOrderNotFound) {
		return Order{}, false, nil
	}
	if err != nil {
		return Order{}, false, err
	}
	return order, true, nil
}

// createOrder converts a cart into an order atomically: it locks the cart row,
// prices the basket through the live catalogue, snapshots every line, and
// records the idempotency key. A duplicate key arriving mid-flight loses the
// insert race, rolls back, and replays the winning order.
func (store *PostgresStore) createOrder(ownerID string, input CreateOrderInput, idempotencyKey string) (Order, bool, error) {
	// The memory store validated ownership first (GetCartForUser) and only
	// then email/address; keep that precedence so handlers see identical errors.
	if ownerID != "" {
		if _, err := store.GetCartForUser(input.CartID, ownerID); err != nil {
			return Order{}, false, err
		}
	}
	if err := validCreateOrderInput(&input); err != nil {
		return Order{}, false, err
	}
	ctx, cancel := store.ctx()
	defer cancel()

	if order, replayed, err := store.findOrderIdempotent(ctx, idempotencyKey); err != nil || replayed {
		return order, replayed, err
	}

	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Order{}, false, err
	}
	defer tx.Rollback(ctx)

	var cartOwner string
	err = tx.QueryRow(ctx,
		`SELECT COALESCE(user_id::text,'') FROM carts WHERE id=$1 FOR UPDATE`, input.CartID).Scan(&cartOwner)
	if err != nil {
		return Order{}, false, cartLookupErr(err)
	}
	if ownerID != "" && cartOwner != ownerID {
		return Order{}, false, ErrCartAccessDenied
	}

	items, err := store.cartItems(ctx, tx, input.CartID)
	if err != nil {
		return Order{}, false, err
	}
	view := buildCartView(store.catalog, input.CartID, items, store.now().UTC())
	if len(view.Items) == 0 {
		return Order{}, false, ErrEmptyCart
	}

	discount := checkoutDiscount(view.Subtotal, input.DiscountCode)
	discountedSubtotal := max(0.0, view.Subtotal-discount)
	shipping := 199.0
	if strings.EqualFold(strings.TrimSpace(input.ShippingMethod), "express") {
		shipping = 299
	} else if discountedSubtotal >= 1999 {
		shipping = 0
	}

	now := store.now().UTC()
	accessToken := ""
	if ownerID == "" {
		accessToken = randomID("ot_", 24)
	}
	addressJSON, err := json.Marshal(input.ShippingAddress)
	if err != nil {
		return Order{}, false, err
	}

	order := Order{
		OrderNumber: "YV-" + now.Format("20060102") + "-" + strings.ToUpper(randomID("", 4)),
		CustomerEmail: strings.ToLower(strings.TrimSpace(input.CustomerEmail)), UserID: ownerID,
		AccessToken: accessToken, Items: append([]CartLine(nil), view.Items...), Currency: view.Currency,
		Subtotal: view.Subtotal, ShippingAmount: shipping, DiscountAmount: discount,
		TotalAmount: discountedSubtotal + shipping, OrderStatus: "PENDING_PAYMENT",
		PaymentStatus: "PENDING", FulfillmentStatus: "UNFULFILLED",
		ShippingAddress: input.ShippingAddress, CreatedAt: now,
	}

	err = tx.QueryRow(ctx,
		`INSERT INTO orders (order_number, user_id, customer_email, currency, subtotal, discount_amount,
		    shipping_amount, tax_amount, total_amount, order_status, payment_status, fulfillment_status,
		    shipping_address, access_token, idempotency_key)
		 VALUES ($1, NULLIF($2,'')::uuid, $3, $4, $5, $6, $7, 0, $8, 'PENDING_PAYMENT', 'PENDING', 'UNFULFILLED', $9, NULLIF($10,''), NULLIF($11,''))
		 RETURNING id::text, created_at`,
		order.OrderNumber, ownerID, order.CustomerEmail, order.Currency, order.Subtotal, order.DiscountAmount,
		order.ShippingAmount, order.TotalAmount, addressJSON, accessToken, idempotencyKey).
		Scan(&order.ID, &order.CreatedAt)
	if isUniqueViolation(err) && idempotencyKey != "" {
		// A concurrent request with the same key committed first; replay it.
		replay, replayed, replayErr := store.findOrderIdempotent(ctx, idempotencyKey)
		if replayErr != nil {
			return Order{}, false, replayErr
		}
		if replayed {
			return store.replayedOrder(replay, ownerID)
		}
		return Order{}, false, err
	}
	if err != nil {
		return Order{}, false, err
	}

	for _, line := range order.Items {
		subtotal := line.UnitPrice * float64(line.Quantity)
		if _, err := tx.Exec(ctx,
			`INSERT INTO order_items (order_id, product_id, variant_id, product_name, variant_name, shade_name,
			    sku, unit_price, quantity, subtotal, line_key, slug, product_type, size, image)
			 VALUES ($1, $2, $3, $4, $4, $5, $3, $6, $7, $8, $9, $10, $11, $12, $13)`,
			order.ID, line.ProductID, line.VariantID, line.Name, line.Shade, line.UnitPrice,
			line.Quantity, subtotal, line.Key, line.Slug, line.ProductType, line.Size, line.Image); err != nil {
			return Order{}, false, err
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return Order{}, false, err
	}
	return order, false, nil
}

// replayedOrder applies the user binding the memory store performed after a
// replay: the winning order is re-bound to whoever presented the key and its
// guest access token is retired.
func (store *PostgresStore) replayedOrder(order Order, ownerID string) (Order, bool, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	if ownerID != "" {
		record, err := scanOrderRecord(store.db.QueryRow(ctx,
			`UPDATE orders SET user_id=$2::uuid, access_token=NULL, updated_at=NOW()
			 WHERE order_number=$1 RETURNING `+orderReturningColumns, order.OrderNumber, ownerID))
		if err != nil {
			return Order{}, false, err
		}
		rebound, err := record.assemble()
		if err != nil {
			return Order{}, false, err
		}
		items, err := store.loadOrderItems(ctx, store.db, rebound.ID)
		if err != nil {
			return Order{}, false, err
		}
		rebound.Items = items
		order = rebound
	}
	order.AccessToken = ""
	return order, true, nil
}

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

func (store *PostgresStore) GetOrderForUser(orderNumber, ownerID string) (Order, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	order, err := store.loadOrderBy(ctx, store.db, "order_number", orderNumber)
	if err != nil {
		return Order{}, err
	}
	if ownerID == "" || order.UserID != ownerID {
		return Order{}, ErrOrderAccessDenied
	}
	order.AccessToken = ""
	return order, nil
}

// ListOrdersForUser returns only orders owned by the authenticated user. It
// deliberately never accepts an owner id supplied by the browser.
func (store *PostgresStore) ListOrdersForUser(ownerID string) []Order {
	if ownerID == "" {
		return []Order{}
	}
	ctx, cancel := store.ctx()
	defer cancel()
	rows, err := store.db.Query(ctx,
		`SELECT `+orderSelectColumns+` FROM orders o WHERE o.user_id::text=$1 ORDER BY o.created_at DESC, o.id DESC`,
		ownerID)
	if err != nil {
		return []Order{}
	}
	defer rows.Close()
	orders := make([]Order, 0)
	var records []orderRecord
	for rows.Next() {
		record, err := scanOrderRecord(rows)
		if err != nil {
			return []Order{}
		}
		records = append(records, record)
	}
	if err := rows.Err(); err != nil {
		return []Order{}
	}
	for _, record := range records {
		order, err := record.assemble()
		if err != nil {
			continue
		}
		items, err := store.loadOrderItems(ctx, store.db, order.ID)
		if err != nil {
			continue
		}
		order.Items = items
		order.AccessToken = ""
		orders = append(orders, order)
	}
	return orders
}

func (store *PostgresStore) GetOrder(orderNumber, accessToken string) (Order, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	order, err := store.loadOrderBy(ctx, store.db, "order_number", orderNumber)
	if err != nil {
		return Order{}, err
	}
	if accessToken == "" || accessToken != order.AccessToken {
		return Order{}, ErrOrderAccessDenied
	}
	order.AccessToken = ""
	return order, nil
}

// --- razorpay -----------------------------------------------------------------

func (store *PostgresStore) AttachRazorpayOrder(orderNumber, razorpayOrderID string) (Order, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Order{}, err
	}
	defer tx.Rollback(ctx)
	record, err := scanOrderRecord(tx.QueryRow(ctx,
		`UPDATE orders SET razorpay_order_id=$2, updated_at=NOW() WHERE order_number=$1 RETURNING `+orderReturningColumns,
		orderNumber, razorpayOrderID))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return Order{}, ErrOrderNotFound
		}
		return Order{}, err
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO payments (order_id, provider, provider_order_id, amount, currency, status)
		 SELECT id, 'RAZORPAY', $2, total_amount, currency, 'PENDING' FROM orders WHERE order_number=$1
		 ON CONFLICT (order_id, provider) DO UPDATE SET provider_order_id=EXCLUDED.provider_order_id, updated_at=NOW()`,
		orderNumber, razorpayOrderID); err != nil {
		return Order{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Order{}, err
	}
	order, err := record.assemble()
	return order, err
}

func (store *PostgresStore) VerifyRazorpayPayment(razorpayOrderID, paymentID string) (Order, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	record, err := scanOrderRecord(store.db.QueryRow(ctx,
		`UPDATE orders SET razorpay_payment_id=$2,
		    payment_status=CASE WHEN payment_status IN ('PENDING','FAILED') THEN 'AUTHORIZED' ELSE payment_status END,
		    updated_at=NOW()
		 WHERE razorpay_order_id=$1 RETURNING `+orderReturningColumns, razorpayOrderID, paymentID))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return Order{}, ErrPaymentOrderNotFound
		}
		return Order{}, err
	}
	if _, err := store.db.Exec(ctx,
		`UPDATE payments SET provider_payment_id=$2, status='AUTHORIZED', updated_at=NOW()
		 WHERE provider_order_id=$1 AND status IN ('PENDING','FAILED')`, razorpayOrderID, paymentID); err != nil {
		return Order{}, err
	}
	order, err := record.assemble()
	return order, err
}

func (store *PostgresStore) RecordRazorpayPayment(razorpayOrderID, paymentID, status string) (Order, error) {
	capturedOrPaid := status == "captured" || status == "paid"
	paymentStatus := status
	switch {
	case capturedOrPaid:
		paymentStatus = "CAPTURED"
	case status == "failed":
		paymentStatus = "FAILED"
	default:
		paymentStatus = ""
	}
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Order{}, err
	}
	defer tx.Rollback(ctx)
	record, err := scanOrderRecord(tx.QueryRow(ctx,
		`UPDATE orders SET
		    razorpay_payment_id=CASE WHEN $2<>'' THEN $2 ELSE razorpay_payment_id END,
		    payment_status=CASE WHEN $3<>'' THEN $3 ELSE payment_status END,
		    order_status=CASE WHEN $4 THEN 'PAID' ELSE order_status END,
		    updated_at=NOW()
		 WHERE razorpay_order_id=$1 RETURNING `+orderReturningColumns,
		razorpayOrderID, paymentID, paymentStatus, capturedOrPaid))
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return Order{}, ErrPaymentOrderNotFound
		}
		return Order{}, err
	}
	if _, err := tx.Exec(ctx,
		`UPDATE payments SET
		    provider_payment_id=CASE WHEN $2<>'' THEN $2 ELSE provider_payment_id END,
		    status=CASE WHEN $3<>'' THEN $3 ELSE status END,
		    paid_at=CASE WHEN $4 THEN NOW() ELSE paid_at END,
		    updated_at=NOW()
		 WHERE provider_order_id=$1`,
		razorpayOrderID, paymentID, paymentStatus, capturedOrPaid); err != nil {
		return Order{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Order{}, err
	}
	order, err := record.assemble()
	return order, err
}
