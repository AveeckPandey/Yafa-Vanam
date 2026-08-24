package httpserver

// POST /api/v1/yafa/transcribe
//
// Voice path (storefront fix): Browser MediaRecorder -> Go API -> self-hosted
// Faster-Whisper (AWS EC2) -> transcript -> existing Yafa text pipeline.
// The browser never talks to the Whisper host directly and never sees
// WHISPER_INTERNAL_TOKEN; this handler injects Bearer auth server-side.
//
// Configuration (read per request so Railway variable updates need no rebuild):
//   WHISPER_SERVICE_URL    e.g. http://<ec2-host>:9000  (a /transcribe suffix is appended unless already present)
//   WHISPER_INTERNAL_TOKEN shared secret sent as Authorization: Bearer <token>
//
// Failure behaviour: when Whisper is unconfigured/unreachable the endpoint
// returns a clean error - text chat keeps working without it.

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

const (
	transcribeMaxBytes = 25 << 20 // 25 MiB audio cap
	transcribeTimeout  = 90 * time.Second
)

type transcribeResponse struct {
	Text       string  `json:"text"`
	Language   *string `json:"language,omitempty"`
	DurationMS *int64  `json:"duration_ms,omitempty"`
}

func whisperServiceURL() string {
	return strings.TrimRight(strings.TrimSpace(os.Getenv("WHISPER_SERVICE_URL")), "/")
}

func whisperInternalToken() string {
	return strings.TrimSpace(os.Getenv("WHISPER_INTERNAL_TOKEN"))
}

func (server *Server) yafaTranscribe(w http.ResponseWriter, request *http.Request) {
	serviceURL := whisperServiceURL()
	if serviceURL == "" || whisperInternalToken() == "" {
		writeError(w, http.StatusServiceUnavailable, "speech_unconfigured",
			"Voice transcription is not available right now. You can continue by typing.")
		return
	}
	if !strings.HasSuffix(serviceURL, "/transcribe") {
		serviceURL += "/transcribe"
	}

	request.Body = http.MaxBytesReader(w, request.Body, transcribeMaxBytes)
	if err := request.ParseMultipartForm(8 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_audio", "That audio could not be read. Try recording again.")
		return
	}
	file, header, err := request.FormFile("audio")
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_audio", "No audio upload found in the request.")
		return
	}
	defer file.Close()

	contentType := header.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	if !strings.HasPrefix(contentType, "audio/") && contentType != "application/octet-stream" &&
		!strings.HasPrefix(contentType, "video/webm") && !strings.HasPrefix(contentType, "video/mp4") {
		// MediaRecorder may label webm as video/* depending on codec hints.
		writeError(w, http.StatusUnsupportedMediaType, "unsupported_media_type", "Only audio uploads are supported.")
		return
	}

	ctx, cancel := context.WithTimeout(request.Context(), transcribeTimeout)
	defer cancel()
	upstreamRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, serviceURL, file)
	if err != nil {
		writeError(w, http.StatusBadGateway, "speech_unavailable", "Transcription is temporarily unavailable.")
		return
	}
	upstreamRequest.Header.Set("Authorization", "Bearer "+whisperInternalToken())
	upstreamRequest.Header.Set("Content-Type", contentType)
	upstreamRequest.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: transcribeTimeout}
	response, err := client.Do(upstreamRequest)
	if err != nil {
		server.logger.Error("whisper upstream unreachable", "error", err.Error())
		writeError(w, http.StatusBadGateway, "speech_unavailable",
			"Transcription is temporarily unavailable. You can continue by typing.")
		return
	}
	defer response.Body.Close()

	body, err := io.ReadAll(io.LimitReader(response.Body, transcribeMaxBytes))
	if err != nil || response.StatusCode < 200 || response.StatusCode >= 300 {
		server.logger.Error("whisper upstream error", "status", response.StatusCode)
		writeError(w, http.StatusBadGateway, "speech_unavailable",
			"Transcription failed. Please try again, or continue by typing.")
		return
	}

	var decoded transcribeResponse
	if err := json.Unmarshal(body, &decoded); err != nil || strings.TrimSpace(decoded.Text) == "" {
		// Contract flexibility: accept a bare-text body from simpler workers.
		fallback := strings.TrimSpace(string(body))
		if fallback == "" || strings.HasPrefix(fallback, "<") {
			writeError(w, http.StatusBadGateway, "speech_unavailable",
				"Transcription returned no text. Please try again.")
			return
		}
		decoded = transcribeResponse{Text: fallback}
	}
	writeJSON(w, http.StatusOK, decoded)
}
