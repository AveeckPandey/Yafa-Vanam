package yafa

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var (
	ErrNotFound             = errors.New("session not found")
	ErrAccessDenied         = errors.New("session access denied")
	ErrInvalidState         = errors.New("invalid session state")
	ErrInvalidAnswer        = errors.New("invalid answer")
	ErrInvalidShade         = errors.New("invalid shade selection")
	ErrAnalysisUndetermined = errors.New("analysis could not determine a shade")
)

type Service struct {
	db       *pgxpool.Pool
	storage  *Storage
	analyzer *Analyzer
}
type SessionStart struct {
	ID    string `json:"session_id"`
	Token string `json:"session_token,omitempty"`
}
type Confirmation struct {
	ShadeID        string `json:"shade_id"`
	SavedToProfile bool   `json:"saved_to_profile"`
}
type BeautyProfile struct {
	HasProfile bool   `json:"has_profile"`
	ShadeID    string `json:"shade_id,omitempty"`
	ShadeName  string `json:"shade_name,omitempty"`
	ShadeCode  string `json:"shade_code,omitempty"`
	Hex        string `json:"hex,omitempty"`
}

func New(db *pgxpool.Pool) *Service { return &Service{db: db} }
func (s *Service) SetInfrastructure(storage *Storage, analyzer *Analyzer) {
	s.storage, s.analyzer = storage, analyzer
}

func (s *Service) BeautyProfile(ctx context.Context, userID string) (BeautyProfile, error) {
	if strings.TrimSpace(userID) == "" {
		return BeautyProfile{}, ErrAccessDenied
	}
	var profile BeautyProfile
	err := s.db.QueryRow(ctx, `SELECT s.id::text, s.name, COALESCE(s.code, ''), COALESCE(s.hex, '#000000') FROM user_beauty_profiles AS profile JOIN shades AS s ON s.id = profile.confirmed_shade_id WHERE profile.user_id = $1`, userID).Scan(&profile.ShadeID, &profile.ShadeName, &profile.ShadeCode, &profile.Hex)
	if errors.Is(err, pgx.ErrNoRows) {
		return BeautyProfile{HasProfile: false}, nil
	}
	if err != nil {
		return BeautyProfile{}, err
	}
	profile.HasProfile = true
	return profile, nil
}

var answerOptions = map[string]map[string]struct{}{
	"primary_concern":    {"hydration": {}, "uneven_tone": {}, "fine_lines": {}, "acne_prone": {}, "sensitivity": {}, "hyperpigmentation": {}},
	"skin_feel":          {"tight_dry": {}, "balanced": {}, "oily_midday": {}, "combination": {}},
	"spf_daily":          {"yes": {}, "no": {}},
	"foundation_finish":  {"matte": {}, "satin": {}, "dewy": {}, "buildable": {}},
	"visible_dark_spots": {"yes": {}, "some": {}, "no": {}},
	"oil_free":           {"yes": {}, "no": {}, "unsure": {}},
	"routine_time":       {"under_5": {}, "5_15": {}, "15_30": {}, "over_30": {}},
}

func (s *Service) Start(ctx context.Context, userID string) (SessionStart, error) {
	if strings.TrimSpace(userID) != "" {
		var id string
		err := s.db.QueryRow(ctx, `INSERT INTO yafa_sessions (user_id) VALUES ($1) RETURNING id::text`, userID).Scan(&id)
		return SessionStart{ID: id}, err
	}
	token, err := randomToken()
	if err != nil {
		return SessionStart{}, err
	}
	hash := sha256.Sum256([]byte(token))
	var id string
	err = s.db.QueryRow(ctx, `INSERT INTO yafa_sessions (anonymous_token_hash) VALUES ($1) RETURNING id::text`, hash[:]).Scan(&id)
	return SessionStart{ID: id, Token: token}, err
}

func (s *Service) SaveAnswer(ctx context.Context, sessionID, userID, token, stepID, answer string) error {
	if !validAnswer(stepID, answer) {
		return ErrInvalidAnswer
	}
	if err := s.authorize(ctx, sessionID, userID, token); err != nil {
		return err
	}
	command, err := s.db.Exec(ctx, `UPDATE yafa_sessions SET answers = jsonb_set(answers, ARRAY[$2], to_jsonb($3::text), true) WHERE id = $1 AND status = 'in_progress'`, sessionID, stepID, answer)
	if err != nil {
		return err
	}
	if command.RowsAffected() != 1 {
		return ErrInvalidState
	}
	return nil
}

