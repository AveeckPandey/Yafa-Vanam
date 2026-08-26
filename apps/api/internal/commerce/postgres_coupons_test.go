package commerce

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// These tests run only when TEST_DATABASE_URL points at a disposable database
// (see postgres_store_test.go). They cover the server-enforced guarantees the
// memory store cannot express: partial unique indexes, redemption rows, and
// cross-table idempotency.
func TestPostgresIssueWelcomeCouponIsIdempotent(t *testing.T) {
	store := newTestPostgresStore(t)
	ctx := context.Background()

	first, err := store.IssueWelcomeCoupon(ctx, "Welcome.User@Example.com", "cognito-sub-1")
	if err != nil {
		t.Fatalf("IssueWelcomeCoupon() error = %v", err)
	}
	if !strings.HasPrefix(first.Code, welcomeCodePrefix) || len(first.Code) != len(welcomeCodePrefix)+8 {
		t.Fatalf("code = %q, want %s plus 8 characters", first.Code, welcomeCodePrefix)
	}
	if first.DiscountPercent != 10 {
		t.Fatalf("discount percent = %v, want 10", first.DiscountPercent)
	}
	if first.ExpiresAt.Before(time.Now().UTC().Add(29 * 24 * time.Hour)) {
		t.Fatalf("expires_at = %v, want roughly 30 days out", first.ExpiresAt)
	}

	retry, err := store.IssueWelcomeCoupon(ctx, "welcome.user@example.com", "")
	if err != nil || retry.Code != first.Code {
		t.Fatalf("duplicate issue = %#v error %v, want the SAME code %q", retry, err, first.Code)
	}
	if other, err := store.IssueWelcomeCoupon(ctx, "someoneelse@example.com", "cognito-sub-2"); err != nil || other.Code == first.Code {
		t.Fatalf("a different user must get their own code, got %#v error %v", other, err)
	}
}

func TestPostgresOrderValidatesAndRedeemsCouponAtVerifyTime(t *testing.T) {
	store := newTestPostgresStore(t)
	ctx := context.Background()

	coupon, err := store.IssueWelcomeCoupon(ctx, "redeemer@example.com", "cognito-sub-3")
	if err != nil {
		t.Fatalf("IssueWelcomeCoupon() error = %v", err)
	}
	// Personalised coupons are owner-bound: resolve the account the welcome
	// upsert created and order as that user.
	var userID string
	if err := store.db.QueryRow(ctx,
		`SELECT id::text FROM users WHERE email = 'redeemer@example.com'`).Scan(&userID); err != nil {
		t.Fatal(err)
	}

	cart, err := store.CreateCartForUser(userID)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(userID, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}

	// Below-minimum and exhausted paths reject before an order exists.
	if _, _, err := store.CreateOrderForUser(userID, CreateOrderInput{
		CartID: cart.ID, CustomerEmail: "redeemer@example.com", DiscountCode: "NOTAREALCODE",
		ShippingAddress: Address{RecipientName: "A", Line1: "1 Road", City: "Pune", StateRegion: "MH", PostalCode: "411001"},
	}, ""); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("unknown code error = %v, want ErrCouponInvalid", err)
	}

	order, replayed, err := store.CreateOrderForUser(userID, CreateOrderInput{
		CartID: cart.ID, CustomerEmail: "redeemer@example.com", DiscountCode: strings.ToLower(coupon.Code),
		ShippingAddress: Address{RecipientName: "A", Line1: "1 Road", City: "Pune", StateRegion: "MH", PostalCode: "411001"},
	}, "checkout-coupon-1")
	if err != nil || replayed {
		t.Fatalf("CreateOrderForUser() replayed=%v error=%v", replayed, err)
	}
	if order.DiscountAmount != 240 { // 10% of the 2400 subtotal
		t.Fatalf("DiscountAmount = %v, want 240", order.DiscountAmount)
	}

	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_coupon_verify"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	for attempt := 0; attempt < 2; attempt++ {
		if _, err := store.VerifyRazorpayPayment("order_coupon_verify", "pay_coupon_verify"); err != nil {
			t.Fatalf("VerifyRazorpayPayment() attempt %d error = %v", attempt+1, err)
		}
	}

	var redemptions int
	var uses int
	if err := store.db.QueryRow(ctx,
		`SELECT COUNT(*) FROM coupon_redemptions WHERE order_id=$1::uuid`, order.ID).Scan(&redemptions); err != nil {
		t.Fatal(err)
	}
	if err := store.db.QueryRow(ctx,
		`SELECT uses FROM coupons WHERE code=$1`, coupon.Code).Scan(&uses); err != nil {
		t.Fatal(err)
	}
	if redemptions != 1 || uses != 1 {
		t.Fatalf("double verify produced redemptions=%d uses=%d, want exactly one of each", redemptions, uses)
	}

	messageID, err := store.RecordLifecycleMessage(ctx, LifecycleMessageInput{
		Email: "redeemer@example.com", TriggerName: "welcome_coupon",
		CouponCode: coupon.Code, ProviderMessageID: "ses-test-1", Status: "SENT",
	})
	if err != nil || messageID == "" {
		t.Fatalf("RecordLifecycleMessage() = %q error %v", messageID, err)
	}
	if _, err := store.RecordLifecycleMessage(ctx, LifecycleMessageInput{Email: "nobody-here@example.com"}); !errors.Is(err, ErrInvalidEmail) {
		t.Fatalf("unknown-email RecordLifecycleMessage() error = %v, want ErrInvalidEmail", err)
	}
}
