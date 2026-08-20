package httpserver

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"runtime/debug"
	"strconv"
	"strings"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/auth"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
)

type Config struct {
	AllowedOrigins          []string
	Logger                  *slog.Logger
	Auth                    *auth.Handler
	RazorpayKeyID           string
	RazorpayKeySecret       string
	RazorpayWebhookSecret   string
	RazorpayCheckoutEnabled bool
}

type Server struct {
	catalog                 *commerce.Catalog
	store                   *commerce.Store
	logger                  *slog.Logger
	allowedOrigins          map[string]struct{}
	startedAt               time.Time
	razorpayKeyID           string
	razorpayKeySecret       string
	razorpayWebhookSecret   string
	razorpayCheckoutEnabled bool
}

type apiError struct {
	Error errorDetail `json:"error"`
}

type errorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func New(catalog *commerce.Catalog, store *commerce.Store, config Config) http.Handler {
	logger := config.Logger
	if logger == nil {
		logger = slog.Default()
	}
	server := &Server{
		catalog: catalog, store: store, logger: logger, startedAt: time.Now().UTC(),
		allowedOrigins:          make(map[string]struct{}),
		razorpayKeyID:           config.RazorpayKeyID,
		razorpayKeySecret:       config.RazorpayKeySecret,
		razorpayWebhookSecret:   config.RazorpayWebhookSecret,
		razorpayCheckoutEnabled: config.RazorpayCheckoutEnabled,
	}
	for _, origin := range config.AllowedOrigins {
		origin = strings.TrimSpace(origin)
		if origin != "" {
			server.allowedOrigins[origin] = struct{}{}
		}
	}

	mux := http.NewServeMux()
	if config.Auth != nil {
		config.Auth.Routes(mux)
	}
	mux.HandleFunc("GET /health", server.health)
	mux.HandleFunc("GET /ready", server.health)
	mux.HandleFunc("GET /api/v1", server.index)
	mux.HandleFunc("GET /api/v1/categories", server.categories)
	mux.HandleFunc("GET /api/v1/products", server.products)
	mux.HandleFunc("GET /api/v1/products/{slug}", server.product)
	mux.HandleFunc("POST /api/v1/payments/razorpay/orders", server.createRazorpayOrder)
	mux.HandleFunc("POST /api/v1/payments/razorpay/verify", server.verifyRazorpayPayment)
	mux.HandleFunc("POST /api/v1/payments/razorpay/webhook", server.razorpayWebhook)
	if config.Auth != nil {
		mux.Handle("POST /api/v1/carts", config.Auth.Middleware(http.HandlerFunc(server.createCart)))
		mux.Handle("GET /api/v1/carts/{cartID}", config.Auth.Middleware(http.HandlerFunc(server.getCart)))
		mux.Handle("POST /api/v1/carts/{cartID}/items", config.Auth.Middleware(http.HandlerFunc(server.addCartItem)))
		mux.Handle("PATCH /api/v1/carts/{cartID}/items/{variantID}", config.Auth.Middleware(http.HandlerFunc(server.setCartItem)))
		mux.Handle("DELETE /api/v1/carts/{cartID}/items/{variantID}", config.Auth.Middleware(http.HandlerFunc(server.removeCartItem)))
		mux.Handle("POST /api/v1/orders", config.Auth.Middleware(http.HandlerFunc(server.createOrder)))
		mux.Handle("GET /api/v1/orders/{orderNumber}", config.Auth.Middleware(http.HandlerFunc(server.getOrder)))
	} else {
		mux.HandleFunc("POST /api/v1/carts", server.createCart)
		mux.HandleFunc("GET /api/v1/carts/{cartID}", server.getCart)
		mux.HandleFunc("POST /api/v1/carts/{cartID}/items", server.addCartItem)
		mux.HandleFunc("PATCH /api/v1/carts/{cartID}/items/{variantID}", server.setCartItem)
		mux.HandleFunc("DELETE /api/v1/carts/{cartID}/items/{variantID}", server.removeCartItem)
		mux.HandleFunc("POST /api/v1/orders", server.createOrder)
		mux.HandleFunc("GET /api/v1/orders/{orderNumber}", server.getOrder)
	}
	mux.HandleFunc("/", server.notFound)

	return server.recoverPanic(server.securityHeaders(server.cors(server.requestLog(mux))))
}

