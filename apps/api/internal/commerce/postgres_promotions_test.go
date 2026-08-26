package commerce

import (
	"context"
	"errors"
	"sync"
	"testing"
)

// Integration tests for the two account-bound promotion programmes (migration
// 000009). They run only when TEST_DATABASE_URL points at a disposable
// database — never production credentials or data (see postgres_store_test.go).
//
// Covered guarantees:
//   - FIRST_ORDER_10 applies automatically to a signed-in, verified user's
//     first successfully paid order and is derived from that user's own
//     paid-order history (never a global row count);
//   - any prior paid order disqualifies the promotion;
//   - YV_20 vouchers are bound to their owner: a code alone is worthless on
//     every other account, including guest checkouts;
//   - vouchers can be revoked until redeemed;
//   - retries, duplicate Razorpay webhooks, and concurrent verifications
//     redeem exactly once via database uniqueness constraints.

const (
	firstOrderUser  = "aaaaaaa1-0000-4000-8000-000000000001"
	rivalUser       = "bbbbbbb2-0000-4000-8000-000000000002"
	recoveryOwner   = "ccccccc3-0000-4000-8000-000000000003"
	unverifiedUser  = "ddddddd4-0000-4000-8000-000000000004"
	concurrencyUser = "eeeeeee5-0000-4000-8000-000000000005"
	reservationUser = "99999999-0000-4000-8000-000000000009"
	// Each voucher scenario uses its own accounts: the disposable database
	// persists users across tests, so ids must map to exactly one address.
	leakOwnerID    = "aaaabbb1-0000-4000-8000-00000000000a"
	leakRivalID    = "bbbbaaa2-0000-4000-8000-00000000000b"
	revokeOwnerID  = "cccceee3-0000-4000-8000-00000000000c"
	redeemUserID   = "ddddfff4-0000-4000-8000-00000000000d"
	duplicateOwner = "eeeeaaa5-0000-4000-8000-00000000000e"
	paidOther      = "ffffff06-0000-4000-8000-000000000006"
)

func checkoutInput(cartID string) CreateOrderInput {
	return CreateOrderInput{
		CartID: cartID, CustomerEmail: "buyer@example.com",
		ShippingAddress: Address{RecipientName: "Buyer", Line1: "9 Promotion Way", City: "Pune", StateRegion: "MH", PostalCode: "411001"},
	}
}

// paidOrder drives an order through verification so its owner has paid history.
func paidOrder(t *testing.T, store *PostgresStore, ownerID, razorpayOrderID string) Order {
	t.Helper()
	cart, err := store.CreateCartForUser(ownerID)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(ownerID, cart.ID, "p1", "v1", 1); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	order, replayed, err := store.CreateOrderForUser(ownerID, checkoutInput(cart.ID), "")
	if err != nil || replayed {
		t.Fatalf("CreateOrderForUser() replayed=%v error=%v", replayed, err)
	}
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, razorpayOrderID); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	if _, err := store.VerifyRazorpayPayment(razorpayOrderID, "pay_"+razorpayOrderID); err != nil {
		t.Fatalf("VerifyRazorpayPayment() error = %v", err)
	}
	return order
}

func firstOrderGrants(t *testing.T, store *PostgresStore, userID string) int {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	var grants int
	if err := store.db.QueryRow(ctx,
		`SELECT COUNT(*) FROM user_promotion_redemptions WHERE user_id=$1::uuid`, userID).Scan(&grants); err != nil {
		t.Fatal(err)
	}
	return grants
}

