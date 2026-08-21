package httpserver

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

func TestCommerceHTTPFlow(t *testing.T) {
	catalog, err := commerce.DecodeCatalog(strings.NewReader(`[{"id":"p1","name":"Tint","slug":"tint","category":"Makeup","subcategory":"Lips","product_type":"Tint","status":"active","commerce":{"currency":"INR","base_price":1000},"variants":[{"id":"v1","price":1000,"stock":2,"is_active":true}],"images":{"paths_verified":false}}]`))
	if err != nil {
		t.Fatal(err)
	}
	handler := New(catalog, commerce.NewStore(catalog), Config{})

	create := httptest.NewRecorder()
	handler.ServeHTTP(create, httptest.NewRequest(http.MethodPost, "/api/v1/carts", nil))
	if create.Code != http.StatusCreated {
		t.Fatalf("create cart status = %d, body = %s", create.Code, create.Body.String())
	}
	var cart struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(create.Body.Bytes(), &cart); err != nil || cart.ID == "" {
		t.Fatalf("create cart body = %s, error = %v", create.Body.String(), err)
	}

	add := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/carts/"+cart.ID+"/items", strings.NewReader(`{"product_id":"p1","variant_id":"v1","quantity":2}`))
	request.Header.Set("Content-Type", "application/json")
	handler.ServeHTTP(add, request)
	if add.Code != http.StatusOK || !strings.Contains(add.Body.String(), `"item_count":2`) {
		t.Fatalf("add item status = %d, body = %s", add.Code, add.Body.String())
	}

	unknown := httptest.NewRecorder()
	handler.ServeHTTP(unknown, httptest.NewRequest(http.MethodGet, "/api/v1/products/missing", nil))
	if unknown.Code != http.StatusNotFound || !strings.Contains(unknown.Body.String(), `"code":"not_found"`) {
		t.Fatalf("missing product status = %d, body = %s", unknown.Code, unknown.Body.String())
	}
}

func TestPaymentRateLimitIsBoundedPerClient(t *testing.T) {
	server := &Server{clientRates: make(map[string]*clientRate)}
	request := httptest.NewRequest(http.MethodPost, "/api/v1/payments/razorpay/orders", nil)
	bucket, limit := requestLimitBucket(request)
	if limit != 20 {
		t.Fatalf("payment limit = %d, want 20", limit)
	}
	for attempt := 0; attempt < limit; attempt++ {
		if !server.allowRequest(context.Background(), bucket, limit) {
			t.Fatalf("payment request %d should have been allowed", attempt+1)
		}
	}
	if server.allowRequest(context.Background(), bucket, limit) {
		t.Fatal("payment requests above the burst limit must be rejected")
	}
}
