package yafa

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"time"
)

type Analyzer struct {
	endpoint, token string
	client          *http.Client
}
type AnalysisCandidate struct {
	ShadeCode  string  `json:"shade_code"`
	Confidence float64 `json:"confidence"`
	Reason     string  `json:"reason"`
}

func NewAnalyzer(endpoint, token string) (*Analyzer, error) {
	if strings.TrimSpace(endpoint) == "" || strings.TrimSpace(token) == "" {
		return nil, errors.New("incomplete Yafa analyzer configuration")
	}
	if len(token) < 32 {
		return nil, errors.New("Yafa analyzer credential is too short")
	}
	return &Analyzer{endpoint: strings.TrimRight(endpoint, "/") + "/ai/analyze", token: token, client: &http.Client{Timeout: 12 * time.Second}}, nil
}
func (a *Analyzer) Analyze(ctx context.Context, answers json.RawMessage, selfieURL *string) ([]AnalysisCandidate, error) {
	body, err := json.Marshal(map[string]any{"answers": json.RawMessage(answers), "selfie_url": selfieURL})
	if err != nil {
		return nil, err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, a.endpoint, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Yafa-Service-Token", a.token)
	response, err := a.client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode == http.StatusUnprocessableEntity {
		return nil, ErrAnalysisUndetermined
	}
	if response.StatusCode != http.StatusOK {
		return nil, errors.New("Yafa analysis unavailable")
	}
	var decoded struct {
		Candidates      []AnalysisCandidate `json:"candidates"`
		ShadeDetermined bool                `json:"shade_determined"`
	}
	if err = json.NewDecoder(io.LimitReader(response.Body, 128<<10)).Decode(&decoded); err != nil {
		return nil, errors.New("invalid Yafa analysis response")
	}
	if !decoded.ShadeDetermined {
		return nil, ErrAnalysisUndetermined
	}
	if len(decoded.Candidates) != 3 {
		return nil, errors.New("invalid Yafa analysis response")
	}
	return decoded.Candidates, nil
}
