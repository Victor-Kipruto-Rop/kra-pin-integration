// Package oscu provides a server-side client for KRA's direct OSCU sandbox API.
package oscu

import (
	"bytes"
	"context"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"
)

//go:embed etims_oscu_endpoints.json
var manifestBytes []byte

const tokenURL = "https://sbx.kra.go.ke/v1/token/generate?grant_type=client_credentials"
const apiBase = "https://sbx.kra.go.ke/etims-oscu/api/v1"

type operation struct {
	ID      string   `json:"id"`
	Method  string   `json:"method"`
	Path    string   `json:"path"`
	Headers []string `json:"headers"`
	Mutates bool     `json:"mutates"`
}

type endpointManifest struct {
	Operations []operation `json:"operations"`
}

type OscuError struct {
	Code           string
	Message        string
	OutcomeUnknown bool
}

func (e *OscuError) Error() string { return e.Message }

type Client struct {
	key, secret, appID string
	http               *http.Client
	operations         map[string]operation
	mu                 sync.Mutex
	token              string
	tokenExpires       time.Time
}

func NewClient(key, secret, appID string, httpClient *http.Client) (*Client, error) {
	if key == "" || secret == "" || appID == "" {
		return nil, fmt.Errorf("OSCU consumer credentials and app ID are required")
	}
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 20 * time.Second}
	}
	var manifest endpointManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, fmt.Errorf("invalid packaged OSCU manifest")
	}
	ops := make(map[string]operation, len(manifest.Operations))
	for _, op := range manifest.Operations {
		ops[op.ID] = op
	}
	return &Client{key: key, secret: secret, appID: appID, http: httpClient, operations: ops}, nil
}

func (c *Client) tokenValue(ctx context.Context) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.token != "" && time.Now().Before(c.tokenExpires.Add(-time.Minute)) {
		return c.token, nil
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, tokenURL, nil)
	if err != nil { return "", &OscuError{Code: "oscu_auth_failed", Message: "Could not build KRA token request"} }
	req.SetBasicAuth(c.key, c.secret)
	resp, err := c.http.Do(req)
	if err != nil { return "", &OscuError{Code: "oscu_auth_failed", Message: "Could not obtain KRA OSCU access token"} }
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", &OscuError{Code: "oscu_auth_failed", Message: "KRA rejected OSCU token request"}
	}
	var body struct { AccessToken string `json:"access_token"`; ExpiresIn int `json:"expires_in"` }
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&body); err != nil || body.AccessToken == "" {
		return "", &OscuError{Code: "oscu_auth_failed", Message: "KRA returned an invalid OSCU token response"}
	}
	ttl := body.ExpiresIn
	if ttl <= 0 { ttl = 3600 }
	c.token, c.tokenExpires = body.AccessToken, time.Now().Add(time.Duration(ttl)*time.Second)
	return c.token, nil
}

// Invoke sends one operation. Mutations require explicit caller confirmation.
// The client never automatically retries a request after it has been submitted.
func (c *Client) Invoke(ctx context.Context, operationID string, payload map[string]any, tenant map[string]string, confirmMutation bool) (json.RawMessage, error) {
	op, ok := c.operations[operationID]
	if !ok { return nil, fmt.Errorf("unknown OSCU operation ID") }
	if payload == nil { return nil, fmt.Errorf("payload must be a JSON object") }
	if op.Mutates && !confirmMutation { return nil, fmt.Errorf("operation may mutate KRA state; explicit confirmation required") }
	headers := map[string]string{"apigee_app_id": c.appID, "Accept": "application/json", "Content-Type": "application/json"}
	for _, name := range op.Headers {
		if name == "apigee_app_id" { continue }
		if tenant[name] == "" { return nil, fmt.Errorf("missing required OSCU context: %s", name) }
		headers[name] = tenant[name]
	}
	token, err := c.tokenValue(ctx)
	if err != nil { return nil, err }
	encoded, err := json.Marshal(payload)
	if err != nil { return nil, fmt.Errorf("payload is not valid JSON") }
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, apiBase+op.Path, bytes.NewReader(encoded))
	if err != nil { return nil, fmt.Errorf("could not build KRA OSCU request") }
	for k, v := range headers { req.Header.Set(k, v) }
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := c.http.Do(req)
	if err != nil {
		if op.Mutates {
			return nil, &OscuError{Code: "oscu_outcome_unknown", Message: "KRA OSCU request outcome is unknown; reconcile before resubmitting", OutcomeUnknown: true}
		}
		return nil, &OscuError{Code: "oscu_upstream_unreachable", Message: "Could not reach KRA OSCU"}
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		if op.Mutates && resp.StatusCode >= 500 {
			return nil, &OscuError{Code: "oscu_outcome_unknown", Message: "KRA OSCU returned a server error; reconcile before resubmitting", OutcomeUnknown: true}
		}
		return nil, &OscuError{Code: "oscu_request_rejected", Message: fmt.Sprintf("KRA OSCU rejected request (HTTP %d)", resp.StatusCode)}
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		if op.Mutates { return nil, &OscuError{Code: "oscu_outcome_unknown", Message: "KRA OSCU response could not be read; reconcile before resubmitting", OutcomeUnknown: true} }
		return nil, &OscuError{Code: "oscu_response_read_failed", Message: "Could not read KRA OSCU response"}
	}
	if len(bytes.TrimSpace(body)) == 0 { return json.RawMessage("null"), nil }
	if !json.Valid(body) {
		if op.Mutates { return nil, &OscuError{Code: "oscu_outcome_unknown", Message: "KRA OSCU returned an invalid response; reconcile before resubmitting", OutcomeUnknown: true} }
		return nil, &OscuError{Code: "oscu_invalid_response", Message: "KRA OSCU returned non-JSON content"}
	}
	return json.RawMessage(body), nil
}
