package httpserver

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/auth"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/yafa"
	"github.com/redis/go-redis/v9"
	"golang.org/x/time/rate"
)

type Config struct {
	AllowedOrigins          []string
	Logger                  *slog.Logger
	DependencyHealth        func(context.Context) map[string]string
	RateLimitStore          redis.UniversalClient
	PanicReporter           func(*http.Request, any, []byte)
	Auth                    *auth.Handler
	Yafa                    *yafa.Service
	RazorpayKeyID           string
	RazorpayKeySecret       string
	RazorpayWebhookSecret   string
	RazorpayCheckoutEnabled bool
	InternalServiceToken    string
}

type Server struct {
	catalog                 *commerce.Catalog
	store                   commerce.CommerceStore
	logger                  *slog.Logger
	allowedOrigins          map[string]struct{}
	startedAt               time.Time
	dependencyHealth        func(context.Context) map[string]string
	rateLimitStore          redis.UniversalClient
	panicReporter           func(*http.Request, any, []byte)
	razorpayKeyID           string
	razorpayKeySecret       string
	razorpayWebhookSecret   string
	razorpayCheckoutEnabled bool
	razorpayMu              sync.Mutex
	internalServiceToken    string
	yafa                    *yafa.Service
	rateMu                  sync.Mutex
	clientRates             map[string]*clientRate
}

type clientRate struct {
	limiter *rate.Limiter
	seenAt  time.Time
}

type apiError struct {
	Error errorDetail `json:"error"`
}

type errorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func New(catalog *commerce.Catalog, store commerce.CommerceStore, config Config) http.Handler {
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
		internalServiceToken:    config.InternalServiceToken,
		yafa:                    config.Yafa,
		clientRates:             make(map[string]*clientRate),
		dependencyHealth:        config.DependencyHealth,
		rateLimitStore:          config.RateLimitStore,
		panicReporter:           config.PanicReporter,
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
	mux.HandleFunc("POST /api/v1/yafa/transcribe", server.yafaTranscribe)
	if config.Auth != nil {
		mux.Handle("POST /api/v1/payments/razorpay/orders", config.Auth.Middleware(http.HandlerFunc(server.createRazorpayOrder)))
		mux.Handle("POST /api/v1/payments/razorpay/verify", config.Auth.Middleware(http.HandlerFunc(server.verifyRazorpayPayment)))
	} else {
		mux.HandleFunc("POST /api/v1/payments/razorpay/orders", server.createRazorpayOrder)
		mux.HandleFunc("POST /api/v1/payments/razorpay/verify", server.verifyRazorpayPayment)
	}
	mux.HandleFunc("POST /api/v1/payments/razorpay/webhook", server.razorpayWebhook)
	// Machine-to-machine routes (welcome-coupon Lambda). Guarded by the shared
	// service token, not user sessions — fail closed when unconfigured.
	mux.Handle("POST /api/internal/coupons/welcome", server.internalGuard(http.HandlerFunc(server.issueWelcomeCoupon)))
	mux.Handle("POST /api/internal/messages/record", server.internalGuard(http.HandlerFunc(server.recordLifecycleMessage)))
	if config.Auth != nil {
		mux.Handle("GET /api/v1/me/beauty-profile", config.Auth.Middleware(http.HandlerFunc(server.yafaBeautyProfile)))
		mux.Handle("POST /api/v1/yafa/session/start", config.Auth.OptionalMiddleware(http.HandlerFunc(server.startYafaSession)))
		mux.Handle("PATCH /api/v1/yafa/session/{sessionID}/answer", config.Auth.OptionalMiddleware(http.HandlerFunc(server.saveYafaAnswer)))
		mux.Handle("POST /api/v1/yafa/session/{sessionID}/selfie", config.Auth.OptionalMiddleware(http.HandlerFunc(server.uploadYafaSelfie)))
		mux.Handle("POST /api/v1/yafa/session/{sessionID}/analyze", config.Auth.OptionalMiddleware(http.HandlerFunc(server.analyzeYafaSession)))
		mux.Handle("POST /api/v1/yafa/session/{sessionID}/confirm", config.Auth.OptionalMiddleware(http.HandlerFunc(server.confirmYafaShade)))
		mux.Handle("POST /api/v1/yafa/confirm-shade", config.Auth.OptionalMiddleware(http.HandlerFunc(server.confirmYafaShade)))
	} else {
		mux.HandleFunc("POST /api/v1/yafa/session/start", server.startYafaSession)
		mux.HandleFunc("PATCH /api/v1/yafa/session/{sessionID}/answer", server.saveYafaAnswer)
		mux.HandleFunc("POST /api/v1/yafa/session/{sessionID}/selfie", server.uploadYafaSelfie)
		mux.HandleFunc("POST /api/v1/yafa/session/{sessionID}/analyze", server.analyzeYafaSession)
		mux.HandleFunc("POST /api/v1/yafa/session/{sessionID}/confirm", server.confirmYafaShade)
		mux.HandleFunc("POST /api/v1/yafa/confirm-shade", server.confirmYafaShade)
	}
	if config.Auth != nil {
		mux.Handle("POST /api/v1/carts", config.Auth.OptionalMiddleware(http.HandlerFunc(server.createCart)))
		mux.Handle("GET /api/v1/carts/{cartID}", config.Auth.OptionalMiddleware(http.HandlerFunc(server.getCart)))
		mux.Handle("POST /api/v1/carts/{cartID}/items", config.Auth.OptionalMiddleware(http.HandlerFunc(server.addCartItem)))
		mux.Handle("PATCH /api/v1/carts/{cartID}/items/{variantID}", config.Auth.OptionalMiddleware(http.HandlerFunc(server.setCartItem)))
		mux.Handle("DELETE /api/v1/carts/{cartID}/items/{variantID}", config.Auth.OptionalMiddleware(http.HandlerFunc(server.removeCartItem)))
		mux.Handle("POST /api/v1/orders", config.Auth.Middleware(http.HandlerFunc(server.createOrder)))
		mux.Handle("GET /api/v1/orders", config.Auth.Middleware(http.HandlerFunc(server.listOrders)))
		mux.Handle("GET /api/v1/orders/{orderNumber}", config.Auth.Middleware(http.HandlerFunc(server.getOrder)))
	} else {
		mux.HandleFunc("POST /api/v1/carts", server.createCart)
		mux.HandleFunc("GET /api/v1/carts/{cartID}", server.getCart)
		mux.HandleFunc("POST /api/v1/carts/{cartID}/items", server.addCartItem)
		mux.HandleFunc("PATCH /api/v1/carts/{cartID}/items/{variantID}", server.setCartItem)
		mux.HandleFunc("DELETE /api/v1/carts/{cartID}/items/{variantID}", server.removeCartItem)
		mux.HandleFunc("POST /api/v1/orders", server.createOrder)
		mux.HandleFunc("GET /api/v1/orders", server.listOrders)
		mux.HandleFunc("GET /api/v1/orders/{orderNumber}", server.getOrder)
	}
	mux.HandleFunc("/", server.notFound)

	var handler http.Handler = mux
	handler = server.requestLog(handler)
	if config.Auth != nil {
		handler = config.Auth.OptionalMiddleware(handler)
		handler = config.Auth.CSRFMiddleware(handler)
	}
	return server.recoverPanic(server.securityHeaders(server.cors(server.rateLimit(handler))))
}

