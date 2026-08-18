package auth

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"golang.org/x/time/rate"
)

const accessCookie = "yafa_access"
const refreshCookie = "yafa_refresh"
const csrfCookie = "yafa_csrf"

type Handler struct {
	service                       *Service
	oauth                         *oauth2.Config
	secure                        bool
	frontendURL                   string
	loginLimiter, registerLimiter *rate.Limiter
}

func (h *Handler) Middleware(next http.Handler) http.Handler { return h.service.Middleware(next) }

func NewHandler(s *Service, clientID, clientSecret, callback, frontendURL string) *Handler {
	h := &Handler{service: s, secure: s.config.SecureCookies, frontendURL: strings.TrimRight(frontendURL, "/"), loginLimiter: rate.NewLimiter(rate.Every(time.Minute/8), 8), registerLimiter: rate.NewLimiter(rate.Every(time.Minute/5), 5)}
	if clientID != "" && clientSecret != "" && callback != "" {
		h.oauth = &oauth2.Config{ClientID: clientID, ClientSecret: clientSecret, RedirectURL: callback, Endpoint: google.Endpoint, Scopes: []string{"openid", "email", "profile"}}
	}
	return h
}
func (h *Handler) Routes(mux *http.ServeMux) {
	mux.HandleFunc("GET /auth/csrf", h.csrf)
	mux.HandleFunc("GET /auth/me", h.me)
	mux.HandleFunc("POST /auth/register", h.register)
	mux.HandleFunc("POST /auth/login", h.login)
	mux.HandleFunc("POST /auth/refresh", h.refresh)
	mux.HandleFunc("POST /auth/logout", h.logout)
	mux.HandleFunc("GET /auth/google", h.google)
	mux.HandleFunc("GET /auth/google/callback", h.callback)
}
func (h *Handler) csrf(w http.ResponseWriter, r *http.Request) {
	token, err := token()
	if err != nil {
		fail(w, 500, "Unable to prepare session.")
		return
	}
	http.SetCookie(w, &http.Cookie{Name: csrfCookie, Value: token, Path: "/", HttpOnly: false, Secure: h.secure, SameSite: http.SameSiteStrictMode, MaxAge: 86400})
	json.NewEncoder(w).Encode(map[string]string{"csrfToken": token})
}
func (h *Handler) register(w http.ResponseWriter, r *http.Request) {
	if !h.registerLimiter.Allow() {
		fail(w, 429, "Too many attempts. Please try again shortly.")
		return
	}
	if !h.validCSRF(r) {
		fail(w, 403, "Invalid security token.")
		return
	}
	var in struct {
		Name, Email, Password string
		Remember              bool `json:"remember"`
	}
	if !decode(r, &in) {
		fail(w, 400, "Invalid registration details.")
		return
	}
	u, e := h.service.Register(r.Context(), in.Name, in.Email, in.Password)
	if e != nil {
		fail(w, 422, e.Error())
		return
	}
	h.respondSession(w, r.Context(), u, in.Remember)
}
func (h *Handler) login(w http.ResponseWriter, r *http.Request) {
	if !h.loginLimiter.Allow() {
		fail(w, 429, "Too many attempts. Please try again shortly.")
		return
	}
	if !h.validCSRF(r) {
		fail(w, 403, "Invalid security token.")
		return
	}
	var in struct {
		Email, Password string
		Remember        bool `json:"remember"`
	}
	if !decode(r, &in) {
		fail(w, 400, "Invalid sign in details.")
		return
	}
	u, e := h.service.Login(r.Context(), in.Email, in.Password)
	if e != nil {
		fail(w, 401, "Your email or password is incorrect.")
		return
	}
	h.respondSession(w, r.Context(), u, in.Remember)
}
func (h *Handler) refresh(w http.ResponseWriter, r *http.Request) {
	if !h.validCSRF(r) {
		fail(w, 403, "Invalid security token.")
		return
	}
	u, a, rt, e := h.service.Rotate(r.Context(), cookie(r, refreshCookie))
	if e != nil {
		h.clear(w)
		fail(w, 401, "Your session has expired.")
		return
	}
	h.set(w, a, rt, false)
	json.NewEncoder(w).Encode(map[string]User{"user": u})
}
func (h *Handler) logout(w http.ResponseWriter, r *http.Request) {
	if !h.validCSRF(r) {
		fail(w, 403, "Invalid security token.")
		return
	}
	h.service.Revoke(r.Context(), cookie(r, refreshCookie))
	h.clear(w)
	w.WriteHeader(http.StatusNoContent)
}
func (h *Handler) me(w http.ResponseWriter, r *http.Request) {
	u, e := h.service.ValidateAccess(cookie(r, accessCookie))
	if e != nil {
		fail(w, 401, "Not signed in.")
		return
	}
	json.NewEncoder(w).Encode(map[string]User{"user": u})
}
func (h *Handler) google(w http.ResponseWriter, r *http.Request) {
	if h.oauth == nil {
		fail(w, 503, "Google sign-in is not configured.")
		return
	}
	state, e := token()
	if e != nil {
		fail(w, 500, "Unable to begin Google sign-in.")
		return
	}
	returnTo := r.URL.Query().Get("return_to")
	if !strings.HasPrefix(returnTo, "/") || strings.HasPrefix(returnTo, "//") {
		returnTo = "/"
	}
	http.SetCookie(w, &http.Cookie{Name: "yafa_oauth_state", Value: state, Path: "/auth/google", HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteLaxMode, MaxAge: 600})
	http.SetCookie(w, &http.Cookie{Name: "yafa_oauth_return", Value: returnTo, Path: "/auth/google", HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteLaxMode, MaxAge: 600})
	http.Redirect(w, r, h.oauth.AuthCodeURL(state, oauth2.AccessTypeOffline), http.StatusFound)
}
func (h *Handler) callback(w http.ResponseWriter, r *http.Request) {
	returnTo := cookie(r, "yafa_oauth_return")
	if !strings.HasPrefix(returnTo, "/") || strings.HasPrefix(returnTo, "//") {
		returnTo = "/"
	}
	redirect := h.frontendURL + returnTo
	if h.oauth == nil || r.URL.Query().Get("state") != cookie(r, "yafa_oauth_state") {
		http.Redirect(w, r, redirect+"?auth_error=google", http.StatusFound)
		return
	}
	t, e := h.oauth.Exchange(r.Context(), r.URL.Query().Get("code"))
	if e != nil {
		http.Redirect(w, r, redirect+"?auth_error=google", 302)
		return
	}
	c := h.oauth.Client(context.Background(), t)
	res, e := c.Get("https://www.googleapis.com/oauth2/v3/userinfo")
	if e != nil || res.StatusCode != 200 {
		http.Redirect(w, r, redirect+"?auth_error=google", 302)
		return
	}
	defer res.Body.Close()
	var p struct{ Sub, Email, Name, Picture string }
	if json.NewDecoder(res.Body).Decode(&p) != nil || p.Sub == "" || p.Email == "" {
		http.Redirect(w, r, redirect+"?auth_error=google", 302)
		return
	}
	u, e := h.service.GoogleUser(r.Context(), p.Sub, p.Name, p.Email, p.Picture)
	if e != nil {
		http.Redirect(w, r, redirect+"?auth_error=google", 302)
		return
	}
	a, rt, e := h.service.Issue(r.Context(), u, true)
	if e != nil {
		http.Redirect(w, r, "/?auth_error=google", 302)
		return
	}
	h.set(w, a, rt, true)
	http.Redirect(w, r, redirect, 302)
}
func (h *Handler) respondSession(w http.ResponseWriter, ctx context.Context, u User, remember bool) {
	a, r, e := h.service.Issue(ctx, u, remember)
	if e != nil {
		fail(w, 500, "Unable to start your session.")
		return
	}
	h.set(w, a, r, remember)
	json.NewEncoder(w).Encode(map[string]User{"user": u})
}
func (h *Handler) set(w http.ResponseWriter, a, r string, remember bool) {
	ttl := h.service.config.RefreshTTL
	if remember {
		ttl = h.service.config.RememberRefreshTTL
	}
	http.SetCookie(w, &http.Cookie{Name: accessCookie, Value: a, Path: "/", HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteStrictMode, MaxAge: int(h.service.config.AccessTTL.Seconds())})
	http.SetCookie(w, &http.Cookie{Name: refreshCookie, Value: r, Path: "/", HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteStrictMode, MaxAge: int(ttl.Seconds())})
}
func (h *Handler) clear(w http.ResponseWriter) {
	for _, n := range []string{accessCookie, refreshCookie} {
		http.SetCookie(w, &http.Cookie{Name: n, Value: "", Path: "/", HttpOnly: true, Secure: h.secure, SameSite: http.SameSiteStrictMode, MaxAge: -1})
	}
}
func (h *Handler) validCSRF(r *http.Request) bool {
	return cookie(r, csrfCookie) != "" && cookie(r, csrfCookie) == r.Header.Get("X-CSRF-Token")
}
func cookie(r *http.Request, n string) string {
	c, e := r.Cookie(n)
	if e != nil {
		return ""
	}
	return c.Value
}
func decode(r *http.Request, v any) bool {
	return json.NewDecoder(r.Body).Decode(v) == nil
}
func fail(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": message})
}
func token() (string, error) {
	b := make([]byte, 32)
	_, e := rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b), e
}
