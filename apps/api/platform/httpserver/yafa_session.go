package httpserver

import (
	"errors"
	"io"
	"net/http"
	"regexp"
	"strings"

	"github.com/BuildWithAveeck/yafa-vanam/apps/api/internal/yafa"
)

var uuidPattern = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)

func (server *Server) startYafaSession(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	user, signedIn := requestUser(request)
	started, err := server.yafa.Start(request.Context(), map[bool]string{true: user.ID, false: ""}[signedIn])
	if err != nil {
		server.logger.Error("yafa session start failed", "error", err)
		writeError(w, http.StatusInternalServerError, "internal_error", "We could not start Yafa.")
		return
	}
	writeJSON(w, http.StatusCreated, started)
}

func (server *Server) yafaBeautyProfile(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	user, signedIn := requestUser(request)
	if !signedIn {
		writeError(w, http.StatusUnauthorized, "unauthenticated", "Sign in is required to view your Yafa profile.")
		return
	}
	profile, err := server.yafa.BeautyProfile(request.Context(), user.ID)
	if err != nil {
		server.writeYafaError(w, err, http.StatusOK)
		return
	}
	writeJSON(w, http.StatusOK, profile)
}

func (server *Server) saveYafaAnswer(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	sessionID := strings.ToLower(request.PathValue("sessionID"))
	if !uuidPattern.MatchString(sessionID) {
		writeError(w, http.StatusBadRequest, "invalid_request", "The Yafa session is invalid.")
		return
	}
	var input struct {
		StepID string `json:"step_id"`
		Answer string `json:"answer"`
	}
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "The answer could not be saved.")
		return
	}
	user, signedIn := requestUser(request)
	err := server.yafa.SaveAnswer(request.Context(), sessionID, map[bool]string{true: user.ID, false: ""}[signedIn], request.Header.Get("X-Yafa-Session-Token"), input.StepID, input.Answer)
	server.writeYafaError(w, err, http.StatusNoContent)
}

func (server *Server) uploadYafaSelfie(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	sessionID := strings.ToLower(request.PathValue("sessionID"))
	if !uuidPattern.MatchString(sessionID) {
		writeError(w, http.StatusBadRequest, "invalid_request", "The Yafa session is invalid.")
		return
	}
	request.Body = http.MaxBytesReader(w, request.Body, 5<<20)
	if err := request.ParseMultipartForm(5 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "Choose a JPG or PNG image up to 5 MB.")
		return
	}
	file, _, err := request.FormFile("image")
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "Choose a JPG or PNG image up to 5 MB.")
		return
	}
	defer file.Close()
	image, err := io.ReadAll(io.LimitReader(file, (5<<20)+1))
	if err != nil || len(image) > 5<<20 {
		writeError(w, http.StatusBadRequest, "invalid_request", "Choose a JPG or PNG image up to 5 MB.")
		return
	}
	user, signedIn := requestUser(request)
	server.writeYafaError(w, server.yafa.AttachSelfie(request.Context(), sessionID, map[bool]string{true: user.ID, false: ""}[signedIn], request.Header.Get("X-Yafa-Session-Token"), image), http.StatusNoContent)
}

func (server *Server) analyzeYafaSession(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	sessionID := strings.ToLower(request.PathValue("sessionID"))
	if !uuidPattern.MatchString(sessionID) {
		writeError(w, http.StatusBadRequest, "invalid_request", "The Yafa session is invalid.")
		return
	}
	user, signedIn := requestUser(request)
	result, err := server.yafa.Analyze(request.Context(), sessionID, map[bool]string{true: user.ID, false: ""}[signedIn], request.Header.Get("X-Yafa-Session-Token"))
	if err != nil {
		server.writeYafaError(w, err, http.StatusOK)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	_, _ = w.Write(result)
}

func (server *Server) confirmYafaShade(w http.ResponseWriter, request *http.Request) {
	if server.yafa == nil {
		writeError(w, http.StatusServiceUnavailable, "service_unavailable", "Yafa is temporarily unavailable.")
		return
	}
	var input struct {
		SessionID string `json:"quiz_session_id"`
		ShadeID   string `json:"shade_id"`
	}
	if err := decodeJSON(w, request, &input); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "The shade could not be confirmed.")
		return
	}
	if routeSessionID := strings.ToLower(request.PathValue("sessionID")); routeSessionID != "" {
		if input.SessionID != "" && !strings.EqualFold(input.SessionID, routeSessionID) {
			writeError(w, http.StatusBadRequest, "invalid_request", "The shade selection is invalid.")
			return
		}
		input.SessionID = routeSessionID
	}
	input.SessionID, input.ShadeID = strings.ToLower(strings.TrimSpace(input.SessionID)), strings.ToLower(strings.TrimSpace(input.ShadeID))
	if !uuidPattern.MatchString(input.SessionID) || !uuidPattern.MatchString(input.ShadeID) {
		writeError(w, http.StatusBadRequest, "invalid_request", "The shade selection is invalid.")
		return
	}
	user, signedIn := requestUser(request)
	confirmed, err := server.yafa.Confirm(request.Context(), input.SessionID, map[bool]string{true: user.ID, false: ""}[signedIn], request.Header.Get("X-Yafa-Session-Token"), input.ShadeID)
	if err != nil {
		server.writeYafaError(w, err, http.StatusOK)
		return
	}
	writeJSON(w, http.StatusOK, confirmed)
}

func (server *Server) writeYafaError(w http.ResponseWriter, err error, successStatus int) {
	if err == nil {
		w.WriteHeader(successStatus)
		return
	}
	switch {
	case errors.Is(err, yafa.ErrNotFound):
		writeError(w, http.StatusNotFound, "not_found", "The Yafa session was not found.")
	case errors.Is(err, yafa.ErrAccessDenied):
		writeError(w, http.StatusForbidden, "access_denied", "You do not have access to this Yafa session.")
	case errors.Is(err, yafa.ErrInvalidAnswer), errors.Is(err, yafa.ErrInvalidShade), errors.Is(err, yafa.ErrInvalidState):
		writeError(w, http.StatusUnprocessableEntity, "validation_error", "That Yafa action is no longer available.")
	case errors.Is(err, yafa.ErrAnalysisUndetermined):
		writeError(w, http.StatusUnprocessableEntity, "analysis_undetermined", "We could not determine a shade from this selfie. Please retake it in clear, even lighting.")
	default:
		server.logger.Error("yafa session request failed", "error", err)
		writeError(w, http.StatusInternalServerError, "internal_error", "Yafa could not complete that action.")
	}
}
