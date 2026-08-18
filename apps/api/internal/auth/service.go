package auth

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/bcrypt"
)

var (
	ErrInvalidCredentials = errors.New("invalid email or password")
	ErrEmailTaken         = errors.New("an account already exists for this email")
)

type User struct{ ID, Name, Email string }
type Config struct {
	JWTSecret                                 string
	SecureCookies                             bool
	AccessTTL, RefreshTTL, RememberRefreshTTL time.Duration
}
type Service struct {
	db     *pgxpool.Pool
	redis  *redis.Client
	config Config
}

func New(db *pgxpool.Pool, redisClient *redis.Client, config Config) *Service {
	return &Service{db: db, redis: redisClient, config: config}
}

func (s *Service) Register(ctx context.Context, name, email, password string) (User, error) {
	name, email = strings.TrimSpace(name), strings.ToLower(strings.TrimSpace(email))
	if name == "" || len(password) < 8 || !strings.Contains(email, "@") {
		return User{}, errors.New("provide a name, valid email, and password of at least 8 characters")
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return User{}, err
	}
	var user User
	err = s.db.QueryRow(ctx, `WITH inserted AS (INSERT INTO users (email, name) VALUES ($1,$2) ON CONFLICT (email) DO NOTHING RETURNING id::text,name,email) SELECT id,name,email FROM inserted`, email, name).Scan(&user.ID, &user.Name, &user.Email)
	if err != nil {
		return User{}, ErrEmailTaken
	}
	_, err = s.db.Exec(ctx, `INSERT INTO user_credentials (user_id,password_hash) VALUES ($1,$2)`, user.ID, string(hash))
	if err != nil {
		return User{}, err
	}
	return user, nil
}

func (s *Service) Login(ctx context.Context, email, password string) (User, error) {
	var user User
	var hash string
	err := s.db.QueryRow(ctx, `SELECT u.id::text,u.name,u.email,c.password_hash FROM users u JOIN user_credentials c ON c.user_id=u.id WHERE LOWER(u.email)=LOWER($1) AND u.is_active=true`, strings.TrimSpace(email)).Scan(&user.ID, &user.Name, &user.Email, &hash)
	if err != nil || bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) != nil {
		return User{}, ErrInvalidCredentials
	}
	return user, nil
}

func (s *Service) GoogleUser(ctx context.Context, subject, name, email, picture string) (User, error) {
	var u User
	err := s.db.QueryRow(ctx, `INSERT INTO users (email,name,google_subject,avatar_url,email_verified_at) VALUES ($1,$2,$3,$4,NOW()) ON CONFLICT (email) DO UPDATE SET google_subject=EXCLUDED.google_subject, name=COALESCE(NULLIF(EXCLUDED.name,''),users.name), avatar_url=EXCLUDED.avatar_url RETURNING id::text,name,email`, strings.ToLower(email), name, subject, picture).Scan(&u.ID, &u.Name, &u.Email)
	return u, err
}

func (s *Service) Issue(ctx context.Context, user User, remember bool) (string, string, error) {
	access, err := s.signed(user, "access", "", s.config.AccessTTL)
	if err != nil {
		return "", "", err
	}
	jti, err := randomID()
	if err != nil {
		return "", "", err
	}
	ttl := s.config.RefreshTTL
	if remember {
		ttl = s.config.RememberRefreshTTL
	}
	refresh, err := s.signed(user, "refresh", jti, ttl)
	if err != nil {
		return "", "", err
	}
	rememberValue := "0"
	if remember {
		rememberValue = "1"
	}
	if err = s.redis.Set(ctx, "auth:refresh:"+jti, user.ID+":"+rememberValue, ttl).Err(); err != nil {
		return "", "", err
	}
	return access, refresh, nil
}

func (s *Service) Rotate(ctx context.Context, refresh string) (User, string, string, error) {
	claims, err := s.parse(refresh, "refresh")
	if err != nil {
		return User{}, "", "", err
	}
	jti, _ := claims["jti"].(string)
	session, err := s.redis.Get(ctx, "auth:refresh:"+jti).Result()
	if err != nil || session == "" {
		return User{}, "", "", errors.New("refresh session expired")
	}
	if err = s.redis.Del(ctx, "auth:refresh:"+jti).Err(); err != nil {
		return User{}, "", "", err
	}
	parts := strings.SplitN(session, ":", 2)
	var user User
	err = s.db.QueryRow(ctx, `SELECT id::text,name,email FROM users WHERE id=$1 AND is_active=true`, parts[0]).Scan(&user.ID, &user.Name, &user.Email)
	if err != nil {
		return User{}, "", "", ErrInvalidCredentials
	}
	a, r, err := s.Issue(ctx, user, len(parts) == 2 && parts[1] == "1")
	return user, a, r, err
}
func (s *Service) Revoke(ctx context.Context, refresh string) {
	claims, err := s.parse(refresh, "refresh")
	if err == nil {
		if jti, _ := claims["jti"].(string); jti != "" {
			_ = s.redis.Del(ctx, "auth:refresh:"+jti).Err()
		}
	}
}
func (s *Service) ValidateAccess(token string) (User, error) {
	c, err := s.parse(token, "access")
	if err != nil {
		return User{}, err
	}
	return User{ID: fmt.Sprint(c["sub"]), Email: fmt.Sprint(c["email"]), Name: fmt.Sprint(c["name"])}, nil
}
func (s *Service) signed(u User, kind, jti string, ttl time.Duration) (string, error) {
	now := time.Now()
	c := jwt.MapClaims{"sub": u.ID, "email": u.Email, "name": u.Name, "kind": kind, "iat": now.Unix(), "exp": now.Add(ttl).Unix()}
	if jti != "" {
		c["jti"] = jti
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, c).SignedString([]byte(s.config.JWTSecret))
}
func (s *Service) parse(token, kind string) (jwt.MapClaims, error) {
	parsed, err := jwt.Parse(token, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, errors.New("unexpected signing method")
		}
		return []byte(s.config.JWTSecret), nil
	})
	if err != nil || !parsed.Valid {
		return nil, errors.New("invalid token")
	}
	c, ok := parsed.Claims.(jwt.MapClaims)
	if !ok || c["kind"] != kind {
		return nil, errors.New("invalid token")
	}
	return c, nil
}
func randomID() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}
