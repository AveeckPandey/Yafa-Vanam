package commerce

import (
	"errors"
	"strings"
	"testing"
	"time"
)

func TestCouponDiscountAmountMatchesLegacyMaths(t *testing.T) {
	discountCap := 400.0
	cases := []struct {
		name     string
		coupon   Coupon
		subtotal float64
		want     float64
	}{
		{"percentage rounds half up", Coupon{PromotionType: "PERCENTAGE", Value: 10}, 1234, 123},
		{"legacy YAFA20 on 2400", Coupon{PromotionType: "PERCENTAGE", Value: 20}, 2400, 480},
		{"absolute never exceeds subtotal", Coupon{PromotionType: "ABSOLUTE", Value: 500}, 300, 300},
		{"absolute applies fully", Coupon{PromotionType: "ABSOLUTE", Value: 500}, 900, 500},
		{"cap bounds percentage", Coupon{PromotionType: "PERCENTAGE", Value: 50, MaxDiscountCap: &discountCap}, 1200, 400},
		{"unknown type discounts nothing", Coupon{PromotionType: "MYSTERY", Value: 99}, 1000, 0},
	}
	for _, testCase := range cases {
		if got := couponDiscountAmount(testCase.coupon, testCase.subtotal); got != testCase.want {
			t.Errorf("%s: couponDiscountAmount() = %v, want %v", testCase.name, got, testCase.want)
		}
	}
}

func TestValidateCouponForOrderRejectsEveryExhaustionPath(t *testing.T) {
	past := time.Now().UTC().Add(-time.Hour)
	future := time.Now().UTC().Add(time.Hour)
	cases := []struct {
		name   string
		coupon Coupon
		sub    float64
		byUser int
		want   error
	}{
		{"inactive", Coupon{IsActive: false, MaxUses: 1}, 100, 0, ErrCouponInvalid},
		{"expired", Coupon{IsActive: true, MaxUses: 1, ExpiresAt: &past}, 100, 0, ErrCouponExpired},
		{"globally exhausted", Coupon{IsActive: true, Uses: 5, MaxUses: 5}, 100, 0, ErrCouponLimitReached},
		{"per-user exhausted", Coupon{IsActive: true, MaxUses: 9, PerUserLimit: 2}, 100, 2, ErrCouponLimitReached},
		{"below minimum", Coupon{IsActive: true, MaxUses: 9, MinimumOrderAmount: 500}, 499, 0, ErrCouponMinimumOrder},
	}
	for _, testCase := range cases {
		if err := validateCouponForOrder(testCase.coupon, testCase.sub, testCase.byUser); !errors.Is(err, testCase.want) {
			t.Errorf("%s: validateCouponForOrder() = %v, want %v", testCase.name, err, testCase.want)
		}
	}
	valid := Coupon{IsActive: true, MaxUses: 9, PerUserLimit: 2, ExpiresAt: &future}
	if err := validateCouponForOrder(valid, 100, 1); err != nil {
		t.Fatalf("validateCouponForOrder(valid) = %v, want nil", err)
	}
}

// orderInput is the shared checkout payload used by every coupon flow test.
func orderInput(cartID, code string) CreateOrderInput {
	return CreateOrderInput{
		CartID: cartID, CustomerEmail: "customer@example.com", DiscountCode: code,
		ShippingAddress: Address{RecipientName: "A Customer", Line1: "1 Forest Road", City: "Pune", StateRegion: "Maharashtra", PostalCode: "411001"},
	}
}

// filledCart creates a cart holding two units of the cheapest variant.
func filledCart(t *testing.T, store *Store) string {
	t.Helper()
	cart, err := store.CreateCart()
	if err != nil {
		t.Fatalf("CreateCart() error = %v", err)
	}
	if _, err := store.AddCartItem(cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItem() error = %v", err)
	}
	return cart.ID
}

