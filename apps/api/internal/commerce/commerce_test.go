package commerce

import (
	"errors"
	"path/filepath"
	"strings"
	"testing"
)

const testCatalogJSON = `[
  {
    "id":"p1","name":"Forest Tint","slug":"forest-tint","brand":"YAFA VANAM",
    "category":"Makeup","subcategory":"Lips","product_type":"Lip Tint","status":"active",
    "description":{"short":"A soft berry tint","full":"A buildable berry tint."},
    "commerce":{"currency":"INR","base_price":1200,"compare_at_price":null},
    "variants":[
      {"id":"v1","sku":"SKU-1","size":"4 ml","shade":{"name":"Berry","hex":"#884455"},"price":1200,"stock":4,"is_active":true},
      {"id":"v2","sku":"SKU-2","size":"4 ml","shade":{"name":"Rose","hex":"#cc7788"},"price":1250,"stock":0,"is_active":true}
    ],
    "images":{"primary":"/forest.png","gallery":[],"lifestyle":[],"detail":[],"texture":null,"alt":"Forest Tint","paths_verified":true},
    "benefits":["buildable"],"usage":{"how_to_use":"Apply","amount":null,"when":[]},"warnings":[],
    "ingredients":{"full_inci":null,"active_ingredients":[],"ingredient_data_note":null}
  },
  {
    "id":"draft","name":"Draft","slug":"draft","category":"Makeup","subcategory":"Lips",
    "product_type":"Lip Tint","status":"draft","commerce":{"currency":"INR","base_price":10},"variants":[]
  }
]`

func testCatalog(t *testing.T) *Catalog {
	t.Helper()
	catalog, err := DecodeCatalog(strings.NewReader(testCatalogJSON))
	if err != nil {
		t.Fatalf("DecodeCatalog() error = %v", err)
	}
	return catalog
}

func TestCatalogFiltersActiveProductsAndSearches(t *testing.T) {
	catalog := testCatalog(t)
	if catalog.ProductCount() != 1 {
		t.Fatalf("ProductCount() = %d, want 1", catalog.ProductCount())
	}
	result := catalog.List(ProductFilter{Query: "berry", Limit: 10})
	if result.Total != 1 || result.Items[0].ID != "p1" {
		t.Fatalf("List() = %#v, want p1", result)
	}
	if _, _, err := catalog.SellableVariant("p1", "v2"); !errors.Is(err, ErrVariantUnavailable) {
		t.Fatalf("SellableVariant() error = %v, want ErrVariantUnavailable", err)
	}
}

func TestRepositoryCatalogLoadsAllProducts(t *testing.T) {
	path := filepath.Join("..", "..", "..", "..", "data", "processed", "Product.json")
	catalog, err := LoadCatalog(path)
	if err != nil {
		t.Fatalf("LoadCatalog() error = %v", err)
	}
	if catalog.ProductCount() != 78 {
		t.Fatalf("ProductCount() = %d, want 78", catalog.ProductCount())
	}
}

func TestCartAndOrderFlow(t *testing.T) {
	store := NewStore(testCatalog(t))
	cart := store.CreateCart()
	updated, err := store.AddCartItem(cart.ID, "p1", "v1", 2)
	if err != nil {
		t.Fatalf("AddCartItem() error = %v", err)
	}
	if updated.ItemCount != 2 || updated.Subtotal != 2400 {
		t.Fatalf("cart = %#v, want 2 items and 2400 subtotal", updated)
	}
	if _, err := store.AddCartItem(cart.ID, "p1", "v1", 3); !errors.Is(err, ErrInsufficientStock) {
		t.Fatalf("AddCartItem() error = %v, want ErrInsufficientStock", err)
	}

	input := CreateOrderInput{
		CartID: cart.ID, CustomerEmail: "customer@example.com",
		DiscountCode:    "YAFA20",
		ShippingAddress: Address{RecipientName: "A Customer", Line1: "1 Forest Road", City: "Pune", StateRegion: "Maharashtra", PostalCode: "411001"},
	}
	order, replayed, err := store.CreateOrder(input, "checkout-1")
	if err != nil || replayed {
		t.Fatalf("CreateOrder() = replayed %v, error %v", replayed, err)
	}
	if order.TotalAmount != 1920 || order.DiscountAmount != 480 || order.ShippingAddress.CountryCode != "IN" || order.AccessToken == "" {
		t.Fatalf("order = %#v", order)
	}
	replayedOrder, replayed, err := store.CreateOrder(input, "checkout-1")
	if err != nil || !replayed || replayedOrder.OrderNumber != order.OrderNumber {
		t.Fatalf("idempotent CreateOrder() = %#v, replayed %v, error %v", replayedOrder, replayed, err)
	}
	if _, err := store.GetOrder(order.OrderNumber, "wrong"); !errors.Is(err, ErrOrderAccessDenied) {
		t.Fatalf("GetOrder() error = %v, want ErrOrderAccessDenied", err)
	}
	read, err := store.GetOrder(order.OrderNumber, order.AccessToken)
	if err != nil || read.AccessToken != "" {
		t.Fatalf("GetOrder() = %#v, error %v", read, err)
	}
	attached, err := store.AttachRazorpayOrder(order.OrderNumber, "order_razorpay_123")
	if err != nil || attached.RazorpayOrderID != "order_razorpay_123" {
		t.Fatalf("AttachRazorpayOrder() = %#v, error %v", attached, err)
	}
	verified, err := store.VerifyRazorpayPayment("order_razorpay_123", "pay_razorpay_123")
	if err != nil || verified.PaymentStatus != "AUTHORIZED" {
		t.Fatalf("VerifyRazorpayPayment() = %#v, error %v", verified, err)
	}
	captured, err := store.RecordRazorpayPayment("order_razorpay_123", "pay_razorpay_123", "captured")
	if err != nil || captured.PaymentStatus != "CAPTURED" || captured.OrderStatus != "PAID" {
		t.Fatalf("RecordRazorpayPayment() = %#v, error %v", captured, err)
	}
}
