package commerce

import (
	"context"
	"errors"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/database"
	"github.com/jackc/pgx/v5/pgxpool"
)

// newTestPostgresStore builds a PostgresStore against a real database. Tests
// skip unless TEST_DATABASE_URL points at an disposable instance, e.g. the
// docker-compose postgres:
//
//	TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/yafa_vanam?sslmode=disable go test ./internal/commerce/
func newTestPostgresStore(t *testing.T) *PostgresStore {
	t.Helper()
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL not set; skipping PostgreSQL persistence tests")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("pgxpool.New() error = %v", err)
	}
	t.Cleanup(pool.Close)
	if err := pool.Ping(ctx); err != nil {
		t.Fatalf("database ping error = %v", err)
	}
	migrationsPath := os.Getenv("MIGRATIONS_PATH")
	if migrationsPath == "" {
		migrationsPath = "../../db/migrations"
	}
	if err := database.ApplyPending(ctx, pool, migrationsPath); err != nil {
		t.Fatalf("ApplyPending() error = %v", err)
	}
	// Commerce tables start each test empty; users/auth data remain available
	// across cases. TRUNCATE ... CASCADE clears dependent payments,
	// coupon_redemptions, and user_promotion_redemptions rows too.
	if _, err := pool.Exec(ctx, `TRUNCATE carts, orders, lifecycle_messages CASCADE`); err != nil {
		t.Fatalf("truncate error = %v", err)
	}
	if _, err := pool.Exec(ctx, `DELETE FROM coupons WHERE user_id IS NOT NULL`); err != nil {
		t.Fatalf("delete test coupons error = %v", err)
	}
	return NewPostgresStore(pool, testCatalog(t))
}

// seedTestUser inserts a users row because carts.user_id and orders.user_id
// are foreign keys into the auth user table — exactly as production receives
// owner ids from authenticated sessions. The account is created email-verified
// because every real sign-in path confirms the address first.
func seedTestUser(t *testing.T, pool *pgxpool.Pool, id string) {
	t.Helper()
	seedVerifiedUser(t, pool, id, "test-"+id+"@yafa.local")
}

// seedVerifiedUser seeds an account with a specific address so promotion
// tests can target the exact user a voucher is bound to.
func seedVerifiedUser(t *testing.T, pool *pgxpool.Pool, id, email string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	_, err := pool.Exec(ctx,
		`INSERT INTO users (id, email, email_verified_at) VALUES ($1::uuid, $2, NOW())
		 ON CONFLICT (id) DO NOTHING`,
		id, email)
	if err != nil {
		t.Fatalf("seed user %s error = %v", id, err)
	}
}

const postgresTestTimeout = 30 * time.Second

func TestPostgresCartLifecycleAndOwnership(t *testing.T) {
	store := newTestPostgresStore(t)

	guestCart, err := store.CreateCart()
	if err != nil || guestCart.ID == "" {
		t.Fatalf("CreateCart() = %#v, error %v", guestCart, err)
	}
	if _, err := store.GetCart(guestCart.ID); err != nil {
		t.Fatalf("guest GetCart() error = %v", err)
	}
	updated, err := store.AddCartItem(guestCart.ID, "p1", "v1", 2)
	if err != nil || updated.ItemCount != 2 || updated.Subtotal != 2400 {
		t.Fatalf("AddCartItem() = %#v, error %v", updated, err)
	}

	// A guest cart can be claimed exactly once; later claims are rejected.
	owner := "11111111-1111-1111-1111-111111111111"
	rival := "22222222-2222-2222-2222-222222222222"
	seedTestUser(t, store.db, owner)
	seedTestUser(t, store.db, rival)
	if err := store.ClaimCartForUser(guestCart.ID, owner); err != nil {
		t.Fatalf("ClaimCartForUser() error = %v", err)
	}
	if err := store.ClaimCartForUser(guestCart.ID, rival); !errors.Is(err, ErrCartAccessDenied) {
		t.Fatalf("second ClaimCartForUser() error = %v, want ErrCartAccessDenied", err)
	}
	if _, err := store.GetCart(guestCart.ID); !errors.Is(err, ErrCartAccessDenied) {
		t.Fatalf("guest GetCart() after claim error = %v, want ErrCartAccessDenied", err)
	}

	if _, err := store.GetCartForUser(guestCart.ID, owner); err != nil {
		t.Fatalf("GetCartForUser() error = %v", err)
	}
	if _, err := store.GetCartForUser(guestCart.ID, rival); !errors.Is(err, ErrCartAccessDenied) {
		t.Fatalf("foreign GetCartForUser() error = %v, want ErrCartAccessDenied", err)
	}
	if _, err := store.SetCartItemForUser(owner, guestCart.ID, "v1", 1); err != nil {
		t.Fatalf("SetCartItemForUser() error = %v", err)
	}
	if removed, err := store.RemoveCartItemForUser(owner, guestCart.ID, "v1"); err != nil || removed.ItemCount != 0 {
		t.Fatalf("RemoveCartItemForUser() = %#v, error %v", removed, err)
	}
	if _, err := store.GetCartForUser("cart_doesnotexist", owner); !errors.Is(err, ErrCartNotFound) {
		t.Fatalf("missing GetCartForUser() error = %v, want ErrCartNotFound", err)
	}
}

