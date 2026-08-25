package commerce

import (
	"context"
	"crypto/rand"
	"errors"
	"math/big"
	"strings"
	"time"
)

// Discount validation used to be a hardcoded switch in checkoutDiscount().
// It now resolves against real promotion/coupon rows so codes can expire,
// cap, and be personalised without redeploying the API. The legacy public
// codes are seeded by migration 000007 with enormous limits, which preserves
// the old behaviour exactly.
var (
	ErrCouponInvalid      = errors.New("this discount code is not valid")
	ErrCouponExpired      = errors.New("this discount code has expired")
	ErrCouponLimitReached = errors.New("this discount code has reached its usage limit")
	ErrCouponMinimumOrder = errors.New("order does not meet this code's minimum amount")
)

const welcomeCodePrefix = "WELCOME10-"

type Coupon struct {
	ID                 string     `json:"id"`
	Code               string     `json:"code"`
	PromotionType      string     `json:"promotion_type"`
	Value              float64    `json:"value"`
	MaxDiscountCap     *float64   `json:"max_discount_cap,omitempty"`
	MinimumOrderAmount float64    `json:"minimum_order_amount"`
	MaxUses            int        `json:"max_uses"`
	Uses               int        `json:"uses"`
	PerUserLimit       int        `json:"per_user_limit"`
	ExpiresAt          *time.Time `json:"expires_at,omitempty"`
	IsActive           bool       `json:"is_active"`
}

// WelcomeCoupon is what the internal issue endpoint returns to the Lambda.
// It deliberately carries no internal identifiers — only what the customer
// email needs.
type WelcomeCoupon struct {
	Code            string    `json:"code"`
	DiscountPercent float64   `json:"discount_percent"`
	ExpiresAt       time.Time `json:"expires_at"`
}

// NormalizeDiscountCode canonicalises client input before lookup or storage:
// trimmed, upper-cased; empty stays empty.
func NormalizeDiscountCode(code string) string {
	return strings.ToUpper(strings.TrimSpace(code))
}

// couponDiscountAmount is the single source of truth for turning a validated
// coupon + subtotal into a rupee amount. PERCENTAGE rounds half-up to whole
// rupees (matching the previous int(x*rate+0.5) behaviour); ABSOLUTE caps at
// the subtotal so a discount never produces a negative payable.
func couponDiscountAmount(coupon Coupon, subtotal float64) float64 {
	var amount float64
	switch strings.ToUpper(coupon.PromotionType) {
	case "PERCENTAGE":
		amount = float64(int(subtotal*coupon.Value/100 + 0.5))
	case "ABSOLUTE":
		amount = min(coupon.Value, subtotal)
	}
	if coupon.MaxDiscountCap != nil {
		amount = min(amount, *coupon.MaxDiscountCap)
	}
	return max(0.0, amount)
}

func validateCouponForOrder(coupon Coupon, subtotal float64, previousUsesByUser int) error {
	if !coupon.IsActive {
		return ErrCouponInvalid
	}
	if coupon.ExpiresAt != nil && !subtotalBefore(coupon.ExpiresAt) {
		return ErrCouponExpired
	}
	// A zero limit means "unset" (unlimited): legacy seeds and hand-built
	// Coupon values rely on that, so never compare against a zero bound.
	if (coupon.MaxUses > 0 && coupon.Uses >= coupon.MaxUses) ||
		(coupon.PerUserLimit > 0 && previousUsesByUser >= coupon.PerUserLimit) {
		return ErrCouponLimitReached
	}
	if subtotal < coupon.MinimumOrderAmount {
		return ErrCouponMinimumOrder
	}
	return nil
}

func subtotalBefore(expiresAt *time.Time) bool { return time.Now().UTC().Before(*expiresAt) }

// generateWelcomeCode returns WELCOME10-<8 chars> from an unambiguous
// base32 alphabet (no 0/O/1/I/L) — roughly 32^8 possibilities, unguessable
// and safe to read aloud from an email.
func generateWelcomeCode() (string, error) {
	const alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
	code := make([]byte, 8)
	for index := range code {
		draw, err := rand.Int(rand.Reader, big.NewInt(int64(len(alphabet))))
		if err != nil {
			return "", err
		}
		code[index] = alphabet[draw.Int64()]
	}
	return welcomeCodePrefix + string(code), nil
}

// legacyCoupons mirrors migration 000007's seeds for the in-memory store, so
// database-free development and tests price discounts identically to prod.
func legacyCoupons() map[string]Coupon {
	unlimited := 1_000_000
	definitions := []struct {
		code  string
		kind  string
		value float64
	}{
		{"YAFA20", "PERCENTAGE", 20}, {"NATURE15", "PERCENTAGE", 15},
		{"FLAT500", "ABSOLUTE", 500}, {"WELCOME10", "PERCENTAGE", 10},
	}
	coupons := make(map[string]Coupon, len(definitions))
	for _, definition := range definitions {
		coupons[definition.code] = Coupon{
			Code: definition.code, PromotionType: definition.kind, Value: definition.value,
			MaxUses: unlimited, Uses: 0, PerUserLimit: unlimited, IsActive: true,
		}
	}
	return coupons
}

// LifecycleStore is implemented by stores that can back the internal
// lifecycle endpoints (currently PostgresStore — the Lambda talks to the
// production API, which always runs Postgres).
type LifecycleStore interface {
	IssueWelcomeCoupon(ctx context.Context, email, cognitoSubject string) (WelcomeCoupon, error)
	RecordLifecycleMessage(ctx context.Context, message LifecycleMessageInput) (string, error)
}

type LifecycleMessageInput struct {
	Email             string `json:"email"`
	Channel           string `json:"channel"`      // e.g. EMAIL
	TriggerName       string `json:"trigger_name"` // e.g. welcome_coupon
	TemplateName      string `json:"template_name,omitempty"`
	CouponCode        string `json:"coupon_code,omitempty"`
	ProviderMessageID string `json:"provider_message_id,omitempty"`
	Status            string `json:"status"` // SENT / FAILED / PENDING
}
