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
//
// Ownership is enforced here, at the database boundary: a personalised coupon
// (user_id set — every YV_20 voucher) resolves ONLY for its owner, so a
// leaked code fails identically to an unknown one on every other account.
// Guests can never redeem personalised coupons because an empty owner string
// casts to NULL, which never equals a real user id.
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
		   AND (c.user_id IS NULL OR c.user_id = NULLIF($2,'')::uuid)
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

const firstOrderReservationInterval = "30 minutes"

// redeemOrderPromotion records the promotion a paid order consumed. It runs
// inside the caller's payment transaction so the redemption commits atomically
// with the status flip, and relies purely on unique constraints for
// idempotency:
//   - coupon codes (personalised YV_20 vouchers, legacy welcome coupons) land
//     in coupon_redemptions where order_id UNIQUE absorbs verify/webhook
//     duplicates and concurrent retries;
//   - the automatic FIRST_ORDER_10 grant lands in user_promotion_redemptions
//     where UNIQUE (user_id, promotion_kind) allows exactly one per user ever.
//
// Neither path locks shared rows: every conflict target is scoped to this
// order or this user, so 10M+ users never serialise on one another.
func redeemOrderPromotion(ctx context.Context, tx pgx.Tx, orderID, userID, discountCode string, discountAmount float64) error {
	if discountCode == PromotionFirstOrder {
		if userID == "" {
			return nil // defensive: auto promotions are signed-in only
		}
		// The checkout that received the automatic price must own the
		// reservation. This rejects a second browser tab instead of charging
		// two "first" orders at the discounted amount.
		var reservedOrderID string
		err := tx.QueryRow(ctx,
			`DELETE FROM first_order_promotion_reservations
			  WHERE user_id = $1::uuid AND promotion_kind = $2 AND order_id = $3::uuid
			  RETURNING order_id::text`, userID, PromotionFirstOrder, orderID).
			Scan(&reservedOrderID)
		if errors.Is(err, pgx.ErrNoRows) {
			return ErrCouponInvalid
		}
		if err != nil {
			return err
		}
		_, err = tx.Exec(ctx,
			`INSERT INTO user_promotion_redemptions (user_id, promotion_kind, order_id, discount_amount)
			 VALUES ($1::uuid, $2, $3::uuid, $4)
			 ON CONFLICT (user_id, promotion_kind) DO NOTHING`,
			userID, PromotionFirstOrder, orderID, discountAmount)
		return err
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO coupon_redemptions (coupon_id, order_id, user_id, code_snapshot, discount_amount)
		 SELECT c.id, $1::uuid, NULLIF($2,'')::uuid, UPPER($3), $4
		 FROM coupons c WHERE UPPER(c.code) = UPPER($3)
		 ON CONFLICT (order_id) DO NOTHING`,
		orderID, userID, discountCode, discountAmount); err != nil {
		return err
	}
	_, err := tx.Exec(ctx,
		`UPDATE coupons SET uses = uses + 1
		 WHERE id = (SELECT coupon_id FROM coupon_redemptions WHERE order_id = $1::uuid)`,
		orderID)
	return err
}

// VerifyRazorpayPayment flips the order to AUTHORIZED and, in the same
// transaction, redeems its promotion on the first successful verification.
// Unique constraints on the redemption tables make retries and verify/webhook
// races no-ops; abandoned carts never burn anything because nothing is written
// at order creation time.
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
		if err := redeemOrderPromotion(ctx, tx, orderID, userID, discountCode, discountAmount); err != nil {
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
const recoveryDiscountPercent = 20.0
const firstOrderDiscountPercent = 10.0

// --- FIRST_ORDER_10 automatic promotion -------------------------------------

// firstOrderEligible reports whether a signed-in user may receive the
// automatic FIRST_ORDER_10 discount: the account must exist with a verified
// email, have NO paid order in its history, and never have been granted the
// promotion before. Eligibility is derived purely from this user's rows —
// there is no global "order #1" shortcut — and the reads take no locks so
// concurrent checkouts never serialise on shared state.
//
// The race window between this check and payment confirmation is closed by
// the UNIQUE (user_id, promotion_kind) constraint on user_promotion_redemptions,
// which lets exactly one payment win the grant.
func firstOrderEligible(ctx context.Context, querier dbQuerier, ownerID string) bool {
	if ownerID == "" {
		return false // guests never qualify: sign-in is required
	}
	var eligible bool
	err := querier.QueryRow(ctx,
		`SELECT NOT EXISTS (
	            SELECT 1 FROM orders o
	             WHERE o.user_id = $1::uuid
	               AND o.payment_status IN ('AUTHORIZED', 'CAPTURED'))
	        AND NOT EXISTS (
	            SELECT 1 FROM user_promotion_redemptions g
	             WHERE g.user_id = $1::uuid AND g.promotion_kind = $2)
		 FROM users u WHERE u.id = $1::uuid AND u.email_verified_at IS NOT NULL`,
		ownerID, PromotionFirstOrder).Scan(&eligible)
	if err != nil {
		return false // unknown or unverified user: silently skip the promotion
	}
	return eligible
}

// reserveFirstOrderPromotion grants the displayed FIRST_ORDER_10 price to one
// pending order only. The user row lock is scoped to that one account, and
// the primary key provides the durable cross-request guarantee. Reservations
// expire so an abandoned payment can never lock a customer out indefinitely.
func (store *PostgresStore) reserveFirstOrderPromotion(ctx context.Context, tx pgx.Tx, ownerID, orderID string) (bool, error) {
	if ownerID == "" {
		return false, nil
	}
	var userID string
	err := tx.QueryRow(ctx,
		`SELECT id::text FROM users
		  WHERE id = $1::uuid AND email_verified_at IS NOT NULL
		  FOR UPDATE`, ownerID).Scan(&userID)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}

	var alreadyUsed bool
	if err := tx.QueryRow(ctx,
		`SELECT EXISTS (
		     SELECT 1 FROM orders
		      WHERE user_id = $1::uuid AND payment_status IN ('AUTHORIZED', 'CAPTURED')
		   ) OR EXISTS (
		     SELECT 1 FROM user_promotion_redemptions
		      WHERE user_id = $1::uuid AND promotion_kind = $2
		   )`, userID, PromotionFirstOrder).Scan(&alreadyUsed); err != nil {
		return false, err
	}
	if alreadyUsed {
		return false, nil
	}
	if _, err := tx.Exec(ctx,
		`DELETE FROM first_order_promotion_reservations
		  WHERE user_id = $1::uuid AND promotion_kind = $2 AND expires_at <= NOW()`,
		userID, PromotionFirstOrder); err != nil {
		return false, err
	}
	var reserved string
	err = tx.QueryRow(ctx,
		`INSERT INTO first_order_promotion_reservations (user_id, promotion_kind, order_id, expires_at)
		 VALUES ($1::uuid, $2, $3::uuid, NOW() + $4::interval)
		 ON CONFLICT (user_id, promotion_kind) DO NOTHING
		 RETURNING order_id::text`, userID, PromotionFirstOrder, orderID,
		firstOrderReservationInterval).Scan(&reserved)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	return reserved == orderID, nil
}

// --- YV_20 service-recovery vouchers ----------------------------------------

func (store *PostgresStore) recoveryPromotionID(ctx context.Context) (string, error) {
	var promotionID string
	err := store.db.QueryRow(ctx,
		`INSERT INTO promotions (name, promotion_type, value, kind, is_active)
		 SELECT 'YV_20', 'PERCENTAGE', 20, 'SERVICE_RECOVERY', TRUE
		 WHERE NOT EXISTS (SELECT 1 FROM promotions WHERE name = 'YV_20')
		 RETURNING id::text`).Scan(&promotionID)
	if errors.Is(err, pgx.ErrNoRows) {
		err = store.db.QueryRow(ctx,
			`SELECT id::text FROM promotions WHERE name = 'YV_20' ORDER BY created_at LIMIT 1`).Scan(&promotionID)
	}
	return promotionID, err
}

// IssueRecoveryVoucher mints a brand-new one-time YV_20 voucher bound to the
// account behind `email`. One user, one use, 30-day expiry; redemption also
// requires that user's sign-in, so the code alone is worthless if leaked.
func (store *PostgresStore) IssueRecoveryVoucher(ctx context.Context, email string) (RecoveryVoucher, error) {
	ctx, cancel := boundedContext(ctx)
	defer cancel()
	email = strings.ToLower(strings.TrimSpace(email))
	if email == "" || !validEmail(email) {
		return RecoveryVoucher{}, ErrInvalidEmail
	}

	promotion, err := store.recoveryPromotionID(ctx)
	if err != nil {
		return RecoveryVoucher{}, err
	}
	for attempt := 0; attempt < 5; attempt++ {
		code, err := generateRecoveryCode()
		if err != nil {
			return RecoveryVoucher{}, err
		}
		var issued RecoveryVoucher
		err = store.db.QueryRow(ctx,
			`INSERT INTO coupons (promotion_id, user_id, code, max_uses, per_user_limit, expires_at, minimum_order_amount, is_active)
			 SELECT $1::uuid, u.id, $3, 1, 1, NOW() + interval '30 days', 0, TRUE
			   FROM users u WHERE LOWER(u.email) = $2
			 RETURNING code, expires_at`, promotion, email, code).
			Scan(&issued.Code, &issued.ExpiresAt)
		if err == nil {
			issued.DiscountPercent = recoveryDiscountPercent
			return issued, nil
		}
		if errors.Is(err, pgx.ErrNoRows) {
			return RecoveryVoucher{}, ErrUserNotFound
		}
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			continue // astronomically unlikely code collision — draw again
		}
		return RecoveryVoucher{}, err
	}
	return RecoveryVoucher{}, errors.New("could not allocate a unique recovery voucher code")
}

// RevokeRecoveryVoucher deactivates a voucher that has not been redeemed yet.
// Revoking an unknown code fails without revealing whether it ever existed;
// revoking a redeemed one fails so support history stays truthful.
func (store *PostgresStore) RevokeRecoveryVoucher(ctx context.Context, email, code string) error {
	ctx, cancel := boundedContext(ctx)
	defer cancel()
	email = strings.ToLower(strings.TrimSpace(email))
	code = NormalizeDiscountCode(code)
	if email == "" || !validEmail(email) || code == "" {
		return ErrCouponInvalid
	}
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	var couponID string
	var redeemed bool
	err = tx.QueryRow(ctx,
		`SELECT c.id::text, EXISTS (SELECT 1 FROM coupon_redemptions r WHERE r.coupon_id = c.id)
		 FROM coupons c JOIN users u ON u.id = c.user_id
		 WHERE UPPER(c.code) = $1 AND LOWER(u.email) = $2
		 FOR UPDATE OF c`, code, email).Scan(&couponID, &redeemed)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrCouponInvalid
	}
	if err != nil {
		return err
	}
	if redeemed {
		return ErrVoucherRedeemed
	}
	if _, err := tx.Exec(ctx, `UPDATE coupons SET is_active = FALSE WHERE id = $1::uuid`, couponID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

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
		 SELECT u.id, $2, $3, NULLIF($4,''), c.id, NULLIF($5,''), $6,
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