func TestPostgresOrderFlowIdempotencyAndRazorpay(t *testing.T) {
	store := newTestPostgresStore(t)

	guestCart, err := store.CreateCart()
	if err != nil {
		t.Fatalf("CreateCart() error = %v", err)
	}
	if _, err := store.AddCartItem(guestCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItem() error = %v", err)
	}
	input := CreateOrderInput{
		CartID: guestCart.ID, CustomerEmail: "customer@example.com",
		ShippingAddress: Address{RecipientName: "A Customer", Line1: "1 Forest Road", City: "Pune", StateRegion: "Maharashtra", PostalCode: "411001"},
	}

	order, replayed, err := store.CreateOrder(input, "checkout-pg-1")
	if err != nil || replayed {
		t.Fatalf("CreateOrder() = replayed %v, error %v", replayed, err)
	}
	// Guest checkouts receive no promotion; the 2400 subtotal crosses the
	// 1999 free-shipping threshold, matching the storefront's own checkout math.
	if order.TotalAmount != 2400 || order.DiscountAmount != 0 || order.ShippingAmount != 0 ||
		order.ShippingAddress.CountryCode != "IN" || order.AccessToken == "" {
		t.Fatalf("order amounts/token wrong: total=%v discount=%v shipping=%v token-set=%v country=%q",
			order.TotalAmount, order.DiscountAmount, order.ShippingAmount, order.AccessToken != "", order.ShippingAddress.CountryCode)
	}

	replay, replayed, err := store.CreateOrder(input, "checkout-pg-1")
	if err != nil || !replayed || replay.OrderNumber != order.OrderNumber || replay.Items[0].Key != "p1:v1" {
		t.Fatalf("idempotent replay = %#v replayed %v error %v", replay, replayed, err)
	}

	if _, err := store.GetOrder(order.OrderNumber, "wrong-token"); !errors.Is(err, ErrOrderAccessDenied) {
		t.Fatalf("wrong token error = %v, want ErrOrderAccessDenied", err)
	}
	read, err := store.GetOrder(order.OrderNumber, order.AccessToken)
	if err != nil || read.AccessToken != "" {
		t.Fatalf("GetOrder() = %#v error %v", read, err)
	}

	attached, err := store.AttachRazorpayOrder(order.OrderNumber, "order_rzp_pg_1")
	if err != nil || attached.RazorpayOrderID != "order_rzp_pg_1" {
		t.Fatalf("AttachRazorpayOrder() = %#v error %v", attached, err)
	}
	verified, err := store.VerifyRazorpayPayment("order_rzp_pg_1", "pay_rzp_pg_1")
	if err != nil || verified.PaymentStatus != "AUTHORIZED" {
		t.Fatalf("VerifyRazorpayPayment() = %#v error %v", verified, err)
	}
	captured, err := store.RecordRazorpayPayment("order_rzp_pg_1", "", "captured")
	if err != nil || captured.PaymentStatus != "CAPTURED" || captured.OrderStatus != "PAID" {
		t.Fatalf("RecordRazorpayPayment(captured) = %#v error %v", captured, err)
	}
	failed, err := store.RecordRazorpayPayment("order_rzp_pg_1", "pay_rzp_retry", "failed")
	if err != nil || failed.PaymentStatus != "FAILED" {
		t.Fatalf("RecordRazorpayPayment(failed) = %#v error %v", failed, err)
	}
	if _, err := store.RecordRazorpayPayment("order_unknown", "", "captured"); !errors.Is(err, ErrPaymentOrderNotFound) {
		t.Fatalf("unknown razorpay order error = %v, want ErrPaymentOrderNotFound", err)
	}
}

