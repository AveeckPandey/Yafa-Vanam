package auth

import (
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/time/rate"
)

const (
	testIssuer  = "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_TESTPOOL"
	testClient  = "test-client-id"
	testEmail   = "shopper@example.test"
	testSubject = "cognito-subject-1"
)

// jwksServer serves the pool's public keys and can be rotated mid-test.
type jwksServer struct {
	*httptest.Server
	mu   sync.Mutex
	key  *rsa.PrivateKey
	kids map[string]*rsa.PrivateKey
}

func newJWKSServer(t *testing.T) *jwksServer {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	s := &jwksServer{key: key, kids: map[string]*rsa.PrivateKey{"test-key": key}}
	s.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		s.mu.Lock()
		defer s.mu.Unlock()
		keys := make([]map[string]string, 0, len(s.kids))
		for kid, k := range s.kids {
			keys = append(keys, map[string]string{
				"kid": kid, "kty": "RSA", "alg": "RS256",
				"n": base64.RawURLEncoding.EncodeToString(k.N.Bytes()),
				"e": base64.RawURLEncoding.EncodeToString(big.NewInt(int64(k.E)).Bytes()),
			})
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"keys": keys})
	}))
	t.Cleanup(s.Close)
	return s
}

func (s *jwksServer) rotate(t *testing.T) *rsa.PrivateKey {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	s.mu.Lock()
	s.kids = map[string]*rsa.PrivateKey{"rotated-key": key}
	s.mu.Unlock()
	return key
}

func signCognitoIDToken(t *testing.T, key *rsa.PrivateKey, kid string, mutate func(jwt.MapClaims)) string {
	t.Helper()
	now := time.Now()
	claims := jwt.MapClaims{
		"iss": testIssuer, "aud": testClient, "token_use": "id",
		"sub": testSubject, "email": testEmail, "name": "Shopper",
		"email_verified": true,
		"iat":            now.Unix(),
		"exp":            now.Add(5 * time.Minute).Unix(),
	}
	if mutate != nil {
		mutate(claims)
	}
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	token.Header["kid"] = kid
	signed, err := token.SignedString(key)
	if err != nil {
		t.Fatal(err)
	}
	return signed
}

func TestCognitoVerifierRejectsInvalidTokens(t *testing.T) {
	jwks := newJWKSServer(t)
	verifier := newCognitoVerifier(testIssuer, testClient)
	verifier.jwksURL = jwks.URL + "/.well-known/jwks.json"
	valid := signCognitoIDToken(t, jwks.key, "test-key", nil)

	if _, err := verifier.Verify(valid); err != nil {
		t.Fatalf("valid id_token must verify: %v", err)
	}
	stringVerified := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["email_verified"] = "true" })
	if _, err := verifier.Verify(stringVerified); err != nil {
		t.Fatalf("string-verified id_token must verify: %v", err)
	}

	hs256Forgery, err := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{"iss": testIssuer}).SignedString([]byte("secret"))
	if err != nil {
		t.Fatal(err)
	}
	expired := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["exp"] = time.Now().Add(-time.Hour).Unix() })
	wrongIssuer := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["iss"] = "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_OTHER" })
	wrongAudience := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["aud"] = "someone-elses-client" })
	accessTokenKind := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["token_use"] = "access" })
	unverifiedEmail := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["email_verified"] = false })
	stringUnverified := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { c["email_verified"] = "false" })
	missingEmailVerified := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { delete(c, "email_verified") })
	missingSub := signCognitoIDToken(t, jwks.key, "test-key", func(c jwt.MapClaims) { delete(c, "sub") })

	for name, token := range map[string]string{
		"HS256 forgery":        hs256Forgery,
		"expired":              expired,
		"wrong issuer":         wrongIssuer,
		"wrong audience":       wrongAudience,
		"access token_use":     accessTokenKind,
		"unverified email":     unverifiedEmail,
		"string unverified":    stringUnverified,
		"missing email_verify": missingEmailVerified,
		"missing subject":      missingSub,
		"tampered payload": valid[:len(valid)-4] + "AAAA",
		"unknown kid":      signCognitoIDToken(t, jwks.key, "never-published", nil),
	} {
		if _, err := verifier.Verify(token); err == nil {
			t.Errorf("%s must be rejected", name)
		}
	}
}

