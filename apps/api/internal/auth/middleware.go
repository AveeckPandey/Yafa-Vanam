package auth

import (
	"context"
	"net/http"
)

type contextKey string

const userContextKey contextKey = "auth.user"

// Middleware protects routes that require an authenticated customer. Handlers can
// retrieve the verified user with UserFromContext rather than trusting client input.
func (s *Service) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		user, err := s.ValidateAccess(cookie(request, accessCookie))
		if err != nil {
			fail(w, http.StatusUnauthorized, "Sign in is required to continue.")
			return
		}
		next.ServeHTTP(w, request.WithContext(context.WithValue(request.Context(), userContextKey, user)))
	})
}

// OptionalMiddleware preserves anonymous Yafa sessions while still attaching a
// verified user when a browser presents an access cookie. An invalid cookie is
// rejected rather than silently downgraded to an anonymous session.
func (s *Service) OptionalMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, request *http.Request) {
		access := cookie(request, accessCookie)
		if access == "" {
			next.ServeHTTP(w, request)
			return
		}
		user, err := s.ValidateAccess(access)
		if err != nil {
			fail(w, http.StatusUnauthorized, "Sign in is required to continue.")
			return
		}
		next.ServeHTTP(w, request.WithContext(context.WithValue(request.Context(), userContextKey, user)))
	})
}

func UserFromContext(ctx context.Context) (User, bool) {
	user, ok := ctx.Value(userContextKey).(User)
	return user, ok
}
