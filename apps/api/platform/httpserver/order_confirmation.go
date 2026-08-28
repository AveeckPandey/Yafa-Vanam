package httpserver

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

// OrderConfirmationPublisher deliberately sits behind an interface so a queue
// outage cannot affect payment confirmation. SQS/Lambda retries delivery.
type OrderConfirmationPublisher interface {
	Publish(context.Context, commerce.Order) error
}

type sqsOrderConfirmationPublisher struct {
	client   *sqs.Client
	queueURL string
}

func NewSQSOrderConfirmationPublisher(client *sqs.Client, queueURL string) OrderConfirmationPublisher {
	if client == nil || strings.TrimSpace(queueURL) == "" {
		return nil
	}
	return &sqsOrderConfirmationPublisher{client: client, queueURL: strings.TrimSpace(queueURL)}
}

func (publisher *sqsOrderConfirmationPublisher) Publish(ctx context.Context, order commerce.Order) error {
	body, err := json.Marshal(order)
	if err != nil {
		return err
	}
	_, err = publisher.client.SendMessage(ctx, &sqs.SendMessageInput{QueueUrl: aws.String(publisher.queueURL), MessageBody: aws.String(string(body))})
	return err
}

func (server *Server) enqueueOrderConfirmation(ctx context.Context, order commerce.Order) {
	if server.orderConfirmationPublisher == nil || strings.TrimSpace(order.CustomerEmail) == "" {
		return
	}
	if err := server.orderConfirmationPublisher.Publish(ctx, order); err != nil {
		server.logger.Error("order confirmation queue publish failed", "order_number", order.OrderNumber, "error", err)
		return
	}
	server.logger.Info("order confirmation queued", "order_number", order.OrderNumber)
}