func (server *Server) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"service": "yafa-api", "status": "ok", "catalogue_products": server.catalog.ProductCount(),
		"uptime_seconds": int64(time.Since(server.startedAt).Seconds()), "time": time.Now().UTC(),
	})
}

func (server *Server) index(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"name": "YAFA VANAM Commerce API", "version": "v1",
		"resources": []string{"categories", "products", "carts", "orders"},
	})
}

func (server *Server) categories(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"items": server.catalog.Categories()})
}

func (server *Server) products(w http.ResponseWriter, request *http.Request) {
	query := request.URL.Query()
	limit, _ := strconv.Atoi(query.Get("limit"))
	offset, _ := strconv.Atoi(query.Get("offset"))
	result := server.catalog.List(commerce.ProductFilter{
		Category: query.Get("category"), Subcategory: query.Get("subcategory"), Query: query.Get("q"),
		Limit: limit, Offset: offset,
	})
	writeJSON(w, http.StatusOK, result)
}

func (server *Server) product(w http.ResponseWriter, request *http.Request) {
	product, err := server.catalog.ProductBySlug(request.PathValue("slug"))
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, product)
}

func requestUser(request *http.Request) (auth.User, bool) {
	return auth.UserFromContext(request.Context())
}
func (server *Server) createCart(w http.ResponseWriter, request *http.Request) {
	if user, ok := requestUser(request); ok {
		writeJSON(w, http.StatusCreated, server.store.CreateCartForUser(user.ID))
		return
	}
	writeJSON(w, http.StatusCreated, server.store.CreateCart())
}

func (server *Server) getCart(w http.ResponseWriter, request *http.Request) {
	var cart commerce.CartView
	var err error
	if user, ok := requestUser(request); ok {
		cart, err = server.store.GetCartForUser(request.PathValue("cartID"), user.ID)
	} else {
		cart, err = server.store.GetCart(request.PathValue("cartID"))
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, cart)
}

func (server *Server) addCartItem(w http.ResponseWriter, request *http.Request) {
	var input struct {
		ProductID string `json:"product_id"`
		VariantID string `json:"variant_id"`
		Quantity  int    `json:"quantity"`
	}
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	var cart commerce.CartView
	var err error
	if user, ok := requestUser(request); ok {
		cart, err = server.store.AddCartItemForUser(user.ID, request.PathValue("cartID"), input.ProductID, input.VariantID, input.Quantity)
	} else {
		cart, err = server.store.AddCartItem(request.PathValue("cartID"), input.ProductID, input.VariantID, input.Quantity)
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, cart)
}

func (server *Server) setCartItem(w http.ResponseWriter, request *http.Request) {
	var input struct {
		Quantity int `json:"quantity"`
	}
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	var cart commerce.CartView
	var err error
	if user, ok := requestUser(request); ok {
		cart, err = server.store.SetCartItemForUser(user.ID, request.PathValue("cartID"), request.PathValue("variantID"), input.Quantity)
	} else {
		cart, err = server.store.SetCartItem(request.PathValue("cartID"), request.PathValue("variantID"), input.Quantity)
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, cart)
}

func (server *Server) removeCartItem(w http.ResponseWriter, request *http.Request) {
	var cart commerce.CartView
	var err error
	if user, ok := requestUser(request); ok {
		cart, err = server.store.RemoveCartItemForUser(user.ID, request.PathValue("cartID"), request.PathValue("variantID"))
	} else {
		cart, err = server.store.RemoveCartItem(request.PathValue("cartID"), request.PathValue("variantID"))
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, cart)
}

