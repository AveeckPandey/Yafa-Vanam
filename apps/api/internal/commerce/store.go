package commerce

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"net/mail"
	"sort"
	"strings"
	"sync"
	"time"
)

const maxLineQuantity = 20

var ErrCartNotFound = errors.New("cart not found")
var ErrCartAccessDenied = errors.New("cart access denied")
var ErrOrderNotFound = errors.New("order not found")
var ErrOrderAccessDenied = errors.New("order access denied")
var ErrEmptyCart = errors.New("cart is empty")
var ErrInvalidQuantity = errors.New("quantity must be between 1 and 20")
var ErrInvalidEmail = errors.New("a valid customer email is required")
var ErrInvalidAddress = errors.New("a complete shipping address is required")
var ErrPaymentOrderNotFound = errors.New("payment order not found")

type Cart struct {
	ID        string         `json:"id"`
	OwnerID   string         `json:"-"`
	Items     map[string]int `json:"-"`
	CreatedAt time.Time      `json:"created_at"`
	UpdatedAt time.Time      `json:"updated_at"`
}

type CartLine struct {
	Key         string  `json:"key"`
	ProductID   string  `json:"product_id"`
	VariantID   string  `json:"variant_id"`
	Name        string  `json:"name"`
	Slug        string  `json:"slug"`
	ProductType string  `json:"product_type"`
	Currency    string  `json:"currency"`
	UnitPrice   float64 `json:"unit_price"`
	Quantity    int     `json:"quantity"`
	Size        *string `json:"size"`
	Shade       *string `json:"shade"`
	Image       *string `json:"image"`
}

type CartView struct {
	ID        string     `json:"id"`
	Items     []CartLine `json:"items"`
	ItemCount int        `json:"item_count"`
	Subtotal  float64    `json:"subtotal"`
	Currency  string     `json:"currency"`
	UpdatedAt time.Time  `json:"updated_at"`
}

type Address struct {
	RecipientName string  `json:"recipient_name"`
	Phone         *string `json:"phone"`
	Line1         string  `json:"line1"`
	Line2         *string `json:"line2"`
	City          string  `json:"city"`
	StateRegion   string  `json:"state_region"`
	PostalCode    string  `json:"postal_code"`
	CountryCode   string  `json:"country_code"`
}

type CreateOrderInput struct {
	CartID          string  `json:"cart_id"`
	CustomerEmail   string  `json:"customer_email"`
	ShippingAddress Address `json:"shipping_address"`
	ShippingMethod  string  `json:"shipping_method,omitempty"`
	DiscountCode    string  `json:"discount_code,omitempty"`
}

type Order struct {
	ID                string     `json:"id"`
	OrderNumber       string     `json:"order_number"`
	AccessToken       string     `json:"access_token,omitempty"`
	CustomerEmail     string     `json:"customer_email"`
	UserID            string     `json:"-"`
	Items             []CartLine `json:"items"`
	Currency          string     `json:"currency"`
	Subtotal          float64    `json:"subtotal"`
	ShippingAmount    float64    `json:"shipping_amount"`
	DiscountAmount    float64    `json:"discount_amount"`
	TotalAmount       float64    `json:"total_amount"`
	OrderStatus       string     `json:"order_status"`
	PaymentStatus     string     `json:"payment_status"`
	RazorpayOrderID   string     `json:"razorpay_order_id,omitempty"`
	RazorpayPaymentID string     `json:"razorpay_payment_id,omitempty"`
	FulfillmentStatus string     `json:"fulfillment_status"`
	ShippingAddress   Address    `json:"shipping_address"`
	CreatedAt         time.Time  `json:"created_at"`
}

type Store struct {
	mu          sync.RWMutex
	catalog     *Catalog
	carts       map[string]*Cart
	orders      map[string]*Order
	idempotency map[string]string
	now         func() time.Time
}

func NewStore(catalog *Catalog) *Store {
	return &Store{
		catalog: catalog, carts: make(map[string]*Cart), orders: make(map[string]*Order),
		idempotency: make(map[string]string), now: time.Now,
	}
}

func (store *Store) CreateCart() CartView {
	return store.CreateCartForUser("")
}

func (store *Store) CreateCartForUser(ownerID string) CartView {
	store.mu.Lock()
	defer store.mu.Unlock()
	now := store.now().UTC()
	cart := &Cart{ID: randomID("cart_", 12), OwnerID: ownerID, Items: make(map[string]int), CreatedAt: now, UpdatedAt: now}
	store.carts[cart.ID] = cart
	return store.cartViewLocked(cart)
}

