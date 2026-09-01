package httpserver

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

type refundRequest struct {
	OrderNumber    string `json:"order_number"`
	AmountPaise    int64  `json:"amount_paise,omitempty"`
	Reason         string `json:"reason"`
	IdempotencyKey string `json:"idempotency_key"`
}

type razorpayRefundResponse struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

func (server *Server) refundStore() (commerce.RefundStore, bool) {
	store, ok := server.store.(commerce.RefundStore)
	return store, ok
}

func refundReceipt(idempotencyKey string) string {
	digest := sha256.Sum256([]byte(idempotencyKey))
	return "YVR-" + hex.EncodeToString(digest[:16])
}

func (server *Server) createRefund(w http.ResponseWriter, request *http.Request) {
	if server.razorpayKeyID == "" || server.razorpayKeySecret == "" {
		writeError(w, http.StatusServiceUnavailable, "refund_unavailable", "Razorpay refunds are not configured.")
		return
	}
	store, ok := server.refundStore()
	if !ok {
		writeError(w, http.StatusServiceUnavailable, "refund_unavailable", "This store does not support refunds.")
		return
	}
	var input refundRequest
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	input.OrderNumber = strings.TrimSpace(input.OrderNumber)
	input.Reason = strings.TrimSpace(input.Reason)
	input.IdempotencyKey = strings.TrimSpace(input.IdempotencyKey)
	if input.OrderNumber == "" || input.Reason == "" || len(input.Reason) > 500 || input.IdempotencyKey == "" || len(input.IdempotencyKey) > 200 || input.AmountPaise < 0 {
		writeError(w, http.StatusBadRequest, "invalid_request", "Order number, reason and a valid idempotency key are required.")
		return
	}
	refund, replayed, err := store.PrepareRefund(input.OrderNumber, input.AmountPaise, input.Reason, input.IdempotencyKey, refundReceipt(input.IdempotencyKey))
	if err != nil {
		server.writeRefundError(w, err)
		return
	}
	if replayed && refund.ProviderRefundID != "" {
		writeJSON(w, http.StatusOK, refund)
		return
	}
	provider, err := server.createRazorpayGatewayRefund(request, refund)
	if err != nil {
		server.logger.Error("razorpay refund creation failed", "order_number", refund.OrderNumber, "refund_id", refund.ID, "error", err)
		// Keep the durable row pending. A retry uses the same receipt, which
		// Razorpay treats as its idempotency key, so a timeout cannot pay twice.
		writeError(w, http.StatusBadGateway, "refund_provider_error", "The refund provider did not confirm the request. Retry with the same idempotency key.")
		return
	}
	refund, err = store.CompleteRefund(input.IdempotencyKey, provider.ID, provider.Status)
	if err != nil {
		server.logger.Error("refund persistence failed after provider response", "refund_id", refund.ID, "provider_refund_id", provider.ID, "error", err)
		writeError(w, http.StatusInternalServerError, "refund_persistence_error", "The provider accepted the refund but local reconciliation is pending.")
		return
	}
	writeJSON(w, http.StatusCreated, refund)
}

func (server *Server) createRazorpayGatewayRefund(request *http.Request, refund commerce.Refund) (razorpayRefundResponse, error) {
	payload, err := json.Marshal(map[string]any{
		"amount":  refund.AmountPaise,
		"speed":   "normal",
		"receipt": refund.Receipt,
		"notes":   map[string]string{"order_number": refund.OrderNumber, "reason": refund.Reason},
	})
	if err != nil {
		return razorpayRefundResponse{}, err
	}
	endpoint := "https://api.razorpay.com/v1/payments/" + url.PathEscape(refund.ProviderPaymentID) + "/refund"
	gatewayRequest, err := http.NewRequestWithContext(request.Context(), http.MethodPost, endpoint, strings.NewReader(string(payload)))
	if err != nil {
		return razorpayRefundResponse{}, err
	}
	gatewayRequest.Header.Set("Content-Type", "application/json")
	gatewayRequest.SetBasicAuth(server.razorpayKeyID, server.razorpayKeySecret)
	response, err := (&http.Client{Timeout: 15 * time.Second}).Do(gatewayRequest)
	if err != nil {
		return razorpayRefundResponse{}, err
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	if err != nil {
		return razorpayRefundResponse{}, err
	}
	if response.StatusCode < 200 || response.StatusCode > 299 {
		return razorpayRefundResponse{}, fmt.Errorf("gateway returned %s", response.Status)
	}
	var result razorpayRefundResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return razorpayRefundResponse{}, err
	}
	if result.ID == "" {
		return razorpayRefundResponse{}, errors.New("gateway did not return a refund id")
	}
	return result, nil
}

func (server *Server) writeRefundError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, commerce.ErrOrderNotFound):
		writeError(w, http.StatusNotFound, "order_not_found", "The order could not be found.")
	case errors.Is(err, commerce.ErrRefundNotSupported):
		writeError(w, http.StatusConflict, "refund_not_supported", "Only captured Razorpay payments can be refunded.")
	case errors.Is(err, commerce.ErrRefundAmountInvalid):
		writeError(w, http.StatusConflict, "refund_amount_invalid", "The refund exceeds the remaining captured amount.")
	case errors.Is(err, commerce.ErrRefundIdempotencyConflict):
		writeError(w, http.StatusConflict, "idempotency_conflict", "That idempotency key was already used for different refund details.")
	default:
		server.logger.Error("refund operation failed", "error", err)
		writeError(w, http.StatusInternalServerError, "refund_error", "The refund could not be prepared.")
	}
}
