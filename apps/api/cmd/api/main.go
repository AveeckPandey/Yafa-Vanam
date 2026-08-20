package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/auth"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/commerce"
	"github.com/BuildWithAveeck/yafa-vanam/apps/api/platform/httpserver"
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
		port = "4000"
	}
	origins := strings.Split(envOrDefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000"), ",")
	var authHandler *auth.Handler
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
		if err := redisClient.Ping(context.Background()).Err(); err != nil {
			logger.Error("auth redis unavailable", "error", err)
			os.Exit(1)
		}
		defer db.Close()
		defer redisClient.Close()
		authHandler = auth.NewHandler(auth.New(db, redisClient, auth.Config{JWTSecret: secret, SecureCookies: os.Getenv("APP_ENV") == "production", AccessTTL: 15 * time.Minute, RefreshTTL: 24 * time.Hour, RememberRefreshTTL: 30 * 24 * time.Hour}), os.Getenv("GOOGLE_CLIENT_ID"), os.Getenv("GOOGLE_CLIENT_SECRET"), os.Getenv("GOOGLE_CALLBACK_URL"), envOrDefault("APP_URL", "http://localhost:3000"))
	} else {
		logger.Warn("authentication disabled: set DATABASE_URL, REDIS_URL, and a 32+ character JWT_SECRET to enable it")
	}
	handler := httpserver.New(catalog, commerce.NewStore(catalog), httpserver.Config{
		AllowedOrigins: origins, Logger: logger, Auth: authHandler,
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
