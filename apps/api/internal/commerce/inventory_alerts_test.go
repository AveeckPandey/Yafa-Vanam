package commerce

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

type fakeInventoryAlertOutbox struct {
	alerts    []InventoryAlert
	completed []string
	failed    map[string]string
}

func (outbox *fakeInventoryAlertOutbox) claimInventoryAlerts(context.Context, int) ([]InventoryAlert, error) {
	return outbox.alerts, nil
}

func (outbox *fakeInventoryAlertOutbox) completeInventoryAlert(_ context.Context, id string) error {
	outbox.completed = append(outbox.completed, id)
	return nil
}

func (outbox *fakeInventoryAlertOutbox) failInventoryAlert(_ context.Context, id, message string) error {
	if outbox.failed == nil {
		outbox.failed = map[string]string{}
	}
	outbox.failed[id] = message
	return nil
}

type fakeInventoryAlertQueue struct {
	input *sqs.SendMessageInput
	err   error
}

func (queue *fakeInventoryAlertQueue) SendMessage(_ context.Context, input *sqs.SendMessageInput, _ ...func(*sqs.Options)) (*sqs.SendMessageOutput, error) {
	queue.input = input
	return &sqs.SendMessageOutput{}, queue.err
}

func TestDispatchInventoryAlertsOnceCompletesSentAlert(t *testing.T) {
	alert := InventoryAlert{ID: "event-1", VariantID: "variant-1", AvailableQuantity: 10, LowStockThreshold: 10, InventoryVersion: 91, CreatedAt: time.Unix(1, 0).UTC()}
	outbox := &fakeInventoryAlertOutbox{alerts: []InventoryAlert{alert}}
	queue := &fakeInventoryAlertQueue{}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))

	if err := DispatchInventoryAlertsOnce(context.Background(), logger, outbox, queue, "queue-url"); err != nil {
		t.Fatalf("DispatchInventoryAlertsOnce() error = %v", err)
	}
	if len(outbox.completed) != 1 || outbox.completed[0] != alert.ID {
		t.Fatalf("completed = %v, want [%s]", outbox.completed, alert.ID)
	}
	if got := aws.ToString(queue.input.MessageDeduplicationId); got != "variant-1:91" {
		t.Fatalf("deduplication id = %q", got)
	}
	if got := aws.ToString(queue.input.MessageGroupId); got != "inventory-alerts" {
		t.Fatalf("message group id = %q", got)
	}
}

func TestDispatchInventoryAlertsOnceReturnsFailedAlertToPending(t *testing.T) {
	outbox := &fakeInventoryAlertOutbox{alerts: []InventoryAlert{{ID: "event-2", VariantID: "variant-2", InventoryVersion: 1}}}
	queue := &fakeInventoryAlertQueue{err: errors.New("SQS unavailable")}
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))

	err := DispatchInventoryAlertsOnce(context.Background(), logger, outbox, queue, "queue-url")
	if err == nil {
		t.Fatal("DispatchInventoryAlertsOnce() error = nil")
	}
	if got := outbox.failed["event-2"]; got != "SQS unavailable" {
		t.Fatalf("failed message = %q", got)
	}
	if len(outbox.completed) != 0 {
		t.Fatalf("completed = %v, want none", outbox.completed)
	}
}
