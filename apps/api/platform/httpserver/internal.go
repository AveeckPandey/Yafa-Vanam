package httpserver

import (
	"crypto/subtle"
	"errors"
	"net/http"
	"strings"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

// internalGuard protects machine-to-machine routes (the welcome-coupon Lambda)
// with a shared bearer token. The token is unset in local/database-free setups
// by design: an unconfigured secret must fail closed with 503, never fall
// open.
func (server *Server) internalGuard(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		expected := server.internalServiceToken
		if expected == "" {
			writeError(w, http.StatusServiceUnavailable, "not_configured", "Internal service is not configured.")
			return
		}
		presented := strings.TrimPrefix(request.Header.Get("Authorization"), "Bearer ")
		if presented == "" || subtle.ConstantTimeCompare([]byte(presented), []byte(expected)) != 1 {
			writeError(w, http.StatusUnauthorized, "unauthorized", "Invalid service credentials.")
			return
		}
		next.ServeHTTP(w, request)
	})
}

func (server *Server) lifecycleStore() (commerce.LifecycleStore, bool) {
	lifecycle, ok := server.store.(commerce.LifecycleStore)
	return lifecycle, ok
}

// issueWelcomeCoupon is called by the Cognito PostConfirmation Lambda after a
// confirmed sign-up. It is idempotent: retries and duplicate triggers return
// the customer's existing coupon instead of minting another one.
func (server *Server) issueWelcomeCoupon(w http.ResponseWriter, request *http.Request) {
	lifecycle, ok := server.lifecycleStore()
	if !ok {
		writeError(w, http.StatusServiceUnavailable, "not_supported", "This store does not support lifecycle coupons.")
		return
	}
	var input struct {
		CognitoSub string `json:"cognito_sub"`
		Email      string `json:"email"`
	}
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	coupon, err := lifecycle.IssueWelcomeCoupon(request.Context(), input.Email, input.CognitoSub)
	if err != nil {
		if isInvalidEmail(err) {
			writeError(w, http.StatusBadRequest, "validation_error", "A valid customer email is required.")
		} else {
			server.logger.Error("welcome coupon issue failed", "error", err)
			writeError(w, http.StatusInternalServerError, "internal_error", "An unexpected error occurred.")
		}
		return
	}
	// Only log shape, never contents — codes and addresses stay out of logs.
	server.logger.Info("welcome coupon issued", "coupon_expires_at", coupon.ExpiresAt.Format(http.TimeFormat))
	writeJSON(w, http.StatusOK, coupon)
}

// recordLifecycleMessage stores the SES outcome of a lifecycle email for
// auditing. Failures here are logged but never block the Lambda's own retry
// semantics — SES delivery state is observability, not money.
func (server *Server) recordLifecycleMessage(w http.ResponseWriter, request *http.Request) {
	lifecycle, ok := server.lifecycleStore()
	if !ok {
		writeError(w, http.StatusServiceUnavailable, "not_supported", "This store does not support lifecycle messages.")
		return
	}
	var input commerce.LifecycleMessageInput
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	id, err := lifecycle.RecordLifecycleMessage(request.Context(), input)
	if err != nil {
		if isInvalidEmail(err) {
			writeError(w, http.StatusBadRequest, "validation_error", "A valid customer email is required.")
		} else {
			server.logger.Error("lifecycle message record failed", "error", err)
			writeError(w, http.StatusInternalServerError, "internal_error", "An unexpected error occurred.")
		}
		return
	}
	writeJSON(w, http.StatusCreated, map[string]string{"id": id})
}

func isInvalidEmail(err error) bool {
	return errors.Is(err, commerce.ErrInvalidEmail)
}