func (server *Server) health(w http.ResponseWriter, request *http.Request) {
	dependencies := map[string]string{}
	if server.dependencyHealth != nil {
		dependencies = server.dependencyHealth(request.Context())
	}
	status := "ok"
	for _, value := range dependencies {
		if value != "ok" {
			status = "degraded"
			break
		}
	}
	response := map[string]any{"service": "yafa-api", "status": status, "catalogue_products": server.catalog.ProductCount(), "uptime_seconds": int64(time.Since(server.startedAt).Seconds()), "time": time.Now().UTC()}
	for name, value := range dependencies {
		response[name] = value
	}
	if status != "ok" {
		writeJSON(w, http.StatusServiceUnavailable, response)
		return
	}
	writeJSON(w, http.StatusOK, response)
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
		cart, err := server.store.CreateCartForUser(user.ID)
		if err != nil {
			server.writeDomainError(w, err)
			return
		}
		writeJSON(w, http.StatusCreated, cart)
		return
	}
	cart, err := server.store.CreateCart()
	if err != nil {
		server.writeDomainError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, cart)
}

func (server *Server) getCart(w http.ResponseWriter, request *http.Request) {
	var cart commerce.CartView
	var err error
	if user, ok := requestUser(request); ok {
		if err = server.store.ClaimCartForUser(request.PathValue("cartID"), user.ID); err != nil {
			server.writeDomainError(w, err)
			return
		}
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
		if err := server.store.ClaimCartForUser(request.PathValue("cartID"), user.ID); err != nil {
			server.writeDomainError(w, err)
			return
		}
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
		if err := server.store.ClaimCartForUser(request.PathValue("cartID"), user.ID); err != nil {
			server.writeDomainError(w, err)
			return
		}
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
		if err := server.store.ClaimCartForUser(request.PathValue("cartID"), user.ID); err != nil {
			server.writeDomainError(w, err)
			return
		}
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

func (server *Server) listOrders(w http.ResponseWriter, request *http.Request) {
	user, ok := requestUser(request)
	if !ok {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Sign in is required to continue.")
		return
	}
	writeJSON(w, http.StatusOK, server.store.ListOrdersForUser(user.ID))
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
		requestID := requestID(request.Header.Get("X-Request-ID"))
		w.Header().Set("X-Request-ID", requestID)
		recorder := &statusRecorder{ResponseWriter: w}
		next.ServeHTTP(recorder, request)
		status := recorder.status
		if status == 0 {
			status = http.StatusOK
		}
		userID := "anonymous"
		if user, ok := requestUser(request); ok {
			userID = user.ID
		}
		server.logger.Info("request", "request_id", requestID, "method", request.Method, "path", request.URL.Path, "status_code", status, "latency_ms", time.Since(started).Milliseconds(), "user_id", userID)
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (recorder *statusRecorder) WriteHeader(status int) {
	recorder.status = status
	recorder.ResponseWriter.WriteHeader(status)
}

func (recorder *statusRecorder) Write(body []byte) (int, error) {
	if recorder.status == 0 {
		recorder.status = http.StatusOK
	}
	return recorder.ResponseWriter.Write(body)
}

func requestID(incoming string) string {
	incoming = strings.TrimSpace(incoming)
	if len(incoming) > 0 && len(incoming) <= 100 {
		valid := true
		for _, character := range incoming {
			if !((character >= 'a' && character <= 'z') || (character >= 'A' && character <= 'Z') || (character >= '0' && character <= '9') || character == '-' || character == '_') {
				valid = false
				break
			}
		}
		if valid {
			return incoming
		}
	}
	bytes := make([]byte, 16)
	if _, err := rand.Read(bytes); err == nil {
		return hex.EncodeToString(bytes)
	}
	return strconv.FormatInt(time.Now().UnixNano(), 36)
}

func (server *Server) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		origin := request.Header.Get("Origin")
		if _, ok := server.allowedOrigins[origin]; origin != "" && ok {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key, X-Order-Access-Token, X-CSRF-Token, X-Yafa-Session-Token")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
		}
		if request.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, request)
	})
}

