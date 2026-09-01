package commerce

import (
	"errors"
	"strings"
	"testing"
)

func capturedRefundOrder(t *testing.T) (*Store, Order) {
	t.Helper()
	catalog, err := DecodeCatalog(strings.NewReader(`[{"id":"p1","name":"Tint","slug":"tint","category":"Makeup","subcategory":"Lips","product_type":"Tint","status":"active","commerce":{"currency":"INR","base_price":1000},"variants":[{"id":"v1","price":1000,"stock":20,"is_active":true}],"images":{"paths_verified":false}}]`))
	if err != nil {
		t.Fatal(err)
	}
	store := NewStore(catalog)
	cart, err := store.CreateCart()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.AddCartItem(cart.ID, "p1", "v1", 1); err != nil {
		t.Fatal(err)
	}
	order, _, err := store.CreateOrder(CreateOrderInput{CartID: cart.ID, CustomerEmail: "customer@example.com", ShippingAddress: Address{RecipientName: "Customer", Line1: "1 Test Road", City: "Mumbai", StateRegion: "Maharashtra", PostalCode: "400001", CountryCode: "IN"}}, "checkout-1")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.AttachRazorpayOrder(order.OrderNumber, "order_refund_test"); err != nil {
		t.Fatal(err)
	}
	order, err = store.RecordRazorpayPayment("order_refund_test", "pay_refund_test", "captured")
	if err != nil {
		t.Fatal(err)
	}
	return store, order
}

func TestRefundsAreIdempotentAndCannotExceedCapturedAmount(t *testing.T) {
	store, order := capturedRefundOrder(t)
	partial, replayed, err := store.PrepareRefund(order.OrderNumber, 50000, "customer return", "refund-1", "YVR-1")
	if err != nil || replayed || partial.AmountPaise != 50000 {
		t.Fatalf("PrepareRefund() = %#v, replayed=%v, err=%v", partial, replayed, err)
	}
	if _, _, err := store.PrepareRefund(order.OrderNumber, 70000, "too much", "refund-2", "YVR-2"); !errors.Is(err, ErrRefundAmountInvalid) {
		t.Fatalf("excess refund error = %v, want ErrRefundAmountInvalid", err)
	}
	processed, err := store.CompleteRefund("refund-1", "rfnd_partial", "processed")
	if err != nil || processed.Status != "PROCESSED" {
		t.Fatalf("CompleteRefund() = %#v, err=%v", processed, err)
	}
	replayedRefund, replayed, err := store.PrepareRefund(order.OrderNumber, 50000, "customer return", "refund-1", "YVR-1")
	if err != nil || !replayed || replayedRefund.ProviderRefundID != "rfnd_partial" {
		t.Fatalf("replay = %#v, replayed=%v, err=%v", replayedRefund, replayed, err)
	}
	remaining, _, err := store.PrepareRefund(order.OrderNumber, 0, "remaining amount", "refund-2", "YVR-2")
	if err != nil || remaining.AmountPaise != 69900 {
		t.Fatalf("remaining refund = %#v, err=%v", remaining, err)
	}
	if _, err := store.CompleteRefund("refund-2", "rfnd_full", "processed"); err != nil {
		t.Fatal(err)
	}
	if store.orders[order.OrderNumber].PaymentStatus != "REFUNDED" || store.orders[order.OrderNumber].OrderStatus != "REFUNDED" {
		t.Fatalf("order state = %s/%s", store.orders[order.OrderNumber].PaymentStatus, store.orders[order.OrderNumber].OrderStatus)
	}
}

func TestRefundRequiresCapturedPaymentAndStableIdempotencyDetails(t *testing.T) {
	store, order := capturedRefundOrder(t)
	if _, _, err := store.PrepareRefund(order.OrderNumber, 1000, "first", "refund-key", "YVR-key"); err != nil {
		t.Fatal(err)
	}
	if _, _, err := store.PrepareRefund(order.OrderNumber, 2000, "different", "refund-key", "YVR-key"); !errors.Is(err, ErrRefundIdempotencyConflict) {
		t.Fatalf("idempotency mismatch error = %v", err)
	}

	uncaptured := *store.orders[order.OrderNumber]
	uncaptured.OrderNumber = "YV-UNCAPTURED"
	uncaptured.PaymentStatus = "AUTHORIZED"
	store.orders[uncaptured.OrderNumber] = &uncaptured
	if _, _, err := store.PrepareRefund(uncaptured.OrderNumber, 1000, "not captured", "refund-uncaptured", "YVR-uncaptured"); !errors.Is(err, ErrRefundNotSupported) {
		t.Fatalf("uncaptured refund error = %v", err)
	}
}
