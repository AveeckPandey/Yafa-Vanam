package commerce

import (
	"errors"
	"math"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var ErrRefundNotSupported = errors.New("only captured payments can be refunded")
var ErrRefundAmountInvalid = errors.New("refund amount exceeds the remaining captured amount")
var ErrRefundNotFound = errors.New("refund not found")
var ErrRefundIdempotencyConflict = errors.New("refund idempotency key was already used for different details")

type Refund struct {
	ID                string     `json:"id"`
	OrderNumber       string     `json:"order_number"`
	ProviderPaymentID string     `json:"provider_payment_id"`
	ProviderRefundID  string     `json:"provider_refund_id,omitempty"`
	IdempotencyKey    string     `json:"-"`
	Receipt           string     `json:"receipt"`
	AmountPaise       int64      `json:"amount_paise"`
	Currency          string     `json:"currency"`
	Reason            string     `json:"reason"`
	Status            string     `json:"status"`
	CreatedAt         time.Time  `json:"created_at"`
	ProcessedAt       *time.Time `json:"processed_at,omitempty"`
}

type RefundStore interface {
	PrepareRefund(orderNumber string, amountPaise int64, reason, idempotencyKey, receipt string) (Refund, bool, error)
	CompleteRefund(idempotencyKey, providerRefundID, status string) (Refund, error)
	RecordRefundStatus(providerRefundID, receipt, status string) (Refund, error)
}

func normalizeRefundStatus(status string) string {
	switch strings.ToLower(strings.TrimSpace(status)) {
	case "processed":
		return "PROCESSED"
	case "failed":
		return "FAILED"
	default:
		return "PENDING"
	}
}

func (store *Store) PrepareRefund(orderNumber string, amountPaise int64, reason, idempotencyKey, receipt string) (Refund, bool, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	if existing, ok := store.refunds[idempotencyKey]; ok {
		if existing.OrderNumber != orderNumber || (amountPaise > 0 && existing.AmountPaise != amountPaise) {
			return Refund{}, false, ErrRefundIdempotencyConflict
		}
		return *existing, true, nil
	}
	order := store.orders[orderNumber]
	if order == nil {
		return Refund{}, false, ErrOrderNotFound
	}
	if order.PaymentStatus != "CAPTURED" || order.RazorpayPaymentID == "" {
		return Refund{}, false, ErrRefundNotSupported
	}
	totalPaise := int64(math.Round(order.TotalAmount * 100))
	var alreadyReserved int64
	for _, item := range store.refunds {
		if item.OrderNumber == orderNumber && item.Status != "FAILED" {
			alreadyReserved += item.AmountPaise
		}
	}
	remaining := totalPaise - alreadyReserved
	if amountPaise == 0 {
		amountPaise = remaining
	}
	if amountPaise <= 0 || amountPaise > remaining {
		return Refund{}, false, ErrRefundAmountInvalid
	}
	now := store.now().UTC()
	refund := &Refund{ID: randomID("rfd_", 12), OrderNumber: orderNumber, ProviderPaymentID: order.RazorpayPaymentID, IdempotencyKey: idempotencyKey, Receipt: receipt, AmountPaise: amountPaise, Currency: order.Currency, Reason: strings.TrimSpace(reason), Status: "PENDING", CreatedAt: now}
	store.refunds[idempotencyKey] = refund
	return *refund, false, nil
}

func (store *Store) CompleteRefund(idempotencyKey, providerRefundID, status string) (Refund, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	refund := store.refunds[idempotencyKey]
	if refund == nil {
		return Refund{}, ErrRefundNotFound
	}
	return store.completeRefundLocked(refund, providerRefundID, status)
}

func (store *Store) RecordRefundStatus(providerRefundID, receipt, status string) (Refund, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	for _, refund := range store.refunds {
		if refund.ProviderRefundID == providerRefundID || (refund.ProviderRefundID == "" && receipt != "" && refund.Receipt == receipt) {
			return store.completeRefundLocked(refund, providerRefundID, status)
		}
	}
	return Refund{}, ErrRefundNotFound
}

func (store *Store) completeRefundLocked(refund *Refund, providerRefundID, status string) (Refund, error) {
	if refund.ProviderRefundID != "" && providerRefundID != "" && refund.ProviderRefundID != providerRefundID {
		return Refund{}, ErrRefundIdempotencyConflict
	}
	if providerRefundID != "" {
		refund.ProviderRefundID = providerRefundID
	}
	refund.Status = normalizeRefundStatus(status)
	if refund.Status == "PROCESSED" && refund.ProcessedAt == nil {
		now := store.now().UTC()
		refund.ProcessedAt = &now
		order := store.orders[refund.OrderNumber]
		if order != nil {
			var processed int64
			for _, item := range store.refunds {
				if item.OrderNumber == refund.OrderNumber && item.Status == "PROCESSED" {
					processed += item.AmountPaise
				}
			}
			if processed >= int64(math.Round(order.TotalAmount*100)) {
				order.PaymentStatus, order.OrderStatus = "REFUNDED", "REFUNDED"
			} else {
				order.PaymentStatus = "PARTIALLY_REFUNDED"
			}
		}
	}
	return *refund, nil
}

type refundRowScanner interface {
	Scan(dest ...any) error
}

func scanRefund(row refundRowScanner) (Refund, error) {
	var refund Refund
	err := row.Scan(&refund.ID, &refund.OrderNumber, &refund.ProviderPaymentID, &refund.ProviderRefundID, &refund.IdempotencyKey, &refund.Receipt, &refund.AmountPaise, &refund.Currency, &refund.Reason, &refund.Status, &refund.CreatedAt, &refund.ProcessedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, ErrRefundNotFound
	}
	return refund, err
}

const refundReturningColumns = `r.id::text, o.order_number, p.provider_payment_id, COALESCE(r.provider_refund_id,''), r.idempotency_key, r.receipt, r.amount_paise, r.currency, r.reason, r.status, r.created_at, r.processed_at`

func (store *PostgresStore) PrepareRefund(orderNumber string, amountPaise int64, reason, idempotencyKey, receipt string) (Refund, bool, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Refund{}, false, err
	}
	defer tx.Rollback(ctx)
	if existing, err := scanRefund(tx.QueryRow(ctx, `SELECT `+refundReturningColumns+` FROM refunds r JOIN orders o ON o.id=r.order_id JOIN payments p ON p.id=r.payment_id WHERE r.idempotency_key=$1`, idempotencyKey)); err == nil {
		if existing.OrderNumber != orderNumber || (amountPaise > 0 && existing.AmountPaise != amountPaise) {
			return Refund{}, false, ErrRefundIdempotencyConflict
		}
		return existing, true, nil
	} else if !errors.Is(err, ErrRefundNotFound) {
		return Refund{}, false, err
	}
	var orderID, paymentID, providerPaymentID, paymentStatus, currency string
	var totalPaise int64
	err = tx.QueryRow(ctx, `SELECT o.id::text, p.id::text, COALESCE(p.provider_payment_id,''), o.payment_status, (o.total_amount*100)::bigint, o.currency FROM orders o JOIN payments p ON p.order_id=o.id AND p.provider='RAZORPAY' WHERE o.order_number=$1 FOR UPDATE OF o`, orderNumber).Scan(&orderID, &paymentID, &providerPaymentID, &paymentStatus, &totalPaise, &currency)
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, false, ErrOrderNotFound
	}
	if err != nil {
		return Refund{}, false, err
	}
	if paymentStatus != "CAPTURED" || providerPaymentID == "" {
		return Refund{}, false, ErrRefundNotSupported
	}
	var reserved int64
	if err := tx.QueryRow(ctx, `SELECT COALESCE(SUM(amount_paise),0) FROM refunds WHERE order_id=$1::uuid AND status IN ('PENDING','PROCESSED')`, orderID).Scan(&reserved); err != nil {
		return Refund{}, false, err
	}
	remaining := totalPaise - reserved
	if amountPaise == 0 {
		amountPaise = remaining
	}
	if amountPaise <= 0 || amountPaise > remaining {
		return Refund{}, false, ErrRefundAmountInvalid
	}
	refund, err := scanRefund(tx.QueryRow(ctx, `INSERT INTO refunds (order_id, payment_id, idempotency_key, receipt, amount_paise, currency, reason) VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7) RETURNING id::text, $8, $9, '', idempotency_key, receipt, amount_paise, currency, reason, status, created_at, processed_at`, orderID, paymentID, idempotencyKey, receipt, amountPaise, currency, strings.TrimSpace(reason), orderNumber, providerPaymentID))
	if err != nil {
		return Refund{}, false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return Refund{}, false, err
	}
	return refund, false, nil
}