func TestCognitoVerifierRefreshesKeysOnRotation(t *testing.T) {
	jwks := newJWKSServer(t)
	verifier := newCognitoVerifier(testIssuer, testClient)
	verifier.jwksURL = jwks.URL + "/.well-known/jwks.json"

	oldToken := signCognitoIDToken(t, jwks.key, "test-key", nil)
	if _, err := verifier.Verify(oldToken); err != nil {
		t.Fatalf("pre-rotation token should verify: %v", err)
	}
	newKey := jwks.rotate(t)
	rotatedToken := signCognitoIDToken(t, newKey, "rotated-key", nil)
	// The rotated key is unknown to the cached JWKS; the verifier must force a
	// refresh and succeed without any manual cache invalidation.
	if _, err := verifier.Verify(rotatedToken); err != nil {
		t.Fatalf("post-rotation token should verify after forced JWKS refresh: %v", err)
	}
	// Old-kid tokens now fail: the pool no longer publishes that key.
	if _, err := verifier.Verify(oldToken); err == nil {
		t.Fatal("token signed by a removed key must be rejected")
	}
}

func TestNewCognitoVerifierRequiresFullConfiguration(t *testing.T) {
	for _, parts := range [][3]string{{"", "pool", "client"}, {"ap-south-1", "", "client"}, {"ap-south-1", "pool", ""}} {
		if NewCognitoVerifier(parts[0], parts[1], parts[2]) != nil {
			t.Fatalf("partial config %v must disable the verifier", parts)
		}
	}
	v := NewCognitoVerifier(" ap-south-1 ", " ap-south-1_POOL ", " client ")
	if v == nil || v.issuer != fmt.Sprintf("https://cognito-idp.%s.amazonaws.com/%s", "ap-south-1", "ap-south-1_POOL") {
		t.Fatalf("full config must produce an issuer-scoped verifier, got %+v", v)
	}
}

func TestCognitoExchangeEndpointGuards(t *testing.T) {
	post := func(body string, csrfValue, csrfHeader string) *httptest.ResponseRecorder {
		request := httptest.NewRequest(http.MethodPost, "/auth/cognito/exchange", strings.NewReader(body))
		if csrfValue != "" {
			request.AddCookie(&http.Cookie{Name: csrfCookie, Value: csrfValue})
		}
		if csrfHeader != "" {
			request.Header.Set("X-CSRF-Token", csrfHeader)
		}
		recorder := httptest.NewRecorder()
		handler := &Handler{exchangeLimiter: rate.NewLimiter(rate.Inf, 1)}
		handler.cognitoExchange(recorder, request)
		return recorder
	}

	// A missing CSRF pair is rejected before configuration is even examined.
	if code := post(`{"id_token":"x"}`, "", "").Code; code != http.StatusForbidden {
		t.Fatalf("missing CSRF status = %d, want 403", code)
	}
	if code := post(`{"id_token":"x"}`, csrfCookie, "other-value").Code; code != http.StatusForbidden {
		t.Fatalf("mismatched CSRF status = %d, want 403", code)
	}

	// Without pool configuration the endpoint degrades to 503 rather than
	// half-working; CSRF still gates first.
	notConfigured := &Handler{exchangeLimiter: rate.NewLimiter(rate.Inf, 1)}
	request := httptest.NewRequest(http.MethodPost, "/auth/cognito/exchange", strings.NewReader(`{"id_token":"x"}`))
	request.AddCookie(&http.Cookie{Name: csrfCookie, Value: "token-value"})
	request.Header.Set("X-CSRF-Token", "token-value")
	recorder := httptest.NewRecorder()
	notConfigured.cognitoExchange(recorder, request)
	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("unconfigured verifier status = %d, want 503", recorder.Code)
	}

	// Malformed JSON with full credentials present.
	verifier := newCognitoVerifier(testIssuer, testClient)
	verifier.jwksURL = "http://127.0.0.1:1/.well-known/jwks.json" // never reached for a 400
	gated := &Handler{exchangeLimiter: rate.NewLimiter(rate.Inf, 1), cognito: verifier}
	badBody := httptest.NewRequest(http.MethodPost, "/auth/cognito/exchange", strings.NewReader(`not-json`))
	badBody.AddCookie(&http.Cookie{Name: csrfCookie, Value: "token-value"})
	badBody.Header.Set("X-CSRF-Token", "token-value")
	badRecorder := httptest.NewRecorder()
	gated.cognitoExchange(badRecorder, badBody)
	if badRecorder.Code != http.StatusBadRequest {
		t.Fatalf("malformed body status = %d, want 400", badRecorder.Code)
	}

	// The Next.js bridge sends snake_case JSON. Ensure id_token is decoded and
	// reaches verification instead of being mistaken for an empty credential.
	validShape := httptest.NewRequest(http.MethodPost, "/auth/cognito/exchange", strings.NewReader(`{"id_token":"not-a-jwt","remember":true}`))
	validShape.AddCookie(&http.Cookie{Name: csrfCookie, Value: "token-value"})
	validShape.Header.Set("X-CSRF-Token", "token-value")
	shapeRecorder := httptest.NewRecorder()
	gated.cognitoExchange(shapeRecorder, validShape)
	if shapeRecorder.Code != http.StatusUnauthorized {
		t.Fatalf("snake_case id_token status = %d, want 401 after verifier rejection", shapeRecorder.Code)
	}
}