func (server *Server) rateLimit(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		if request.Method == http.MethodOptions || request.URL.Path == "/health" || request.URL.Path == "/ready" {
			next.ServeHTTP(w, request)
			return
		}
		bucket, perMinute := requestLimitBucket(request)
		if !server.allowRequest(request.Context(), bucket, perMinute) {
			w.Header().Set("Retry-After", "60")
			writeError(w, http.StatusTooManyRequests, "rate_limited", "Too many requests. Please try again shortly.")
			return
		}
		next.ServeHTTP(w, request)
	})
}

func requestLimitBucket(request *http.Request) (string, int) {
	path := request.URL.Path
	class, perMinute := "api", 100
	if strings.HasPrefix(path, "/auth/") {
		class, perMinute = "auth", 10
	} else if strings.HasPrefix(path, "/api/v1/payments/") {
		class, perMinute = "payments", 20
	}
	host, _, err := net.SplitHostPort(request.RemoteAddr)
	if err != nil || host == "" {
		host = request.RemoteAddr
	}
	return class + ":" + host, perMinute
}

func (server *Server) allowRequest(ctx context.Context, bucket string, perMinute int) bool {
	if server.rateLimitStore != nil {
		key := "yafa:ratelimit:" + bucket
		count, err := server.rateLimitStore.Incr(ctx, key).Result()
		if err == nil {
			if count == 1 {
				_ = server.rateLimitStore.Expire(ctx, key, time.Minute).Err()
			}
			return count <= int64(perMinute)
		}
		server.logger.Error("rate limit store unavailable; using local fallback", "error", err)
	}
	now := time.Now()
	server.rateMu.Lock()
	defer server.rateMu.Unlock()
	if len(server.clientRates) > 2_048 {
		for key, value := range server.clientRates {
			if now.Sub(value.seenAt) > 10*time.Minute {
				delete(server.clientRates, key)
			}
		}
	}
	entry := server.clientRates[bucket]
	if entry == nil {
		entry = &clientRate{limiter: rate.NewLimiter(rate.Limit(float64(perMinute)/60), perMinute)}
		server.clientRates[bucket] = entry
	}
	entry.seenAt = now
	return entry.limiter.Allow()
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
				stack := debug.Stack()
				if server.panicReporter != nil {
					server.panicReporter(request, recovered, stack)
				}
				server.logger.Error("panic recovered", "panic", recovered, "stack", string(stack))
				writeError(w, http.StatusInternalServerError, "internal_error", "An unexpected error occurred.")
			}
		}()
		next.ServeHTTP(w, request)
	})
}
