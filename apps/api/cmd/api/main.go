package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/auth"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/database"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/yafa"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/platform/httpserver"
	"github.com/getsentry/sentry-go"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	catalogPath, err := commerce.ResolveCatalogPath(os.Getenv("YAFA_CATALOGUE_PATH"))
	if err != nil {
		logger.Error("catalogue configuration failed", "error", err)
		os.Exit(1)
	}
	catalog, err := commerce.LoadCatalog(catalogPath)
	if err != nil {
		logger.Error("catalogue load failed", "path", catalogPath, "error", err)
		os.Exit(1)
	}

	port := strings.TrimSpace(os.Getenv("API_PORT"))
	if port == "" {
		port = strings.TrimSpace(os.Getenv("PORT"))
	}
	if port == "" {
		port = "4000"
	}
	environment := envOrDefault("ENVIRONMENT", envOrDefault("APP_ENV", "development"))
	production := strings.EqualFold(environment, "production")
	if sentryDSN := strings.TrimSpace(os.Getenv("SENTRY_DSN")); sentryDSN != "" {
		if err := sentry.Init(sentry.ClientOptions{Dsn: sentryDSN, Environment: environment, Release: strings.TrimSpace(os.Getenv("RELEASE_VERSION")), AttachStacktrace: true, TracesSampleRate: 0.1}); err != nil {
			logger.Error("Sentry initialization failed", "error", err)
			if production {
				os.Exit(1)
			}
		} else {
			defer sentry.Flush(2 * time.Second)
		}
	}
	rawOrigins := strings.TrimSpace(os.Getenv("CORS_ALLOWED_ORIGINS"))
	if production && rawOrigins == "" {
		logger.Error("CORS_ALLOWED_ORIGINS is required in production")
		os.Exit(1)
	}
	origins := strings.Split(envOrDefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000"), ",")
	var authHandler *auth.Handler
	var yafaService *yafa.Service
	var healthDB *pgxpool.Pool
	var healthRedis *redis.Client
	if databaseURL, redisURL, secret := strings.TrimSpace(os.Getenv("DATABASE_URL")), strings.TrimSpace(os.Getenv("REDIS_URL")), strings.TrimSpace(os.Getenv("JWT_SECRET")); databaseURL != "" && redisURL != "" && len(secret) >= 32 {
		db, dbErr := pgxpool.New(context.Background(), databaseURL)
		redisOptions, redisErr := redis.ParseURL(redisURL)
		if dbErr != nil || redisErr != nil {
			logger.Error("auth configuration failed", "database_error", dbErr, "redis_error", redisErr)
			os.Exit(1)
		}
		redisClient := redis.NewClient(redisOptions)
		if err := db.Ping(context.Background()); err != nil {
			logger.Error("auth database unavailable", "error", err)
			os.Exit(1)
		}
		if err := database.ApplyPending(context.Background(), db, envOrDefault("MIGRATIONS_PATH", "db/migrations")); err != nil {
			logger.Error("database migration failed", "error", err)
			os.Exit(1)
		}
		if err := redisClient.Ping(context.Background()).Err(); err != nil {
			logger.Error("auth redis unavailable", "error", err)
			os.Exit(1)
		}
		defer db.Close()
		defer redisClient.Close()
		healthDB, healthRedis = db, redisClient
		authHandler = auth.NewHandler(auth.New(db, redisClient, auth.Config{JWTSecret: secret, SecureCookies: production, AccessTTL: 15 * time.Minute, RefreshTTL: 24 * time.Hour, RememberRefreshTTL: 30 * 24 * time.Hour}), os.Getenv("GOOGLE_CLIENT_ID"), os.Getenv("GOOGLE_CLIENT_SECRET"), os.Getenv("GOOGLE_CALLBACK_URL"), envOrDefault("APP_URL", "http://localhost:3000"), auth.NewSMTPMailer(os.Getenv("SMTP_HOST"), os.Getenv("SMTP_PORT"), os.Getenv("SMTP_USERNAME"), os.Getenv("SMTP_PASSWORD"), os.Getenv("SMTP_FROM")))
		yafaService = yafa.New(db)
		storage, storageErr := yafa.NewStorage(context.Background(), yafa.StorageConfig{Endpoint: strings.TrimSpace(os.Getenv("YAFA_STORAGE_ENDPOINT")), Region: strings.TrimSpace(os.Getenv("YAFA_STORAGE_REGION")), Bucket: strings.TrimSpace(os.Getenv("YAFA_STORAGE_BUCKET")), AccessKeyID: strings.TrimSpace(os.Getenv("YAFA_STORAGE_ACCESS_KEY_ID")), SecretAccessKey: strings.TrimSpace(os.Getenv("YAFA_STORAGE_SECRET_ACCESS_KEY"))})
		analyzer, analyzerErr := yafa.NewAnalyzer(strings.TrimSpace(os.Getenv("YAFA_ANALYZER_URL")), strings.TrimSpace(os.Getenv("YAFA_INTERNAL_SERVICE_TOKEN")))
		if storageErr == nil && analyzerErr == nil {
			yafaService.SetInfrastructure(storage, analyzer)
		} else if production {
			// Railway's log view can hide structured fields, so retain the safe error
			// descriptions in the message itself. Neither constructor includes a
			// credential value in its error text.
			logger.Error(fmt.Sprintf("Yafa configuration failed: storage=%v; analyzer=%v", storageErr, analyzerErr))
			os.Exit(1)
		} else {
			logger.Warn("Yafa selfie analysis disabled until private storage and analyzer are configured")
		}
	} else if production {
		logger.Error("database, Redis, and a 32+ character JWT_SECRET are required in production")
		os.Exit(1)
	} else {
		logger.Warn("authentication disabled: set DATABASE_URL, REDIS_URL, and a 32+ character JWT_SECRET to enable it")
	}
	// Carts, orders, and payments must survive restarts and deploys, so they
	// persist through PostgreSQL whenever a pool is configured. Without one
	// the process falls back to the ephemeral in-memory store for local
	// development and says so loudly rather than silently losing checkouts.
	var commerceStore commerce.CommerceStore = commerce.NewStore(catalog)
	if healthDB != nil {
		commerceStore = commerce.NewPostgresStore(healthDB, catalog)
		logger.Info("commerce persistence enabled", "backend", "postgresql")
	} else {
		logger.Warn("commerce carts/orders are EPHEMERAL (in-memory): configure DATABASE_URL to persist them across restarts")
	}
	if production && strings.EqualFold(strings.TrimSpace(os.Getenv("RAZORPAY_CHECKOUT_ENABLED")), "true") && (strings.TrimSpace(os.Getenv("RAZORPAY_KEY_ID")) == "" || strings.TrimSpace(os.Getenv("RAZORPAY_KEY_SECRET")) == "" || strings.TrimSpace(os.Getenv("RAZORPAY_WEBHOOK_SECRET")) == "") {
		logger.Error("Razorpay checkout is enabled but payment secrets are incomplete")
		os.Exit(1)
	}
	dependencyHealth := func(ctx context.Context) map[string]string {
		result := map[string]string{"db": "unconfigured", "redis": "unconfigured"}
		if healthDB != nil {
			result["db"] = "ok"
			if err := healthDB.Ping(ctx); err != nil {
				result["db"] = "error"
			}
		}
		if healthRedis != nil {
			result["redis"] = "ok"
			if err := healthRedis.Ping(ctx).Err(); err != nil {
				result["redis"] = "error"
			}
		}
		return result
	}
	handler := httpserver.New(catalog, commerceStore, httpserver.Config{
		AllowedOrigins: origins, Logger: logger, DependencyHealth: dependencyHealth, RateLimitStore: healthRedis, Auth: authHandler, Yafa: yafaService,
		PanicReporter: func(request *http.Request, recovered any, stack []byte) {
			sentry.WithScope(func(scope *sentry.Scope) {
				scope.SetRequest(request)
				scope.SetExtra("panic", recovered)
				scope.SetExtra("stack", string(stack))
				sentry.CaptureException(fmt.Errorf("panic: %v", recovered))
			})
		},
		RazorpayKeyID:           strings.TrimSpace(os.Getenv("RAZORPAY_KEY_ID")),
		RazorpayKeySecret:       strings.TrimSpace(os.Getenv("RAZORPAY_KEY_SECRET")),
		RazorpayWebhookSecret:   strings.TrimSpace(os.Getenv("RAZORPAY_WEBHOOK_SECRET")),
		RazorpayCheckoutEnabled: strings.EqualFold(strings.TrimSpace(os.Getenv("RAZORPAY_CHECKOUT_ENABLED")), "true"),
	})
	server := &http.Server{
		Addr: ":" + port, Handler: handler, ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second,
	}

	go func() {
		logger.Info("YAFA VANAM Commerce API started", "port", port, "catalogue", catalogPath, "products", catalog.ProductCount())
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("API server failed", "error", err)
			os.Exit(1)
		}
	}()

	shutdownSignal, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	<-shutdownSignal.Done()
	context, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(context); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
		os.Exit(1)
	}
	logger.Info("YAFA VANAM Commerce API stopped")
}

func envOrDefault(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