func (store *Store) ownedCart(id, ownerID string) (*Cart, error) {
	cart, ok := store.carts[id]
	if !ok {
		return nil, ErrCartNotFound
	}
	if ownerID == "" || cart.OwnerID != ownerID {
		return nil, ErrCartAccessDenied
	}
	return cart, nil
}

func (store *Store) GetCartForUser(id, ownerID string) (CartView, error) {
	store.mu.RLock()
	defer store.mu.RUnlock()
	cart, err := store.ownedCart(id, ownerID)
	if err != nil {
		return CartView{}, err
	}
	return store.cartViewLocked(cart), nil
}
func (store *Store) ClaimCartForUser(id, ownerID string) error {
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, ok := store.carts[id]
	if !ok {
		return ErrCartNotFound
	}
	if ownerID == "" || (cart.OwnerID != "" && cart.OwnerID != ownerID) {
		return ErrCartAccessDenied
	}
	cart.OwnerID = ownerID
	cart.UpdatedAt = store.now().UTC()
	return nil
}
func (store *Store) AddCartItemForUser(ownerID, cartID, productID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	_, variant, err := store.catalog.SellableVariant(productID, variantID)
	if err != nil {
		return CartView{}, err
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, err := store.ownedCart(cartID, ownerID)
	if err != nil {
		return CartView{}, err
	}
	updatedQuantity := min(cart.Items[variantID]+quantity, maxLineQuantity)
	if variant.Stock != nil && updatedQuantity > *variant.Stock {
		return CartView{}, ErrInsufficientStock
	}
	cart.Items[variantID] = updatedQuantity
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}
func (store *Store) SetCartItemForUser(ownerID, cartID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, err := store.ownedCart(cartID, ownerID)
	if err != nil {
		return CartView{}, err
	}
	if _, ok := cart.Items[variantID]; !ok {
		return CartView{}, ErrVariantNotFound
	}
	ref, ok := store.catalog.variants[variantID]
	if !ok || !ref.variant.IsActive {
		return CartView{}, ErrVariantUnavailable
	}
	if ref.variant.Stock != nil && quantity > *ref.variant.Stock {
		return CartView{}, ErrInsufficientStock
	}
	cart.Items[variantID] = quantity
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}
func (store *Store) RemoveCartItemForUser(ownerID, cartID, variantID string) (CartView, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, err := store.ownedCart(cartID, ownerID)
	if err != nil {
		return CartView{}, err
	}
	delete(cart.Items, variantID)
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}

func (store *Store) GetCart(id string) (CartView, error) {
	store.mu.RLock()
	defer store.mu.RUnlock()
	cart, ok := store.carts[id]
	if !ok {
		return CartView{}, ErrCartNotFound
	}
	if cart.OwnerID != "" {
		return CartView{}, ErrCartAccessDenied
	}
	return store.cartViewLocked(cart), nil
}

func (store *Store) AddCartItem(cartID, productID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	_, variant, err := store.catalog.SellableVariant(productID, variantID)
	if err != nil {
		return CartView{}, err
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, ok := store.carts[cartID]
	if !ok {
		return CartView{}, ErrCartNotFound
	}
	if cart.OwnerID != "" {
		return CartView{}, ErrCartAccessDenied
	}
	updatedQuantity := min(cart.Items[variantID]+quantity, maxLineQuantity)
	if variant.Stock != nil && updatedQuantity > *variant.Stock {
		return CartView{}, ErrInsufficientStock
	}
	cart.Items[variantID] = updatedQuantity
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}

func (store *Store) SetCartItem(cartID, variantID string, quantity int) (CartView, error) {
	if quantity < 1 || quantity > maxLineQuantity {
		return CartView{}, ErrInvalidQuantity
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, ok := store.carts[cartID]
	if !ok {
		return CartView{}, ErrCartNotFound
	}
	if cart.OwnerID != "" {
		return CartView{}, ErrCartAccessDenied
	}
	if _, ok := cart.Items[variantID]; !ok {
		return CartView{}, ErrVariantNotFound
	}
	ref, ok := store.catalog.variants[variantID]
	if !ok || !ref.variant.IsActive {
		return CartView{}, ErrVariantUnavailable
	}
	if ref.variant.Stock != nil && quantity > *ref.variant.Stock {
		return CartView{}, ErrInsufficientStock
	}
	cart.Items[variantID] = quantity
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}

func (store *Store) RemoveCartItem(cartID, variantID string) (CartView, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	cart, ok := store.carts[cartID]
	if !ok {
		return CartView{}, ErrCartNotFound
	}
	if cart.OwnerID != "" {
		return CartView{}, ErrCartAccessDenied
	}
	delete(cart.Items, variantID)
	cart.UpdatedAt = store.now().UTC()
	return store.cartViewLocked(cart), nil
}

func (store *Store) CreateOrder(input CreateOrderInput, idempotencyKey string) (Order, bool, error) {
	if !validEmail(input.CustomerEmail) {
		return Order{}, false, ErrInvalidEmail
	}
	if input.ShippingAddress.CountryCode == "" {
		input.ShippingAddress.CountryCode = "IN"
	}
	input.ShippingAddress.CountryCode = strings.ToUpper(strings.TrimSpace(input.ShippingAddress.CountryCode))
	if err := validateAddress(input.ShippingAddress); err != nil {
		return Order{}, false, err
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	if idempotencyKey != "" {
		if orderNumber, ok := store.idempotency[idempotencyKey]; ok {
			return *store.orders[orderNumber], true, nil
		}
	}
	cart, ok := store.carts[input.CartID]
	if !ok {
		return Order{}, false, ErrCartNotFound
	}
	view := store.cartViewLocked(cart)
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
	order := &Order{
		ID: randomID("ord_", 12), OrderNumber: "YV-" + now.Format("20060102") + "-" + strings.ToUpper(randomID("", 4)),
		AccessToken: randomID("ot_", 24), CustomerEmail: strings.ToLower(strings.TrimSpace(input.CustomerEmail)),
		Items: append([]CartLine(nil), view.Items...), Currency: view.Currency, Subtotal: view.Subtotal,
		ShippingAmount: shipping, DiscountAmount: discount, TotalAmount: discountedSubtotal + shipping, OrderStatus: "PENDING_PAYMENT",
		PaymentStatus: "PENDING", FulfillmentStatus: "UNFULFILLED", ShippingAddress: input.ShippingAddress,
		CreatedAt: now,
	}
	store.orders[order.OrderNumber] = order
	if idempotencyKey != "" {
		store.idempotency[idempotencyKey] = order.OrderNumber
	}
	return *order, false, nil
}

func checkoutDiscount(subtotal float64, code string) float64 {
	switch strings.ToUpper(strings.TrimSpace(code)) {
	case "YAFA20":
		return float64(int(subtotal*0.2 + 0.5))
	case "NATURE15":
		return float64(int(subtotal*0.15 + 0.5))
	case "FLAT500":
		return min(500, subtotal)
	case "WELCOME10":
		return float64(int(subtotal*0.1 + 0.5))
	default:
		return 0
	}
}

func (store *Store) AttachRazorpayOrder(orderNumber, razorpayOrderID string) (Order, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	order, ok := store.orders[orderNumber]
	if !ok {
		return Order{}, ErrOrderNotFound
	}
	order.RazorpayOrderID = razorpayOrderID
	return *order, nil
}

func (store *Store) VerifyRazorpayPayment(razorpayOrderID, paymentID string) (Order, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	for _, order := range store.orders {
		if order.RazorpayOrderID == razorpayOrderID {
			order.RazorpayPaymentID = paymentID
			if order.PaymentStatus == "PENDING" || order.PaymentStatus == "FAILED" {
				order.PaymentStatus = "AUTHORIZED"
			}
			return *order, nil
		}
	}
	return Order{}, ErrPaymentOrderNotFound
}

func (store *Store) RecordRazorpayPayment(razorpayOrderID, paymentID, status string) (Order, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	for _, order := range store.orders {
		if order.RazorpayOrderID != razorpayOrderID {
			continue
		}
		if paymentID != "" {
			order.RazorpayPaymentID = paymentID
		}
		switch status {
		case "captured", "paid":
			order.PaymentStatus = "CAPTURED"
			order.OrderStatus = "PAID"
		case "failed":
			order.PaymentStatus = "FAILED"
		}
		return *order, nil
	}
	return Order{}, ErrPaymentOrderNotFound
}

func (store *Store) CreateOrderForUser(ownerID string, input CreateOrderInput, idempotencyKey string) (Order, bool, error) {
	if _, err := store.GetCartForUser(input.CartID, ownerID); err != nil {
		return Order{}, false, err
	}
	order, replayed, err := store.CreateOrder(input, idempotencyKey)
	if err != nil {
		return Order{}, false, err
	}
	store.mu.Lock()
	if stored := store.orders[order.OrderNumber]; stored != nil {
		stored.UserID = ownerID
		stored.AccessToken = ""
		order = *stored
	}
	store.mu.Unlock()
	return order, replayed, nil
}

func (store *Store) GetOrderForUser(orderNumber, ownerID string) (Order, error) {
	store.mu.RLock()
	defer store.mu.RUnlock()
	order, ok := store.orders[orderNumber]
	if !ok {
		return Order{}, ErrOrderNotFound
	}
	if ownerID == "" || order.UserID != ownerID {
		return Order{}, ErrOrderAccessDenied
	}
	result := *order
	result.AccessToken = ""
	return result, nil
}

// ListOrdersForUser returns only orders owned by the authenticated user. It
// deliberately never accepts an owner id supplied by the browser.
func (store *Store) ListOrdersForUser(ownerID string) []Order {
	store.mu.RLock()
	defer store.mu.RUnlock()
	orders := make([]Order, 0)
	for _, order := range store.orders {
		if ownerID == "" || order.UserID != ownerID {
			continue
		}
		item := *order
		item.AccessToken = ""
		orders = append(orders, item)
	}
	sort.Slice(orders, func(i, j int) bool { return orders[i].CreatedAt.After(orders[j].CreatedAt) })
	return orders
}

func (store *Store) GetOrder(orderNumber, accessToken string) (Order, error) {
	store.mu.RLock()
	defer store.mu.RUnlock()
	order, ok := store.orders[orderNumber]
	if !ok {
		return Order{}, ErrOrderNotFound
	}
	if accessToken == "" || accessToken != order.AccessToken {
		return Order{}, ErrOrderAccessDenied
	}
	result := *order
	result.AccessToken = ""
	return result, nil
}

func (store *Store) cartViewLocked(cart *Cart) CartView {
	view := CartView{ID: cart.ID, Currency: "INR", UpdatedAt: cart.UpdatedAt, Items: []CartLine{}}
	for variantID, quantity := range cart.Items {
		ref, ok := store.catalog.variants[variantID]
		if !ok || !ref.variant.IsActive || (ref.variant.Stock != nil && *ref.variant.Stock <= 0) {
			continue
		}
		shade := (*string)(nil)
		if ref.variant.Shade != nil {
			value := ref.variant.Shade.Name
			shade = &value
		}
		image := (*string)(nil)
		if ref.product.Images.PathsVerified {
			image = ref.product.Images.Primary
		}
		line := CartLine{
			Key: ref.product.ID + ":" + variantID, ProductID: ref.product.ID, VariantID: variantID,
			Name: ref.product.Name, Slug: ref.product.Slug, ProductType: ref.product.ProductType,
			Currency: ref.product.Commerce.Currency, UnitPrice: ref.variant.Price, Quantity: quantity,
			Size: ref.variant.Size, Shade: shade, Image: image,
		}
		view.Items = append(view.Items, line)
		view.ItemCount += quantity
		view.Subtotal += line.UnitPrice * float64(quantity)
		view.Currency = line.Currency
	}
	sort.Slice(view.Items, func(i, j int) bool { return view.Items[i].Key < view.Items[j].Key })
	return view
}

func validateAddress(address Address) error {
	if strings.TrimSpace(address.RecipientName) == "" || strings.TrimSpace(address.Line1) == "" ||
		strings.TrimSpace(address.City) == "" || strings.TrimSpace(address.StateRegion) == "" ||
		strings.TrimSpace(address.PostalCode) == "" {
		return ErrInvalidAddress
	}
	if len(address.CountryCode) != 2 {
		return ErrInvalidAddress
	}
	return nil
}

func validEmail(value string) bool {
	value = strings.TrimSpace(value)
	parsed, err := mail.ParseAddress(value)
	return err == nil && strings.EqualFold(parsed.Address, value) && strings.Contains(value, "@")
}

func randomID(prefix string, bytes int) string {
	buffer := make([]byte, bytes)
	if _, err := rand.Read(buffer); err != nil {
		panic(fmt.Sprintf("secure random source unavailable: %v", err))
	}
	return prefix + hex.EncodeToString(buffer)
}