func (store *PostgresStore) CompleteRefund(idempotencyKey, providerRefundID, status string) (Refund, error) {
	return store.updateRefund("r.idempotency_key", idempotencyKey, providerRefundID, status)
}

func (store *PostgresStore) RecordRefundStatus(providerRefundID, receipt, status string) (Refund, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	var idempotencyKey string
	err := store.db.QueryRow(ctx, `SELECT idempotency_key FROM refunds WHERE provider_refund_id=$1 OR (provider_refund_id IS NULL AND receipt=$2)`, providerRefundID, receipt).Scan(&idempotencyKey)
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, ErrRefundNotFound
	}
	if err != nil {
		return Refund{}, err
	}
	return store.CompleteRefund(idempotencyKey, providerRefundID, status)
}

func (store *PostgresStore) updateRefund(column, value, providerRefundID, status string) (Refund, error) {
	ctx, cancel := store.ctx()
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return Refund{}, err
	}
	defer tx.Rollback(ctx)
	var refundID, currentProviderID string
	err = tx.QueryRow(ctx, `SELECT r.id::text, COALESCE(r.provider_refund_id,'') FROM refunds r WHERE `+column+`=$1 FOR UPDATE`, value).Scan(&refundID, &currentProviderID)
	if errors.Is(err, pgx.ErrNoRows) {
		return Refund{}, ErrRefundNotFound
	}
	if err != nil {
		return Refund{}, err
	}
	if currentProviderID != "" && providerRefundID != "" && currentProviderID != providerRefundID {
		return Refund{}, ErrRefundIdempotencyConflict
	}
	normalized := normalizeRefundStatus(status)
	refund, err := scanRefund(tx.QueryRow(ctx, `UPDATE refunds r SET provider_refund_id=COALESCE(NULLIF($2,''),provider_refund_id), status=$3, processed_at=CASE WHEN $3='PROCESSED' THEN COALESCE(processed_at,NOW()) ELSE processed_at END, updated_at=NOW() FROM orders o, payments p WHERE r.id=$1::uuid AND o.id=r.order_id AND p.id=r.payment_id RETURNING `+refundReturningColumns, refundID, providerRefundID, normalized))
	if err != nil {
		return Refund{}, err
	}
	if normalized == "PROCESSED" {
		if _, err := tx.Exec(ctx, `UPDATE orders o SET payment_status=CASE WHEN totals.refunded >= (o.total_amount*100)::bigint THEN 'REFUNDED' ELSE 'PARTIALLY_REFUNDED' END, order_status=CASE WHEN totals.refunded >= (o.total_amount*100)::bigint THEN 'REFUNDED' ELSE order_status END, updated_at=NOW() FROM (SELECT order_id, SUM(amount_paise) refunded FROM refunds WHERE order_id=(SELECT order_id FROM refunds WHERE id=$1::uuid) AND status='PROCESSED' GROUP BY order_id) totals WHERE o.id=totals.order_id`, refundID); err != nil {
			return Refund{}, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return Refund{}, err
	}
	return refund, nil
}
