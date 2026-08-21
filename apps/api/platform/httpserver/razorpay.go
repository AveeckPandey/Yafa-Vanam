package httpserver

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

type razorpayOrderRequest struct {
	commerce.CreateOrderInput
}

type razorpayOrderResponse struct {
	OrderNumber     string `json:"order_number"`
	RazorpayOrderID string `json:"razorpay_order_id"`
	Amount          int64  `json:"amount"`
	Currency        string `json:"currency"`
	KeyID           string `json:"key_id"`
}

type razorpayVerificationRequest struct {
	RazorpayPaymentID string `json:"razorpay_payment_id"`
	RazorpayOrderID   string `json:"razorpay_order_id"`
	RazorpaySignature string `json:"razorpay_signature"`
}

func (server *Server) paymentConfigurationError(w http.ResponseWriter) bool {
	if !server.razorpayCheckoutEnabled {
		writeError(w, http.StatusServiceUnavailable, "payment_unavailable", "Secure payments are being finalised. Please try again shortly.")
		return true
	}
	if server.razorpayKeyID == "" || server.razorpayKeySecret == "" {
		writeError(w, http.StatusServiceUnavailable, "payment_unavailable", "Razorpay is not configured.")
		return true
	}
	return false
}

func (server *Server) createRazorpayOrder(w http.ResponseWriter, request *http.Request) {
	if server.paymentConfigurationError(w) {
		return
	}
	var input razorpayOrderRequest
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	idempotencyKey := strings.TrimSpace(request.Header.Get("Idempotency-Key"))
	if len(idempotencyKey) > 200 {
		writeError(w, http.StatusBadRequest, "invalid_idempotency_key", "Idempotency-Key must be 200 characters or fewer")
		return
	}
	// A retry with the same idempotency key must never create a second gateway
	// order while the first request is still attaching its provider ID.
	server.razorpayMu.Lock()
	defer server.razorpayMu.Unlock()
	var order commerce.Order
	var err error
	if user, ok := requestUser(request); ok {
		input.CustomerEmail = user.Email
		order, _, err = server.store.CreateOrderForUser(user.ID, input.CreateOrderInput, idempotencyKey)
	} else {
		order, _, err = server.store.CreateOrder(input.CreateOrderInput, idempotencyKey)
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}

	razorpayOrderID := order.RazorpayOrderID
	if razorpayOrderID == "" {
		razorpayOrderID, err = server.createRazorpayGatewayOrder(request, order)
		if err != nil {
			server.logger.Error("razorpay order creation failed", "order_number", order.OrderNumber, "error", err)
			writeError(w, http.StatusBadGateway, "payment_provider_error", "We could not prepare your payment. Please try again.")
			return
		}
		if _, err := server.store.AttachRazorpayOrder(order.OrderNumber, razorpayOrderID); err != nil {
			server.logger.Error("razorpay order attachment failed", "order_number", order.OrderNumber, "error", err)
			writeError(w, http.StatusInternalServerError, "payment_setup_error", "We could not prepare your payment. Please try again.")
			return
		}
	}
	writeJSON(w, http.StatusCreated, razorpayOrderResponse{OrderNumber: order.OrderNumber, RazorpayOrderID: razorpayOrderID, Amount: int64(order.TotalAmount * 100), Currency: order.Currency, KeyID: server.razorpayKeyID})
}

func (server *Server) createRazorpayGatewayOrder(request *http.Request, order commerce.Order) (string, error) {
	payload, err := json.Marshal(map[string]any{
		"amount":   int64(order.TotalAmount * 100),
		"currency": order.Currency,
		"receipt":  order.OrderNumber,
		"notes":    map[string]string{"yafa_order_number": order.OrderNumber},
	})
	if err != nil {
		return "", err
	}
	gatewayRequest, err := http.NewRequestWithContext(request.Context(), http.MethodPost, "https://api.razorpay.com/v1/orders", strings.NewReader(string(payload)))
	if err != nil {
		return "", err
	}
	gatewayRequest.Header.Set("Content-Type", "application/json")
	gatewayRequest.SetBasicAuth(server.razorpayKeyID, server.razorpayKeySecret)
	client := &http.Client{Timeout: 15 * time.Second}
	response, err := client.Do(gatewayRequest)
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode > 299 {
		return "", fmt.Errorf("gateway returned %s", response.Status)
	}
	var result struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(io.LimitReader(response.Body, 1<<20)).Decode(&result); err != nil {
		return "", err
	}
	if result.ID == "" {
		return "", errors.New("gateway did not return an order id")
	}
	return result.ID, nil
}

