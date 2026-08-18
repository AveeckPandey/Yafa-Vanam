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

func UserFromContext(ctx context.Context) (User, bool) {
	user, ok := ctx.Value(userContextKey).(User)
	return user, ok
}
