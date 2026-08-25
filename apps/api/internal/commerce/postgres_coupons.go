package commerce

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// lockedCoupon loads a coupon row with FOR UPDATE inside the caller's
// transaction so concurrent checkouts serialise on it, and counts how many
// times the ordering user has already redeemed that coupon. previousUsesByUser
// stays 0 for guests (no owner to count against).
func (store *PostgresStore) lockedCoupon(ctx context.Context, tx pgx.Tx, code, ownerID string) (Coupon, int, error) {
	var (
		coupon     Coupon
		usesByUser int
	)
	err := tx.QueryRow(ctx,
		`SELECT c.id::text, c.code, p.promotion_type, p.value::float8, c.max_discount_cap::float8,
		    c.minimum_order_amount::float8, c.max_uses, c.uses, c.per_user_limit, c.expires_at, c.is_active,
		    (SELECT COUNT(*) FROM coupon_redemptions r
		      WHERE r.coupon_id = c.id AND r.user_id = NULLIF($2,'')::uuid)
		 FROM coupons c JOIN promotions p ON p.id = c.promotion_id
		 WHERE UPPER(c.code) = $1
		 FOR UPDATE OF c`, code, ownerID).
		Scan(&coupon.ID, &coupon.Code, &coupon.PromotionType, &coupon.Value, &coupon.MaxDiscountCap,
			&coupon.MinimumOrderAmount, &coupon.MaxUses, &coupon.Uses, &coupon.PerUserLimit,
			&coupon.ExpiresAt, &coupon.IsActive, &usesByUser)
	if errors.Is(err, pgx.ErrNoRows) {
		return Coupon{}, 0, ErrCouponInvalid
	}
	if err != nil {
		return Coupon{}, 0, err
	}
	return coupon, usesByUser, nil
}

// VerifyRazorpayPayment flips the order to AUTHORIZED and, in the same
// transaction, redeems its coupon on the first successful verification.
// coupon_redemptions.order_id UNIQUE makes retries and verify/webhook races
// no-ops; abandoned carts never burn anything because nothing is written at
// order creation time.
func (store *PostgresStore) VerifyRazorpayPayment(razorpayOrderID, paymentID string) (Order, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Order{}, err
	}
	defer tx.Rollback(ctx)

	// Lock the order and read its PRE-update state: whether this call is the
	// one performing PENDING/FAILED -> AUTHORIZED decides whether the coupon
	// redemption belongs to us.
	var (
		priorStatus    string
		discountCode   string
		orderID        string
		userID         string
		discountAmount float64
	)
	err = tx.QueryRow(ctx,
		`SELECT id::text, payment_status, COALESCE(discount_code,''), COALESCE(user_id::text,''), discount_amount::float8
		 FROM orders WHERE razorpay_order_id=$1 FOR UPDATE`,
		razorpayOrderID).Scan(&orderID, &priorStatus, &discountCode, &userID, &discountAmount)
	if errors.Is(err, pgx.ErrNoRows) {
		return Order{}, ErrPaymentOrderNotFound
	}
	if err != nil {
		return Order{}, err
	}

	record, err := scanOrderRecord(tx.QueryRow(ctx,
		`UPDATE orders SET razorpay_payment_id=$2,
		    payment_status=CASE WHEN payment_status IN ('PENDING','FAILED') THEN 'AUTHORIZED' ELSE payment_status END,
		    updated_at=NOW()
		 WHERE razorpay_order_id=$1 RETURNING `+orderReturningColumns, razorpayOrderID, paymentID))
	if err != nil {
		return Order{}, err
	}
	if _, err := tx.Exec(ctx,
		`UPDATE payments SET provider_payment_id=$2, status='AUTHORIZED', updated_at=NOW()
		 WHERE provider_order_id=$1 AND status IN ('PENDING','FAILED')`, razorpayOrderID, paymentID); err != nil {
		return Order{}, err
	}

	firstSuccess := priorStatus == "PENDING" || priorStatus == "FAILED"
	if firstSuccess && discountCode != "" {
		if _, err := tx.Exec(ctx,
			`INSERT INTO coupon_redemptions (coupon_id, order_id, user_id, code_snapshot, discount_amount)
			 SELECT c.id, $1::uuid, NULLIF($2,'')::uuid, UPPER($3), $4
			 FROM coupons c WHERE UPPER(c.code) = UPPER($3)
			 ON CONFLICT (order_id) DO NOTHING`,
			orderID, userID, discountCode, discountAmount); err != nil {
			return Order{}, err
		}
		if _, err := tx.Exec(ctx,
			`UPDATE coupons SET uses = uses + 1
			 WHERE id = (SELECT coupon_id FROM coupon_redemptions WHERE order_id = $1::uuid)`,
			orderID); err != nil {
			return Order{}, err
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return Order{}, err
	}
	order, err := record.assemble()
	return order, err
}

// boundedContext derives a deadline from the caller's context (or Background)
// so every lifecycle operation is bounded like the rest of the store.
func boundedContext(ctx context.Context) (context.Context, context.CancelFunc) {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithTimeout(ctx, postgresTimeout)
}

