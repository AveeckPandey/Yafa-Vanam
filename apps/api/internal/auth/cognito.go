package auth

import (
	"context"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// CognitoVerifier validates AWS Cognito id_tokens against the user pool's
// published signing keys. It is the server-side half of the storefront bridge:
// the browser authenticates with Cognito, then POST /auth/cognito/exchange
// trades a verified id_token for first-party session cookies. The Go API never
// sees the Cognito client secret — verification is purely public-key.
type CognitoVerifier struct {
	issuer, clientID, jwksURL string
	httpClient                *http.Client

	mu        sync.RWMutex
	keys      map[string]*rsa.PublicKey // kid -> public key
	fetchedAt time.Time                 // successful fetch, drives the read-path TTL
}

const (
	jwksCacheTTL           = time.Hour
	jwksFetchTimeout       = 5 * time.Second
	cognitoClockSkewLeeway = 30 * time.Second
)

type cognitoIdentity struct {
	Subject string
	Name    string
	Email   string
}

// NewCognitoVerifier returns nil unless every pool setting is present, so a
// partially configured deployment keeps the exchange endpoint disabled (503)
// instead of half-working.
func NewCognitoVerifier(region, userPoolID, clientID string) *CognitoVerifier {
	region, userPoolID, clientID = strings.TrimSpace(region), strings.TrimSpace(userPoolID), strings.TrimSpace(clientID)
	if region == "" || userPoolID == "" || clientID == "" {
		return nil
	}
	return newCognitoVerifier(fmt.Sprintf("https://cognito-idp.%s.amazonaws.com/%s", region, userPoolID), clientID)
}

// newCognitoVerifier lets tests point the verifier at an httptest JWKS server.
func newCognitoVerifier(issuer, clientID string) *CognitoVerifier {
	if issuer == "" || clientID == "" {
		return nil
	}
	return &CognitoVerifier{
		issuer:     issuer,
		clientID:   clientID,
		jwksURL:    issuer + "/.well-known/jwks.json",
		httpClient: &http.Client{Timeout: jwksFetchTimeout},
	}
}

// SetCognitoVerifier wires the verifier into the handler after construction,
// mirroring yafa.Service.SetInfrastructure.
func (h *Handler) SetCognitoVerifier(v *CognitoVerifier) { h.cognito = v }

func (v *CognitoVerifier) Verify(rawToken string) (cognitoIdentity, error) {
	claims := jwt.MapClaims{}
	// One forced JWKS refresh is allowed per verification: the retry parse may
	// recover a rotated key but can never trigger a second fetch. The exchange
	// endpoint's rate limiter bounds how often even that single fetch happens.
	forcedRefreshed := false
	parse := func() error {
		_, err := jwt.ParseWithClaims(rawToken, claims, func(t *jwt.Token) (any, error) {
			return v.keyFunc(t, &forcedRefreshed)
		},
			jwt.WithValidMethods([]string{jwt.SigningMethodRS256.Alg()}),
			jwt.WithIssuer(v.issuer),
			jwt.WithAudience(v.clientID),
			jwt.WithExpirationRequired(),
			jwt.WithLeeway(cognitoClockSkewLeeway))
		return err
	}
	err := parse()
	if errors.Is(err, errUnknownSigningKey) {
		err = parse()
	}
	if err != nil {
		return cognitoIdentity{}, fmt.Errorf("invalid cognito id_token: %w", err)
	}
	// token_use distinguishes id_tokens from access_tokens; only an id_token
	// carries the email/identity claims this bridge upserts with.
	if use, _ := claims["token_use"].(string); use != "id" {
		return cognitoIdentity{}, errors.New("cognito token is not an id_token")
	}
	subject, _ := claims["sub"].(string)
	email, _ := claims["email"].(string)
	if subject == "" || email == "" {
		return cognitoIdentity{}, errors.New("cognito id_token is missing sub or email")
	}
	switch verified := claims["email_verified"].(type) {
	case bool:
		if !verified {
			return cognitoIdentity{}, errors.New("cognito account email is not verified")
		}
	case string:
		if strings.EqualFold(verified, "false") {
			return cognitoIdentity{}, errors.New("cognito account email is not verified")
		}
	}
	name, _ := claims["name"].(string)
	if name == "" {
		name, _ = claims["cognito:username"].(string)
	}
	if name == "" {
		name = email
	}
	return cognitoIdentity{Subject: subject, Name: name, Email: strings.ToLower(email)}, nil
}

var errUnknownSigningKey = errors.New("unknown cognito signing key")

func (v *CognitoVerifier) keyFunc(t *jwt.Token, forcedRefreshed *bool) (any, error) {
	kid, _ := t.Header["kid"].(string)
	if kid == "" {
		return nil, errors.New("token header is missing kid")
	}
	if key, ok := v.lookup(kid); ok {
		return key, nil
	}
	// Cache miss: pool keys may have rotated. Fetch once per verification; a
	// still-unknown kid after that fails without further fetches.
	v.mu.Lock()
	var fetchErr error
	if !*forcedRefreshed {
		*forcedRefreshed = true
		fetchErr = v.fetchKeysLocked()
	}
	key, ok := v.keys[kid]
	v.mu.Unlock()
	if !ok {
		if fetchErr != nil {
			return nil, fmt.Errorf("jwks refresh failed: %w", fetchErr)
		}
		return nil, errUnknownSigningKey
	}
	return key, nil
}

func (v *CognitoVerifier) lookup(kid string) (*rsa.PublicKey, bool) {
	v.mu.RLock()
	defer v.mu.RUnlock()
	if time.Since(v.fetchedAt) > jwksCacheTTL {
		return nil, false
	}
	key, ok := v.keys[kid]
	return key, ok
}

func (v *CognitoVerifier) fetchKeysLocked() error {
	ctx, cancel := context.WithTimeout(context.Background(), jwksFetchTimeout)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, v.jwksURL, nil)
	if err != nil {
		return err
	}
	response, err := v.httpClient.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("jwks endpoint returned %d", response.StatusCode)
	}
	var payload struct {
		Keys []struct {
			Kid string `json:"kid"`
			Kty string `json:"kty"`
			N   string `json:"n"`
			E   string `json:"e"`
		} `json:"keys"`
	}
	if json.NewDecoder(response.Body).Decode(&payload) != nil {
		return errors.New("unreadable jwks document")
	}
	keys := make(map[string]*rsa.PublicKey, len(payload.Keys))
	for _, k := range payload.Keys {
		if k.Kty != "RSA" || k.N == "" || k.E == "" {
			continue
		}
		n, err := decodeBigInt(k.N)
		e, eErr := decodeBigInt(k.E)
		if err != nil || eErr != nil || !e.IsInt64() || e.Int64() <= 1 || e.Int64() > 1<<31 {
			continue
		}
		keys[k.Kid] = &rsa.PublicKey{N: n, E: int(e.Int64())}
	}
	v.keys = keys
	v.fetchedAt = time.Now()
	return nil
}

func decodeBigInt(value string) (*big.Int, error) {
	raw, err := base64.RawURLEncoding.DecodeString(value)
	if err != nil {
		return nil, err
	}
	return new(big.Int).SetBytes(raw), nil
}