func TestPostgresConcurrentIdempotencyRace(t *testing.T) {
	store := newTestPostgresStore(t)
	guestCart, err := store.CreateCart()
	if err != nil {
		t.Fatalf("CreateCart() error = %v", err)
	}
	if _, err := store.AddCartItem(guestCart.ID, "p1", "v1", 1); err != nil {
		t.Fatalf("AddCartItem() error = %v", err)
	}
	input := CreateOrderInput{
		CartID: guestCart.ID, CustomerEmail: "race@example.com",
		ShippingAddress: Address{RecipientName: "Racer", Line1: "1 Track", City: "Pune", StateRegion: "Maharashtra", PostalCode: "411001"},
	}

	const racers = 4
	results := make([]struct {
		order    Order
		replayed bool
		err      error
	}, racers)
	var wg sync.WaitGroup
	for i := range racers {
		wg.Add(1)
		go func(slot int) {
			defer wg.Done()
			order, replayed, err := store.CreateOrder(input, "race-key-1")
			results[slot].order, results[slot].replayed, results[slot].err = order, replayed, err
		}(i)
	}
	wg.Wait()

	fresh, orderNumbers := 0, map[string]bool{}
	for _, result := range results {
		if result.err != nil {
			t.Fatalf("concurrent CreateOrder() error = %v", result.err)
		}
		orderNumbers[result.order.OrderNumber] = true
		if !result.replayed {
			fresh++
		}
	}
	if fresh != 1 || len(orderNumbers) != 1 {
		t.Fatalf("want exactly one fresh order for one number, got fresh=%d numbers=%v", fresh, orderNumbers)
	}
}

func TestPostgresUserOrdersListingAndBinding(t *testing.T) {
	store := newTestPostgresStore(t)
	owner := "33333333-3333-3333-3333-333333333333"
	seedTestUser(t, store.db, owner)

	first, err := store.CreateCart()
	if err != nil {
		t.Fatalf("CreateCart() error = %v", err)
	}
	if _, err := store.AddCartItem(first.ID, "p1", "v1", 1); err != nil {
		t.Fatalf("AddCartItem() error = %v", err)
	}
	baseInput := CreateOrderInput{
		CustomerEmail:   "user@example.com",
		ShippingAddress: Address{RecipientName: "Owner", Line1: "3 Hill", City: "Pune", StateRegion: "Maharashtra", PostalCode: "411001"},
	}

	userInput := baseInput
	userInput.CartID = first.ID
	// Production binds a guest cart to the account at login (claim), so the
	// user order flow requires an owned cart — mirror that here.
	if err := store.ClaimCartForUser(first.ID, owner); err != nil {
		t.Fatalf("ClaimCartForUser() error = %v", err)
	}
	userOrder, replayed, err := store.CreateOrderForUser(owner, userInput, "")
	if err != nil || replayed || userOrder.UserID != owner || userOrder.AccessToken != "" {
		t.Fatalf("CreateOrderForUser() = %#v replayed %v error %v", userOrder, replayed, err)
	}

	second, err := store.CreateCartForUser(owner)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(owner, second.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	secondInput := baseInput
	secondInput.CartID = second.ID
	if _, _, err := store.CreateOrderForUser(owner, secondInput, ""); err != nil {
		t.Fatalf("second CreateOrderForUser() error = %v", err)
	}

	listed := store.ListOrdersForUser(owner)
	if len(listed) != 2 {
		t.Fatalf("ListOrdersForUser() = %d orders, want 2", len(listed))
	}
	if listed[0].CreatedAt.Before(listed[1].CreatedAt) && listed[0].OrderNumber != listed[1].OrderNumber {
		t.Fatalf("listing not newest-first: %v then %v", listed[0].CreatedAt, listed[1].CreatedAt)
	}
	for _, order := range listed {
		if order.AccessToken != "" {
			t.Fatalf("listing leaked access token for %s", order.OrderNumber)
		}
	}
	if got := store.ListOrdersForUser(""); len(got) != 0 {
		t.Fatalf("empty owner listing returned %d orders, want 0", len(got))
	}
	if _, err := store.GetOrderForUser(userOrder.OrderNumber, "44444444-4444-4444-4444-444444444444"); !errors.Is(err, ErrOrderAccessDenied) {
		t.Fatalf("foreign GetOrderForUser() error = %v, want ErrOrderAccessDenied", err)
	}
}