func TestPostgresFirstOrderPromotionAppliesAutomaticallyOnce(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, firstOrderUser, "first.order@example.com")

	cart, err := store.CreateCartForUser(firstOrderUser)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	// Two units of the 1200 variant -> 2400 subtotal; 10% = 240.
	if _, err := store.AddCartItemForUser(firstOrderUser, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	order, replayed, err := store.CreateOrderForUser(firstOrderUser, checkoutInput(cart.ID), "")
	if err != nil || replayed {
		t.Fatalf("CreateOrderForUser() replayed=%v error=%v", replayed, err)
	}
	if order.DiscountAmount != 240 || order.DiscountCode != PromotionFirstOrder {
		t.Fatalf("first order discount = %v (%q), want 240 (%s)", order.DiscountAmount, order.DiscountCode, PromotionFirstOrder)
	}
	// 2400 - 240 = 2160 crosses the free-shipping threshold, so shipping is 0.
	if order.TotalAmount != 2160 || order.ShippingAmount != 0 {
		t.Fatalf("total/shipping = %v/%v, want 2160/0", order.TotalAmount, order.ShippingAmount)
	}

	// Payment confirmation records exactly one grant; duplicate verifications
	// and a captured webhook afterwards must not add another.
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_first_10"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	for attempt := 0; attempt < 3; attempt++ {
		if _, err := store.VerifyRazorpayPayment("order_first_10", "pay_first_10"); err != nil {
			t.Fatalf("VerifyRazorpayPayment() attempt %d error = %v", attempt+1, err)
		}
	}
	if _, err := store.RecordRazorpayPayment("order_first_10", "", "captured"); err != nil {
		t.Fatalf("RecordRazorpayPayment(captured) error = %v", err)
	}
	if grants := firstOrderGrants(t, store, firstOrderUser); grants != 1 {
		t.Fatalf("grants after duplicates = %d, want exactly 1", grants)
	}

	// A second checkout gets nothing: the account now has paid history.
	secondCart, err := store.CreateCartForUser(firstOrderUser)
	if err != nil {
		t.Fatalf("second CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(firstOrderUser, secondCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("second AddCartItemForUser() error = %v", err)
	}
	second, _, err := store.CreateOrderForUser(firstOrderUser, checkoutInput(secondCart.ID), "")
	if err != nil {
		t.Fatalf("second CreateOrderForUser() error = %v", err)
	}
	if second.DiscountAmount != 0 || second.DiscountCode != "" {
		t.Fatalf("second order discount = %v (%q), want none once a paid order exists", second.DiscountAmount, second.DiscountCode)
	}
}

func TestPostgresFirstOrderRequiresVerificationAndIgnoresGlobalRowCounts(t *testing.T) {
	store := newTestPostgresStore(t)

	// Another account's paid orders exist in this database (global rows > 0),
	// but eligibility is evaluated per user, not from a global order id.
	seedVerifiedUser(t, store.db, paidOther, "paid.other@example.com")
	paidOrder(t, store, paidOther, "order_paid_other")

	// An unverified account never qualifies, even with zero paid history.
	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	if _, err := store.db.Exec(ctx,
		`INSERT INTO users (id, email) VALUES ($1::uuid, $2) ON CONFLICT (id) DO NOTHING`,
		unverifiedUser, "unverified@example.com"); err != nil {
		t.Fatal(err)
	}
	cart, err := store.CreateCartForUser(unverifiedUser)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(unverifiedUser, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	order, _, err := store.CreateOrderForUser(unverifiedUser, checkoutInput(cart.ID), "")
	if err != nil {
		t.Fatalf("CreateOrderForUser() error = %v", err)
	}
	if order.DiscountAmount != 0 || order.DiscountCode != "" {
		t.Fatalf("unverified discount = %v (%q), want none", order.DiscountAmount, order.DiscountCode)
	}
}

func TestPostgresRecoveryVoucherIsBoundToItsOwner(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, recoveryOwner, "recovery.owner@example.com")

	voucher, err := store.IssueRecoveryVoucher(context.Background(), "Recovery.Owner@Example.com")
	if err != nil {
		t.Fatalf("IssueRecoveryVoucher() error = %v", err)
	}
	if voucher.DiscountPercent != 20 || len(voucher.Code) != len(recoveryCodePrefix)+8 {
		t.Fatalf("voucher = %#v, want 20%% off with an 8-character code", voucher)
	}
	if voucher.ExpiresAt.IsZero() {
		t.Fatal("voucher expiry missing")
	}

	seedVerifiedUser(t, store.db, rivalUser, "rival@example.com")

	// The owner redeems it on their own signed-in account.
	ownerCart, err := store.CreateCartForUser(recoveryOwner)
	if err != nil {
		t.Fatalf("owner CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(recoveryOwner, ownerCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("owner AddCartItemForUser() error = %v", err)
	}
	input := checkoutInput(ownerCart.ID)
	input.CustomerEmail = "recovery.owner@example.com"
	input.DiscountCode = voucher.Code
	order, _, err := store.CreateOrderForUser(recoveryOwner, input, "")
	if err != nil {
		t.Fatalf("owner redemption error = %v", err)
	}
	if order.DiscountAmount != 480 || order.DiscountCode != voucher.Code {
		t.Fatalf("owner discount = %v (%q), want 480 with their voucher", order.DiscountAmount, order.DiscountCode)
	}
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_voucher_owner"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	if _, err := store.VerifyRazorpayPayment("order_voucher_owner", "pay_voucher_owner"); err != nil {
		t.Fatalf("VerifyRazorpayPayment() error = %v", err)
	}

	var uses int
	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	if err := store.db.QueryRow(ctx,
		`SELECT uses FROM coupons WHERE UPPER(code) = UPPER($1)`, voucher.Code).Scan(&uses); err != nil {
		t.Fatal(err)
	}
	if uses != 1 {
		t.Fatalf("voucher uses = %d, want 1 after owner redemption", uses)
	}
}

