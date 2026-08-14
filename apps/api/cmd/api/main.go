package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"time"
)

type healthResponse struct {
	Service string    `json:"service"`
	Status  string    `json:"status"`
	Time    time.Time `json:"time"`
}

func main() {
	port := os.Getenv("API_PORT")
	if port == "" {
		port = "4000"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(healthResponse{
			Service: "yafa-api",
			Status:  "ok",
			Time:    time.Now().UTC(),
		})
	})
	mux.HandleFunc("GET /api/v1", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"name":    "YAFA VANAM Commerce API",
			"version": "v1",
		})
	})

	server := &http.Server{
		Addr:              ":" + port,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	log.Printf("YAFA VANAM Go API listening on :%s", port)
	log.Fatal(server.ListenAndServe())
}