func (server *Server) createOrder(w http.ResponseWriter, request *http.Request) {
	var input commerce.CreateOrderInput
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", err.Error())
		return
	}
	idempotencyKey := strings.TrimSpace(request.Header.Get("Idempotency-Key"))
	if len(idempotencyKey) > 200 {
		writeError(w, http.StatusBadRequest, "invalid_idempotency_key", "Idempotency-Key must be 200 characters or fewer")
		return
	}
	var order commerce.Order
	var replayed bool
	var err error
	if user, ok := requestUser(request); ok {
		input.CustomerEmail = user.Email
		order, replayed, err = server.store.CreateOrderForUser(user.ID, input, idempotencyKey)
	} else {
		order, replayed, err = server.store.CreateOrder(input, idempotencyKey)
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	if replayed {
		w.Header().Set("Idempotent-Replayed", "true")
		writeJSON(w, http.StatusOK, order)
		return
	}
	writeJSON(w, http.StatusCreated, order)
}

func (server *Server) getOrder(w http.ResponseWriter, request *http.Request) {
	var order commerce.Order
	var err error
	if user, ok := requestUser(request); ok {
		order, err = server.store.GetOrderForUser(request.PathValue("orderNumber"), user.ID)
	} else {
		order, err = server.store.GetOrder(request.PathValue("orderNumber"), strings.TrimSpace(request.Header.Get("X-Order-Access-Token")))
	}
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, order)
}

func (server *Server) notFound(w http.ResponseWriter, _ *http.Request) {
	writeError(w, http.StatusNotFound, "not_found", "The requested API resource was not found.")
}

func (server *Server) writeDomainError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, commerce.ErrProductNotFound), errors.Is(err, commerce.ErrVariantNotFound),
		errors.Is(err, commerce.ErrCartNotFound), errors.Is(err, commerce.ErrOrderNotFound):
		writeError(w, http.StatusNotFound, "not_found", err.Error())
	case errors.Is(err, commerce.ErrVariantUnavailable), errors.Is(err, commerce.ErrInsufficientStock):
		writeError(w, http.StatusConflict, "variant_unavailable", err.Error())
	case errors.Is(err, commerce.ErrEmptyCart), errors.Is(err, commerce.ErrInvalidQuantity),
		errors.Is(err, commerce.ErrInvalidEmail), errors.Is(err, commerce.ErrInvalidAddress):
		writeError(w, http.StatusUnprocessableEntity, "validation_error", err.Error())
	case errors.Is(err, commerce.ErrOrderAccessDenied), errors.Is(err, commerce.ErrCartAccessDenied):
		writeError(w, http.StatusForbidden, "access_denied", "The order access token is missing or invalid.")
	default:
		server.logger.Error("unhandled domain error", "error", err)
		writeError(w, http.StatusInternalServerError, "internal_error", "An unexpected error occurred.")
	}
}

func decodeJSON(w http.ResponseWriter, request *http.Request, destination any) error {
	request.Body = http.MaxBytesReader(w, request.Body, 1<<20)
	decoder := json.NewDecoder(request.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(destination); err != nil {
		return fmt.Errorf("invalid JSON body: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return errors.New("request body must contain one JSON object")
	}
	return nil
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, apiError{Error: errorDetail{Code: code, Message: message}})
}

func (server *Server) requestLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, request)
		server.logger.Info("request", "method", request.Method, "path", request.URL.Path, "duration_ms", time.Since(started).Milliseconds())
	})
}

func (server *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		origin := request.Header.Get("Origin")
		if _, ok := server.allowedOrigins[origin]; origin != "" && ok {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key, X-Order-Access-Token, X-CSRF-Token")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
		}
		if request.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, request)
	})
}

func (server *Server) securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
		if request.TLS != nil {
			w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		}
		next.ServeHTTP(w, request)
	})
}

func (server *Server) recoverPanic(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				server.logger.Error("panic recovered", "panic", recovered, "stack", string(debug.Stack()))
				writeError(w, http.StatusInternalServerError, "internal_error", "An unexpected error occurred.")
			}
		}()
		next.ServeHTTP(w, request)
	})
}
