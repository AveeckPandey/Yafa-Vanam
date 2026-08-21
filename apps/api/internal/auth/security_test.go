package auth

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func TestCSRFMiddlewareRequiresDoubleSubmitForSignedInMutation(t *testing.T) {
	handler := (&Handler{}).CSRFMiddleware(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	}))

	valid := httptest.NewRequest(http.MethodPost, "/api/v1/carts", nil)
	valid.AddCookie(&http.Cookie{Name: accessCookie, Value: "access"})
	valid.AddCookie(&http.Cookie{Name: csrfCookie, Value: "csrf-value"})
	valid.Header.Set("X-CSRF-Token", "csrf-value")
	validRecorder := httptest.NewRecorder()
	handler.ServeHTTP(validRecorder, valid)
	if validRecorder.Code != http.StatusNoContent {
		t.Fatalf("valid CSRF request status = %d", validRecorder.Code)
	}

	blocked := httptest.NewRequest(http.MethodPost, "/api/v1/carts", nil)
	blocked.AddCookie(&http.Cookie{Name: accessCookie, Value: "access"})
	blockedRecorder := httptest.NewRecorder()
	handler.ServeHTTP(blockedRecorder, blocked)
	if blockedRecorder.Code != http.StatusForbidden {
		t.Fatalf("missing CSRF token status = %d", blockedRecorder.Code)
	}
}

func TestAccessValidationAllowsOnlyHS256(t *testing.T) {
	secret := strings.Repeat("s", 32)
	service := New(nil, nil, Config{JWTSecret: secret})
	claims := jwt.MapClaims{"sub": "user-1", "email": "person@example.test", "name": "Person", "kind": "access", "exp": time.Now().Add(time.Minute).Unix()}

	valid, err := jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
	if err != nil {
		t.Fatal(err)
	}
	if _, err = service.ValidateAccess(valid); err != nil {
		t.Fatalf("HS256 access token should validate: %v", err)
	}

	wrongAlgorithm, err := jwt.NewWithClaims(jwt.SigningMethodHS512, claims).SignedString([]byte(secret))
	if err != nil {
		t.Fatal(err)
	}
	if _, err = service.ValidateAccess(wrongAlgorithm); err == nil {
		t.Fatal("a non-HS256 token must be rejected")
	}
}