func TestPostgresLeakedVoucherFailsEveryOtherAccount(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, leakOwnerID, "leak.owner@example.com")
	voucher, err := store.IssueRecoveryVoucher(context.Background(), "leak.owner@example.com")
	if err != nil {
		t.Fatalf("IssueRecoveryVoucher() error = %v", err)
	}

	seedVerifiedUser(t, store.db, leakRivalID, "leak.rival@example.com")
	rivalCart, err := store.CreateCartForUser(leakRivalID)
	if err != nil {
		t.Fatalf("rival CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(leakRivalID, rivalCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("rival AddCartItemForUser() error = %v", err)
	}

	// Another signed-in account presenting the stolen code fails closed, and
	// indistinguishably from an unknown code so existence cannot be probed.
	leaked := checkoutInput(rivalCart.ID)
	leaked.CustomerEmail = "leak.rival@example.com"
	leaked.DiscountCode = voucher.Code
	if _, _, err := store.CreateOrderForUser(leakRivalID, leaked, ""); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("stolen voucher error = %v, want ErrCouponInvalid", err)
	}
	if _, _, err := store.CreateOrderForUser(leakRivalID, func() CreateOrderInput {
		input := leaked
		input.DiscountCode = "YV20-NOTREAL"
		return input
	}(), ""); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("unknown voucher error = %v, want ErrCouponInvalid", err)
	}

	// Guests can never redeem personalised codes either.
	guest := leaked
	guest.CartID = filledGuestCartID(t, store)
	if _, _, err := store.CreateOrder(guest, ""); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("guest voucher error = %v, want ErrCouponInvalid", err)
	}

	// The failed attempts consumed nothing: the voucher still works for its owner.
	ownerCart, err := store.CreateCartForUser(leakOwnerID)
	if err != nil {
		t.Fatalf("owner CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(leakOwnerID, ownerCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("owner AddCartItemForUser() error = %v", err)
	}
	ownerInput := checkoutInput(ownerCart.ID)
	ownerInput.CustomerEmail = "leak.owner@example.com"
	ownerInput.DiscountCode = voucher.Code
	if _, _, err := store.CreateOrderForUser(leakOwnerID, ownerInput, ""); err != nil {
		t.Fatalf("owner redemption after leaks error = %v", err)
	}
}