func (s *Service) Confirm(ctx context.Context, sessionID, userID, token, shadeID string) (Confirmation, error) {
	if err := s.authorize(ctx, sessionID, userID, token); err != nil {
		return Confirmation{}, err
	}
	tx, err := s.db.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return Confirmation{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	var answers []byte
	var owner *string
	err = tx.QueryRow(ctx, `SELECT answers, user_id::text FROM yafa_sessions WHERE id = $1 AND status = 'analyzed' AND EXISTS (SELECT 1 FROM jsonb_array_elements(candidates) AS candidate WHERE candidate->>'shade_id' = $2) AND EXISTS (SELECT 1 FROM shades WHERE id = $2 AND is_active = TRUE) FOR UPDATE`, sessionID, shadeID).Scan(&answers, &owner)
	if errors.Is(err, pgx.ErrNoRows) {
		return Confirmation{}, ErrInvalidShade
	}
	if err != nil {
		return Confirmation{}, err
	}
	if _, err = tx.Exec(ctx, `UPDATE yafa_sessions SET status = 'confirmed', confirmed_shade_id = $2, confirmed_at = NOW() WHERE id = $1`, sessionID, shadeID); err != nil {
		return Confirmation{}, err
	}
	confirmed := Confirmation{ShadeID: shadeID}
	if owner != nil {
		if userID == "" || subtle.ConstantTimeCompare([]byte(*owner), []byte(userID)) != 1 {
			return Confirmation{}, ErrAccessDenied
		}
		if _, err = tx.Exec(ctx, `INSERT INTO user_beauty_profiles (user_id, confirmed_shade_id, yafa_answers, updated_at) VALUES ($1, $2, $3::jsonb, NOW()) ON CONFLICT (user_id) DO UPDATE SET confirmed_shade_id = EXCLUDED.confirmed_shade_id, yafa_answers = EXCLUDED.yafa_answers, updated_at = NOW()`, userID, shadeID, string(answers)); err != nil {
			return Confirmation{}, err
		}
		if _, err = tx.Exec(ctx, `INSERT INTO user_shade_history (user_id, shade_id, yafa_session_id) VALUES ($1, $2, $3) ON CONFLICT (yafa_session_id) DO NOTHING`, userID, shadeID, sessionID); err != nil {
			return Confirmation{}, err
		}
		confirmed.SavedToProfile = true
	}
	if err = tx.Commit(ctx); err != nil {
		return Confirmation{}, err
	}
	return confirmed, nil
}

func (s *Service) AttachSelfie(ctx context.Context, sessionID, userID, token string, source []byte) error {
	if s.storage == nil {
		return errors.New("selfie storage unavailable")
	}
	if err := s.authorize(ctx, sessionID, userID, token); err != nil {
		return err
	}
	key, err := s.storage.StoreSelfie(ctx, sessionID, source)
	if err != nil {
		return err
	}
	command, err := s.db.Exec(ctx, `UPDATE yafa_sessions SET selfie_storage_key = $2 WHERE id = $1 AND status = 'in_progress'`, sessionID, key)
	if err != nil {
		return err
	}
	if command.RowsAffected() != 1 {
		return ErrInvalidState
	}
	return nil
}

func (s *Service) Analyze(ctx context.Context, sessionID, userID, token string) (json.RawMessage, error) {
	if s.analyzer == nil {
		return nil, errors.New("Yafa analyzer unavailable")
	}
	if err := s.authorize(ctx, sessionID, userID, token); err != nil {
		return nil, err
	}
	var answers json.RawMessage
	var selfieKey *string
	err := s.db.QueryRow(ctx, `SELECT answers, selfie_storage_key FROM yafa_sessions WHERE id = $1 AND status = 'in_progress'`, sessionID).Scan(&answers, &selfieKey)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrInvalidState
	}
	if err != nil {
		return nil, err
	}
	var signedURL *string
	if selfieKey != nil {
		if s.storage == nil {
			return nil, errors.New("selfie storage unavailable")
		}
		url, signErr := s.storage.SignedReadURL(ctx, *selfieKey)
		if signErr != nil {
			return nil, signErr
		}
		signedURL = &url
	}
	derived, err := s.analyzer.Analyze(ctx, answers, signedURL)
	if err != nil {
		return nil, err
	}
	candidates := make([]map[string]any, 0, 3)
	for _, candidate := range derived {
		var id, name, hex string
		err = s.db.QueryRow(ctx, `SELECT id::text, name, COALESCE(hex, '#000000') FROM shades WHERE code = $1 AND is_active = TRUE ORDER BY created_at ASC LIMIT 1`, strings.ToUpper(strings.TrimSpace(candidate.ShadeCode))).Scan(&id, &name, &hex)
		if err != nil {
			return nil, errors.New("unavailable Yafa shade")
		}
		if candidate.Confidence < 0 || candidate.Confidence > 1 || len(candidate.Reason) > 280 {
			return nil, errors.New("invalid Yafa analysis response")
		}
		candidates = append(candidates, map[string]any{"shade_id": id, "shade_name": name, "hex": hex, "confidence": candidate.Confidence, "reason": candidate.Reason})
	}
	encoded, err := json.Marshal(map[string]any{"candidates": candidates, "primary_recommendation": candidates[0]["shade_id"]})
	if err != nil {
		return nil, err
	}
	command, err := s.db.Exec(ctx, `UPDATE yafa_sessions SET candidates = $2::jsonb, status = 'analyzed', analyzed_at = NOW() WHERE id = $1 AND status = 'in_progress'`, sessionID, string(encoded))
	if err != nil {
		return nil, err
	}
	if command.RowsAffected() != 1 {
		return nil, ErrInvalidState
	}
	return encoded, nil
}

func (s *Service) authorize(ctx context.Context, sessionID, userID, token string) error {
	var owner *string
	var hash []byte
	err := s.db.QueryRow(ctx, `SELECT user_id::text, anonymous_token_hash FROM yafa_sessions WHERE id = $1`, sessionID).Scan(&owner, &hash)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrNotFound
	}
	if err != nil {
		return err
	}
	if owner != nil {
		if userID == "" || subtle.ConstantTimeCompare([]byte(*owner), []byte(userID)) != 1 {
			return ErrAccessDenied
		}
		return nil
	}
	provided := sha256.Sum256([]byte(token))
	if token == "" || len(hash) != len(provided) || subtle.ConstantTimeCompare(hash, provided[:]) != 1 {
		return ErrAccessDenied
	}
	return nil
}

func validAnswer(stepID, answer string) bool {
	options, ok := answerOptions[stepID]
	if !ok || len(answer) > 64 {
		return false
	}
	_, ok = options[answer]
	return ok
}
func randomToken() (string, error) {
	value := make([]byte, 32)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(value), nil
}