// IssueWelcomeCoupon upserts the just-confirmed Cognito user (the Lambda fires
// before their first sign-in, so a users row may not exist yet) and returns
// their single welcome coupon, creating it only if absent. Safe under retry:
// the partial unique index uq_coupons_one_welcome_per_user turns any race
// into a unique violation, which resolves by reading the winner's row.
func (store *PostgresStore) IssueWelcomeCoupon(ctx context.Context, email, cognitoSubject string) (WelcomeCoupon, error) {
	ctx, cancel := boundedContext(ctx)
	defer cancel()
	email = strings.ToLower(strings.TrimSpace(email))
	if email == "" || !validEmail(email) {
		return WelcomeCoupon{}, ErrInvalidEmail
	}

	var userID string
	if err := store.db.QueryRow(ctx,
		`INSERT INTO users (email, cognito_subject, email_verified_at)
		 VALUES ($1, NULLIF($2,''), NOW())
		 ON CONFLICT (email) DO UPDATE SET
		    cognito_subject = COALESCE(users.cognito_subject, EXCLUDED.cognito_subject),
		    email_verified_at = COALESCE(users.email_verified_at, NOW())
		 RETURNING id::text`, email, strings.TrimSpace(cognitoSubject)).Scan(&userID); err != nil {
		return WelcomeCoupon{}, err
	}

	if issued, ok, err := findWelcomeCoupon(ctx, store.db, userID); err != nil || ok {
		return issued, err
	}

	promotion, err := store.welcomePromotionID(ctx)
	if err != nil {
		return WelcomeCoupon{}, err
	}
	for attempt := 0; attempt < 5; attempt++ {
		code, err := generateWelcomeCode()
		if err != nil {
			return WelcomeCoupon{}, err
		}
		var issued WelcomeCoupon
		err = store.db.QueryRow(ctx,
			`INSERT INTO coupons (promotion_id, user_id, code, max_uses, per_user_limit, expires_at, minimum_order_amount, is_active)
			 VALUES ($1::uuid, $2::uuid, $3, 1, 1, NOW() + interval '30 days', 0, TRUE)
			 RETURNING code, expires_at`, promotion, userID, code).
			Scan(&issued.Code, &issued.ExpiresAt)
		if err == nil {
			issued.DiscountPercent = welcomeDiscountPercent
			return issued, nil
		}
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			// Lost a race (same user's concurrent issue, or an astronomically
			// unlikely code collision): re-read whichever row won.
			if found, ok, scanErr := findWelcomeCoupon(ctx, store.db, userID); scanErr != nil {
				return WelcomeCoupon{}, scanErr
			} else if ok {
				return found, nil
			}
			continue // code collision without a winner yet — draw again
		}
		return WelcomeCoupon{}, err
	}
	return WelcomeCoupon{}, errors.New("could not allocate a unique welcome coupon code")
}

func findWelcomeCoupon(ctx context.Context, querier dbQuerier, userID string) (WelcomeCoupon, bool, error) {
	var issued WelcomeCoupon
	err := querier.QueryRow(ctx,
		`SELECT code, expires_at FROM coupons
		 WHERE user_id = $1::uuid AND code LIKE 'WELCOME10-%'
		 ORDER BY created_at DESC LIMIT 1`, userID).
		Scan(&issued.Code, &issued.ExpiresAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return WelcomeCoupon{}, false, nil
	}
	if err != nil {
		return WelcomeCoupon{}, false, err
	}
	issued.DiscountPercent = welcomeDiscountPercent
	return issued, true, nil
}

func (store *PostgresStore) welcomePromotionID(ctx context.Context) (string, error) {
	var promotionID string
	err := store.db.QueryRow(ctx,
		`INSERT INTO promotions (name, promotion_type, value, is_active)
		 SELECT 'Welcome 10% offer', 'PERCENTAGE', 10, TRUE
		 WHERE NOT EXISTS (SELECT 1 FROM promotions WHERE name = 'Welcome 10% offer')
		 RETURNING id::text`).Scan(&promotionID)
	if errors.Is(err, pgx.ErrNoRows) {
		err = store.db.QueryRow(ctx,
			`SELECT id::text FROM promotions WHERE name = 'Welcome 10% offer' ORDER BY created_at LIMIT 1`).Scan(&promotionID)
	}
	return promotionID, err
}

const welcomeDiscountPercent = 10.0

// RecordLifecycleMessage persists one lifecycle event (e.g. the SES delivery
// of a welcome coupon) against the user and, when known, their coupon.
func (store *PostgresStore) RecordLifecycleMessage(ctx context.Context, message LifecycleMessageInput) (string, error) {
	ctx, cancel := boundedContext(ctx)
	defer cancel()
	email := strings.ToLower(strings.TrimSpace(message.Email))
	if email == "" {
		return "", ErrInvalidEmail
	}
	channel := strings.ToUpper(strings.TrimSpace(message.Channel))
	if channel == "" {
		channel = "EMAIL"
	}
	status := strings.ToUpper(strings.TrimSpace(message.Status))
	if status == "" {
		status = "SENT"
	}
	var id string
	err := store.db.QueryRow(ctx,
		`INSERT INTO lifecycle_messages (user_id, channel, trigger_name, template_name, coupon_id, provider_message_id, status, sent_at)
		 SELECT u.id::text, $2, $3, NULLIF($4,''), c.id, NULLIF($5,''), $6,
		        CASE WHEN $6 = 'SENT' THEN NOW() ELSE NULL END
		 FROM users u
		 LEFT JOIN coupons c ON UPPER(c.code) = NULLIF(UPPER($7),'')
		 WHERE u.email = $1
		 RETURNING id::text`,
		email, channel, strings.TrimSpace(message.TriggerName), message.TemplateName,
		message.ProviderMessageID, status, message.CouponCode).Scan(&id)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", ErrInvalidEmail
	}
	return id, err
}