func filledGuestCartID(t *testing.T, store *PostgresStore) string {
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

func TestPostgresRecoveryVoucherRevocationBeforeRedemption(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, revokeOwnerID, "revoke.me@example.com")

	voucher, err := store.IssueRecoveryVoucher(context.Background(), "revoke.me@example.com")
	if err != nil {
		t.Fatalf("IssueRecoveryVoucher() error = %v", err)
	}

	// Revoking an unknown or foreign code fails without leaking existence.
	if err := store.RevokeRecoveryVoucher(context.Background(), "revoke.me@example.com", "YV20-MISSING"); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("revoke unknown error = %v, want ErrCouponInvalid", err)
	}
	if err := store.RevokeRecoveryVoucher(context.Background(), "someone-else@example.com", voucher.Code); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("revoke foreign error = %v, want ErrCouponInvalid", err)
	}

	if err := store.RevokeRecoveryVoucher(context.Background(), "revoke.me@example.com", voucher.Code); err != nil {
		t.Fatalf("RevokeRecoveryVoucher() error = %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	var active bool
	if err := store.db.QueryRow(ctx,
		`SELECT is_active FROM coupons WHERE UPPER(code) = UPPER($1)`, voucher.Code).Scan(&active); err != nil {
		t.Fatal(err)
	}
	if active {
		t.Fatal("revoked voucher still active")
	}

	// Revoked vouchers no longer redeem, even for their owner.
	cart, err := store.CreateCartForUser(revokeOwnerID)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(revokeOwnerID, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	input := checkoutInput(cart.ID)
	input.CustomerEmail = "revoke.me@example.com"
	input.DiscountCode = voucher.Code
	if _, _, err := store.CreateOrderForUser(revokeOwnerID, input, ""); !errors.Is(err, ErrCouponInvalid) {
		t.Fatalf("revoked redemption error = %v, want ErrCouponInvalid", err)
	}

	// A redeemed voucher can no longer be revoked — history stays truthful.
	seedVerifiedUser(t, store.db, redeemUserID, "redeemed@example.com")
	live, err := store.IssueRecoveryVoucher(context.Background(), "redeemed@example.com")
	if err != nil {
		t.Fatalf("IssueRecoveryVoucher() error = %v", err)
	}
	redemptionCart, err := store.CreateCartForUser(redeemUserID)
	if err != nil {
		t.Fatalf("rival CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(redeemUserID, redemptionCart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("rival AddCartItemForUser() error = %v", err)
	}
	redeemInput := checkoutInput(redemptionCart.ID)
	redeemInput.CustomerEmail = "redeemed@example.com"
	redeemInput.DiscountCode = live.Code
	order, _, err := store.CreateOrderForUser(redeemUserID, redeemInput, "")
	if err != nil {
		t.Fatalf("redemption error = %v", err)
	}
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_redeemed_voucher"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}
	if _, err := store.VerifyRazorpayPayment("order_redeemed_voucher", "pay_redeemed_voucher"); err != nil {
		t.Fatalf("VerifyRazorpayPayment() error = %v", err)
	}
	if err := store.RevokeRecoveryVoucher(context.Background(), "redeemed@example.com", live.Code); !errors.Is(err, ErrVoucherRedeemed) {
		t.Fatalf("revoke redeemed error = %v, want ErrVoucherRedeemed", err)
	}
}

func TestPostgresWebhookAndVerifyDuplicatesRedeemOnce(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, duplicateOwner, "dupes@example.com")

	voucher, err := store.IssueRecoveryVoucher(context.Background(), "dupes@example.com")
	if err != nil {
		t.Fatalf("IssueRecoveryVoucher() error = %v", err)
	}
	cart, err := store.CreateCartForUser(duplicateOwner)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(duplicateOwner, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	input := checkoutInput(cart.ID)
	input.CustomerEmail = "dupes@example.com"
	input.DiscountCode = voucher.Code
	order, _, err := store.CreateOrderForUser(duplicateOwner, input, "")
	if err != nil {
		t.Fatalf("CreateOrderForUser() error = %v", err)
	}
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_dupe_storm"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}

	// Client verification races the webhook: verify fires repeatedly while
	// duplicate capture events land before and after.
	for range 3 {
		if _, err := store.VerifyRazorpayPayment("order_dupe_storm", "pay_dupe_storm"); err != nil {
			t.Fatalf("VerifyRazorpayPayment() error = %v", err)
		}
	}
	for range 3 {
		if _, err := store.RecordRazorpayPayment("order_dupe_storm", "", "captured"); err != nil {
			t.Fatalf("RecordRazorpayPayment(captured) error = %v", err)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), postgresTestTimeout)
	defer cancel()
	var redemptions, grants, uses int
	if err := store.db.QueryRow(ctx,
		`SELECT COUNT(*) FROM coupon_redemptions WHERE coupon_id = (SELECT id FROM coupons WHERE UPPER(code)=UPPER($1))`,
		voucher.Code).Scan(&redemptions); err != nil {
		t.Fatal(err)
	}
	if err := store.db.QueryRow(ctx,
		`SELECT COUNT(*) FROM user_promotion_redemptions`).Scan(&grants); err != nil {
		t.Fatal(err)
	}
	if err := store.db.QueryRow(ctx,
		`SELECT uses FROM coupons WHERE UPPER(code)=UPPER($1)`, voucher.Code).Scan(&uses); err != nil {
		t.Fatal(err)
	}
	if redemptions != 1 || grants != 0 || uses != 1 {
		t.Fatalf("duplicate storm produced redemptions=%d grants=%d uses=%d, want 1/0/1", redemptions, grants, uses)
	}
}

func TestPostgresConcurrentVerificationsRedeemExactlyOnce(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, concurrencyUser, "racer@example.com")

	// (a) Many concurrent verifications of ONE payment: unique constraints
	// collapse them into a single redemption.
	cart, err := store.CreateCartForUser(concurrencyUser)
	if err != nil {
		t.Fatalf("CreateCartForUser() error = %v", err)
	}
	if _, err := store.AddCartItemForUser(concurrencyUser, cart.ID, "p1", "v1", 2); err != nil {
		t.Fatalf("AddCartItemForUser() error = %v", err)
	}
	first, _, err := store.CreateOrderForUser(concurrencyUser, checkoutInput(cart.ID), "")
	if err != nil {
		t.Fatalf("first CreateOrderForUser() error = %v", err)
	}
	if first.DiscountAmount != 240 || first.DiscountCode != PromotionFirstOrder {
		t.Fatalf("first order discount = %v (%q), want automatic FIRST_ORDER_10", first.DiscountAmount, first.DiscountCode)
	}
	if _, err := store.AttachRazorpayOrder(first.OrderNumber, "order_race_one"); err != nil {
		t.Fatalf("AttachRazorpayOrder() error = %v", err)
	}

	const racers = 6
	var wg sync.WaitGroup
	errCh := make(chan error, racers*2)
	for range racers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := store.VerifyRazorpayPayment("order_race_one", "pay_race_one"); err != nil {
				errCh <- err
			}
			if _, err := store.RecordRazorpayPayment("order_race_one", "", "captured"); err != nil {
				errCh <- err
			}
		}()
	}
	wg.Wait()
	close(errCh)
	for err := range errCh {
		t.Fatalf("concurrent confirmation error = %v", err)
	}
	if grants := firstOrderGrants(t, store, concurrencyUser); grants != 1 {
		t.Fatalf("concurrent verifications produced %d grants, want exactly 1", grants)
	}

	// (b) Two DIFFERENT orders of the same user confirm simultaneously (two
	// tabs): both payments succeed but only one may hold the grant.
	carts := make([]string, 2)
	razorpayIDs := []string{"order_race_a", "order_race_b"}
	for i := range carts {
		c, err := store.CreateCartForUser(concurrencyUser)
		if err != nil {
			t.Fatalf("race cart %d error = %v", i, err)
		}
		if _, err := store.AddCartItemForUser(concurrencyUser, c.ID, "p1", "v1", 1); err != nil {
			t.Fatalf("race item %d error = %v", i, err)
		}
		order, _, err := store.CreateOrderForUser(concurrencyUser, checkoutInput(c.ID), "")
		if err != nil {
			t.Fatalf("race order %d error = %v", i, err)
		}
		if _, err := store.AttachRazorpayOrder(order.OrderNumber, razorpayIDs[i]); err != nil {
			t.Fatalf("AttachRazorpayOrder() race order %d error = %v", i, err)
		}
		carts[i] = order.ID
	}
	results := make([]error, racers)
	for i := range racers {
		wg.Add(1)
		go func(slot int) {
			defer wg.Done()
			target := razorpayIDs[slot%2]
			_, results[slot] = store.VerifyRazorpayPayment(target, "pay_"+target)
		}(i)
	}
	wg.Wait()
	for slot, err := range results {
		if err != nil {
			t.Fatalf("racing verify %d error = %v", slot, err)
		}
	}
	if grants := firstOrderGrants(t, store, concurrencyUser); grants != 1 {
		t.Fatalf("two-order race produced %d grants, want exactly 1", grants)
	}
}

// A new user can open two checkouts, but only the first pending order gets
// the automatic price. This prevents two Razorpay orders from ever being
// created at 10% off for the same account.
func TestPostgresFirstOrderReservationAllowsOnlyOnePendingDiscount(t *testing.T) {
	store := newTestPostgresStore(t)
	seedVerifiedUser(t, store.db, reservationUser, "reservation@example.com")

	create := func() Order {
		cart, err := store.CreateCartForUser(reservationUser)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := store.AddCartItemForUser(reservationUser, cart.ID, "p1", "v1", 1); err != nil {
			t.Fatal(err)
		}
		order, _, err := store.CreateOrderForUser(reservationUser, checkoutInput(cart.ID), "")
		if err != nil {
			t.Fatal(err)
		}
		return order
	}

	first := create()
	second := create()
	if first.DiscountCode != PromotionFirstOrder || first.DiscountAmount != 120 {
		t.Fatalf("first order = %q / %v, want FIRST_ORDER_10 / 120", first.DiscountCode, first.DiscountAmount)
	}
	if second.DiscountCode != "" || second.DiscountAmount != 0 {
		t.Fatalf("second pending order = %q / %v, want no automatic discount", second.DiscountCode, second.DiscountAmount)
	}
}
