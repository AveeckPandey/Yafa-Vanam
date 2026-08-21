package httpserver

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"testing"
)

func TestValidRazorpaySignature(t *testing.T) {
	secret := "payment-test-secret"
	message := "order_A1|payment_B2"
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(message))
	signature := hex.EncodeToString(mac.Sum(nil))

	if !validRazorpaySignature(secret, message, signature) {
		t.Fatal("expected the valid Razorpay signature to verify")
	}
	if validRazorpaySignature(secret, message+"x", signature) {
		t.Fatal("a signature must be bound to the exact payment payload")
	}
	if validRazorpaySignature(secret, message, "not-hex") {
		t.Fatal("malformed signatures must be rejected")
	}
}
