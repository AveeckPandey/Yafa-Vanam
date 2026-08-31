package commerce

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

const inventoryAlertBatchSize = 10

// InventoryAlert is the durable message contract between the commerce API and
// the AWS low-stock Lambda.
type InventoryAlert struct {
	ID                string    `json:"event_id"`
	VariantID         string    `json:"variant_id"`
	AvailableQuantity int       `json:"available_quantity"`
	LowStockThreshold int       `json:"low_stock_threshold"`
	InventoryVersion  int64     `json:"inventory_version"`
	CreatedAt         time.Time `json:"created_at"`
}

type inventoryAlertOutbox interface {
	claimInventoryAlerts(context.Context, int) ([]InventoryAlert, error)
	completeInventoryAlert(context.Context, string) error
	failInventoryAlert(context.Context, string, string) error
}

type inventoryAlertQueue interface {
	SendMessage(context.Context, *sqs.SendMessageInput, ...func(*sqs.Options)) (*sqs.SendMessageOutput, error)
}

func (store *PostgresStore) claimInventoryAlerts(ctx context.Context, limit int) ([]InventoryAlert, error) {
	if limit <= 0 || limit > 100 {
		limit = inventoryAlertBatchSize
	}
	rows, err := store.db.Query(ctx,
		`WITH candidates AS (
			 SELECT id
			 FROM inventory_alert_outbox
			 WHERE status='PENDING'
			    OR (status='PROCESSING' AND locked_at < NOW() - INTERVAL '5 minutes')
			 ORDER BY created_at, id
			 FOR UPDATE SKIP LOCKED
			 LIMIT $1
		 )
		 UPDATE inventory_alert_outbox alert
		 SET status='PROCESSING', attempts=alert.attempts+1, locked_at=NOW(), last_error=NULL
		 FROM candidates
		 WHERE alert.id=candidates.id
		 RETURNING alert.id::text, alert.variant_id, alert.available_quantity,
		           alert.low_stock_threshold, alert.inventory_version, alert.created_at`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	alerts := make([]InventoryAlert, 0, limit)
	for rows.Next() {
		var alert InventoryAlert
		if err := rows.Scan(&alert.ID, &alert.VariantID, &alert.AvailableQuantity,
			&alert.LowStockThreshold, &alert.InventoryVersion, &alert.CreatedAt); err != nil {
			return nil, err
		}
		alerts = append(alerts, alert)
	}
	return alerts, rows.Err()
}

func (store *PostgresStore) completeInventoryAlert(ctx context.Context, id string) error {
	_, err := store.db.Exec(ctx,
		`UPDATE inventory_alert_outbox
		 SET status='SENT', sent_at=NOW(), locked_at=NULL, last_error=NULL
		 WHERE id=$1::uuid AND status='PROCESSING'`, id)
	return err
}

func (store *PostgresStore) failInventoryAlert(ctx context.Context, id, message string) error {
	message = strings.TrimSpace(message)
	if len(message) > 1000 {
		message = message[:1000]
	}
	_, err := store.db.Exec(ctx,
		`UPDATE inventory_alert_outbox
		 SET status='PENDING', locked_at=NULL, last_error=$2
		 WHERE id=$1::uuid AND status='PROCESSING'`, id, message)
	return err
}

// DispatchInventoryAlertsOnce claims a small batch and publishes it to SQS.
// Rows return to PENDING after a send failure, while stale PROCESSING rows are
// reclaimed after five minutes if the process dies mid-dispatch.
func DispatchInventoryAlertsOnce(ctx context.Context, logger *slog.Logger, outbox inventoryAlertOutbox, queue inventoryAlertQueue, queueURL string) error {
	alerts, err := outbox.claimInventoryAlerts(ctx, inventoryAlertBatchSize)
	if err != nil {
		return fmt.Errorf("claim inventory alerts: %w", err)
	}
	var dispatchErrors []error
	for _, alert := range alerts {
		body, err := json.Marshal(alert)
		if err == nil {
			_, err = queue.SendMessage(ctx, &sqs.SendMessageInput{
				QueueUrl:               aws.String(queueURL),
				MessageBody:            aws.String(string(body)),
				MessageGroupId:         aws.String("inventory-alerts"),
				MessageDeduplicationId: aws.String(fmt.Sprintf("%s:%d", alert.VariantID, alert.InventoryVersion)),
			})
		}
		if err != nil {
			if failErr := outbox.failInventoryAlert(ctx, alert.ID, err.Error()); failErr != nil {
				err = errors.Join(err, failErr)
			}
			dispatchErrors = append(dispatchErrors, fmt.Errorf("dispatch inventory alert %s: %w", alert.ID, err))
			continue
		}
		if err := outbox.completeInventoryAlert(ctx, alert.ID); err != nil {
			dispatchErrors = append(dispatchErrors, fmt.Errorf("complete inventory alert %s: %w", alert.ID, err))
			continue
		}
		logger.Info("low-stock alert queued", "variant_id", alert.VariantID, "available_quantity", alert.AvailableQuantity)
	}
	return errors.Join(dispatchErrors...)
}

// RunInventoryAlertDispatcher continually drains the transactional outbox
// until its context is cancelled during graceful shutdown.
func RunInventoryAlertDispatcher(ctx context.Context, logger *slog.Logger, store *PostgresStore, queue inventoryAlertQueue, queueURL string) {
	ticker := time.NewTicker(20 * time.Second)
	defer ticker.Stop()
	for {
		dispatchCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
		err := DispatchInventoryAlertsOnce(dispatchCtx, logger, store, queue, queueURL)
		cancel()
		if err != nil && !errors.Is(err, context.Canceled) {
			logger.Error("low-stock alert dispatch failed", "error", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}