// attemptOrder drives a cart to order creation and surfaces the raw error so
// rejection paths can assert on sentinel values.
func attemptOrder(t *testing.T, store *Store, code string) error {
	t.Helper()
	_, _, err := store.CreateOrder(orderInput(filledCart(t, store), code), "")
	return err
}

// fullOrderFlow runs a cart through successful order creation.
func fullOrderFlow(t *testing.T, store *Store, code string) Order {
	t.Helper()
	order, replayed, err := store.CreateOrder(orderInput(filledCart(t, store), code), "")
	if err != nil || replayed {
		t.Fatalf("CreateOrder(code=%q) replayed=%v error=%v", code, replayed, err)
	}
	return order
}

func TestOrderRejectsUnknownAndUnusableCodes(t *testing.T) {
	store := NewStore(testCatalog(t))
	if err := attemptOrder(t, store, "NOTAREALCODE"); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("unknown code error = %v, want ErrCouponInvalid", err)
	}

	expired := time.Now().UTC().Add(-time.Minute)
	store.coupons["OLDIE"] = Coupon{Code: "OLDIE", PromotionType: "PERCENTAGE", Value: 30, IsActive: true, ExpiresAt: &expired}
	if err := attemptOrder(t, store, "oldie"); !errors.Is(err, ErrCouponExpired) {
		t.Fatalf("expired code error = %v, want ErrCouponExpired (case-insensitive lookup expected)", err)
	}
}

func TestLegacyCodesStillPriceIdentically(t *testing.T) {
	store := NewStore(testCatalog(t))
	expectations := map[string]float64{"YAFA20": 480, "NATURE15": 360, "FLAT500": 500, "WELCOME10": 240}
	for code, want := range expectations {
		order := fullOrderFlow(t, store, strings.ToLower(code)) // client casing is normalized
		if order.DiscountAmount != want {
			t.Errorf("%s discount = %v, want %v", code, order.DiscountAmount, want)
		}
		if order.DiscountCode != code {
			t.Errorf("%s stored DiscountCode = %q, want normalized %q", code, order.DiscountCode, code)
		}
	}
}

func TestWelcomeCodeGenerationShape(t *testing.T) {
	seen := map[string]bool{}
	for attempt := 0; attempt < 200; attempt++ {
		code, err := generateWelcomeCode()
		if err != nil {
			t.Fatalf("generateWelcomeCode() error = %v", err)
		}
		if !strings.HasPrefix(code, welcomeCodePrefix) || len(code) != len(welcomeCodePrefix)+8 {
			t.Fatalf("code = %q, want WELCOME10- plus 8 characters", code)
		}
		for _, character := range code[len(welcomeCodePrefix):] {
			if strings.ContainsRune("01ILO", character) {
				t.Fatalf("code %q contains an ambiguous character", code)
			}
		}
		seen[code] = true
	}
	if len(seen) < 199 {
		t.Fatalf("expected near-zero collisions across 200 draws, got %d unique codes", len(seen))
	}
}

func TestMemoryStoreRedeemsCouponOncePerPaymentVerification(t *testing.T) {
	store := NewStore(testCatalog(t))
	order := fullOrderFlow(t, store, "WELCOME10")
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_verify_1"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	if _, err := store.VerifyRazorpayPayment("order_verify_1", "pay_1"); err != nil {
		t.Fatalf("VerifyRazorpayPayment() error = %v", err)
	}
	if _, err := store.VerifyRazorpayPayment("order_verify_1", "pay_1"); err != nil {
		t.Fatalf("second VerifyRazorpayPayment() error = %v", err)
	}
	if uses := store.coupons["WELCOME10"].Uses; uses != 1 {
		t.Fatalf("WELCOME10 uses after double verification = %d, want 1", uses)
	}
	if redeemed := store.redemptions[order.OrderNumber]; redeemed != "WELCOME10" {
		t.Fatalf("redemptions[%s] = %q, want WELCOME10", order.OrderNumber, redeemed)
	}
}