func (server *Server) verifyRazorpayPayment(w http.ResponseWriter, request *http.Request) {
	if server.paymentConfigurationError(w) {
		return
	}
	var input razorpayVerificationRequest
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	message := input.RazorpayOrderID + "|" + input.RazorpayPaymentID
	if !validRazorpaySignature(server.razorpayKeySecret, message, input.RazorpaySignature) {
		writeError(w, http.StatusBadRequest, "invalid_payment_signature", "Payment signature could not be verified.")
		return
	}
	order, err := server.store.VerifyRazorpayPayment(input.RazorpayOrderID, input.RazorpayPaymentID)
	if err != nil {
		if errors.Is(err, commerce.ErrPaymentOrderNotFound) {
			writeError(w, http.StatusNotFound, "payment_order_not_found", "The payment order could not be found.")
			return
		}
		server.logger.Error("razorpay verification update failed", "error", err)
		writeError(w, http.StatusInternalServerError, "payment_verification_error", "Payment verification could not be completed.")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"verified": true, "order_number": order.OrderNumber, "payment_status": order.PaymentStatus})
}

func (server *Server) razorpayWebhook(w http.ResponseWriter, request *http.Request) {
	if server.razorpayWebhookSecret == "" {
		writeError(w, http.StatusServiceUnavailable, "webhook_unavailable", "Razorpay webhook verification is not configured.")
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, request.Body, 1<<20))
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "Webhook payload could not be read.")
		return
	}
	if !validRazorpaySignature(server.razorpayWebhookSecret, string(body), request.Header.Get("X-Razorpay-Signature")) {
		writeError(w, http.StatusBadRequest, "invalid_webhook_signature", "Webhook signature could not be verified.")
		return
	}
	var event struct {
		Event   string `json:"event"`
		Payload struct {
			Payment struct {
				Entity struct {
					ID      string `json:"id"`
					OrderID string `json:"order_id"`
				} `json:"entity"`
			} `json:"payment"`
			Order struct {
				Entity struct {
					ID string `json:"id"`
				} `json:"entity"`
			} `json:"order"`
		} `json:"payload"`
	}
	if err := json.Unmarshal(body, &event); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "Webhook payload is invalid.")
		return
	}
	orderID := event.Payload.Payment.Entity.OrderID
	if orderID == "" {
		orderID = event.Payload.Order.Entity.ID
	}
	status := ""
	switch event.Event {
	case "payment.captured", "order.paid":
		status = "captured"
	case "payment.failed":
		status = "failed"
	default:
		writeJSON(w, http.StatusOK, map[string]bool{"received": true})
		return
	}
	if orderID == "" {
		writeJSON(w, http.StatusOK, map[string]bool{"received": true})
		return
	}
	if _, err := server.store.RecordRazorpayPayment(orderID, event.Payload.Payment.Entity.ID, status); err != nil {
		if !errors.Is(err, commerce.ErrPaymentOrderNotFound) {
			server.logger.Error("razorpay webhook update failed", "event", event.Event, "error", err)
		}
	}
	writeJSON(w, http.StatusOK, map[string]bool{"received": true})
}

func validRazorpaySignature(secret, message, signature string) bool {
	if secret == "" || signature == "" {
		return false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(message))
	provided, err := hex.DecodeString(strings.TrimSpace(signature))
	return err == nil && hmac.Equal(mac.Sum(nil), provided)
}
