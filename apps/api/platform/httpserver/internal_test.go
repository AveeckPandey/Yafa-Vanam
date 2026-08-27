package httpserver

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

// stubLifecycleStore embeds the memory store (which does NOT implement
// LifecycleStore) and records lifecycle calls, so endpoint tests run without
// Postgres.
type stubLifecycleStore struct {
	*commerce.Store
	coupon      commerce.WelcomeCoupon
	messages    []commerce.LifecycleMessageInput
	failWelcome bool
}

func (stub *stubLifecycleStore) IssueWelcomeCoupon(ctx context.Context, email, subject string) (commerce.WelcomeCoupon, error) {
	if !strings.Contains(email, "@") || strings.Contains(email, " ") || email == "@bad.com" {
		return commerce.WelcomeCoupon{}, commerce.ErrInvalidEmail
	}
	if stub.failWelcome {
		return commerce.WelcomeCoupon{}, errors.New("database unavailable")
	}
	if stub.coupon.Code == "" {
		stub.coupon = commerce.WelcomeCoupon{Code: "WELCOME10-TESTCODE", DiscountPercent: 10}
	}
	return stub.coupon, nil
}

func (stub *stubLifecycleStore) RecordLifecycleMessage(ctx context.Context, message commerce.LifecycleMessageInput) (string, error) {
	if message.Email == "ghost@example.com" {
		return "", commerce.ErrInvalidEmail
	}
	stub.messages = append(stub.messages, message)
	return "lm_1", nil
}

func newInternalTestServer(t *testing.T, token string, store commerce.CommerceStore) http.Handler {
	t.Helper()
	catalog, err := commerce.DecodeCatalog(strings.NewReader(`[{"id":"p1","name":"Tint","slug":"tint","category":"Makeup","subcategory":"Lips","product_type":"Tint","status":"active","commerce":{"currency":"INR","base_price":1000},"variants":[{"id":"v1","price":1000,"stock":2,"is_active":true}],"images":{"paths_verified":false}}]`))
	if err != nil {
		t.Fatal(err)
	}
	return New(catalog, store, Config{InternalServiceToken: token})
}

func TestInternalRoutesFailClosedWithoutToken(t *testing.T) {
	handler := newInternalTestServer(t, "", commerce.NewStore(nil))
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/api/internal/coupons/welcome", strings.NewReader("{}")))
	if response.Code != http.StatusServiceUnavailable {
		t.Fatalf("unconfigured token status = %d, want 503", response.Code)
	}
}

func TestInternalRoutesRequireBearerToken(t *testing.T) {
	handler := newInternalTestServer(t, "secret-token", commerce.NewStore(nil))
	request := httptest.NewRequest(http.MethodPost, "/api/internal/coupons/welcome", strings.NewReader(`{"email":"a@b.co"}`))
	request.Header.Set("Authorization", "Bearer wrong-token")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("wrong bearer status = %d, want 401", response.Code)
	}

	missing := httptest.NewRecorder()
	handler.ServeHTTP(missing, httptest.NewRequest(http.MethodPost, "/api/internal/coupons/welcome", strings.NewReader(`{}`)))
	if missing.Code != http.StatusUnauthorized {
		t.Fatalf("missing bearer status = %d, want 401", missing.Code)
	}
}

func TestWelcomeCouponEndpointIssuesCoupon(t *testing.T) {
	handler := newInternalTestServer(t, "secret-token", &stubLifecycleStore{Store: commerce.NewStore(nil)})
	request := httptest.NewRequest(http.MethodPost, "/api/internal/coupons/welcome", strings.NewReader(`{"cognito_sub":"sub-1","email":"new@example.com"}`))
	request.Header.Set("Authorization", "Bearer secret-token")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusOK || !strings.Contains(response.Body.String(), "WELCOME10-TESTCODE") {
		t.Fatalf("welcome endpoint status = %d body = %s", response.Code, response.Body.String())
	}
}

func TestRecordLifecycleMessageStoresOutcome(t *testing.T) {
	store := &stubLifecycleStore{Store: commerce.NewStore(nil)}
	handler := newInternalTestServer(t, "secret-token", store)

	body := `{"email":"new@example.com","channel":"EMAIL","trigger_name":"welcome_coupon","coupon_code":"WELCOME10-TESTCODE","provider_message_id":"ses-123","status":"SENT"}`
	request := httptest.NewRequest(http.MethodPost, "/api/internal/messages/record", strings.NewReader(body))
	request.Header.Set("Authorization", "Bearer secret-token")
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, request)
	if response.Code != http.StatusCreated || !strings.Contains(response.Body.String(), `"id":"lm_1"`) {
		t.Fatalf("record status = %d body = %s", response.Code, response.Body.String())
	}
	if len(store.messages) != 1 || store.messages[0].ProviderMessageID != "ses-123" || store.messages[0].Status != "SENT" {
		t.Fatalf("stored messages = %#v", store.messages)
	}

	unknownUser := httptest.NewRequest(http.MethodPost, "/api/internal/messages/record", strings.NewReader(`{"email":"ghost@example.com"}`))
	unknownUser.Header.Set("Authorization", "Bearer secret-token")
	unknownResponse := httptest.NewRecorder()
	handler.ServeHTTP(unknownResponse, unknownUser)
	if unknownResponse.Code != http.StatusBadRequest {
		t.Fatalf("unknown user status = %d, want 400", unknownResponse.Code)
	}
}
