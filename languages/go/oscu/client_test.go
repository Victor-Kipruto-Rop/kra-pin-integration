package oscu

import (
	"context"
	"errors"
	"io"
	"net/http"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)
func (fn roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) { return fn(req) }

func TestManifestContains23Operations(t *testing.T) {
	client, err := NewClient("key", "secret", "app", &http.Client{})
	if err != nil { t.Fatal(err) }
	if len(client.operations) != 23 { t.Fatalf("expected 23 operations, got %d", len(client.operations)) }
}

func TestMutationRequiresConfirmationBeforeNetwork(t *testing.T) {
	called := false
	httpClient := &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		called = true
		return nil, nil
	})}
	client, err := NewClient("key", "secret", "app", httpClient)
	if err != nil { t.Fatal(err) }
	_, err = client.Invoke(context.Background(), "save-item", map[string]any{}, map[string]string{"tin":"P1","bhfId":"00","cmcKey":"k"}, false)
	if err == nil || !strings.Contains(err.Error(), "confirmation") { t.Fatalf("expected mutation guard, got %v", err) }
	if called { t.Fatal("network must not be called before mutation confirmation") }
}

func TestInitializationUsesOnlyAppIdHeader(t *testing.T) {
	client, err := NewClient("key", "secret", "app", &http.Client{})
	if err != nil { t.Fatal(err) }
	op := client.operations["oscu-initialization"]
	if len(op.Headers) != 1 || op.Headers[0] != "apigee_app_id" { t.Fatalf("unexpected headers: %#v", op.Headers) }
}

func TestReadOnlyOperationUsesFixedSandboxHostAndBearerToken(t *testing.T) {
	client, err := NewClient("key", "secret", "app", &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		body := `{"access_token":"token","expires_in":3600}`
		if strings.Contains(req.URL.Path, "/etims-oscu/") {
			if req.URL.Host != "sbx.kra.go.ke" || req.Header.Get("Authorization") != "Bearer token" { t.Errorf("unexpected operation request: %s %s", req.URL, req.Header.Get("Authorization")) }
			if req.Header.Get("tin") != "P123" || req.Header.Get("apigee_app_id") != "app" { t.Errorf("missing headers") }
			body = `{"ok":true}`
		} else if req.URL.Host != "sbx.kra.go.ke" || req.Header.Get("Authorization") == "" { t.Errorf("token request missing basic auth") }
		return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(body)), Request: req}, nil
	})})
	if err != nil { t.Fatal(err) }
	got, err := client.Invoke(context.Background(), "branch-list", map[string]any{}, map[string]string{"tin":"P123","bhfId":"00","cmcKey":"secret"}, false)
	if err != nil { t.Fatal(err) }
	if string(got) != `{"ok":true}` { t.Fatalf("unexpected response: %s", got) }
}

func TestReadOnlyTransportFailureIsNotMarkedUnknownMutation(t *testing.T) {
	calls := 0
	client, err := NewClient("key", "secret", "app", &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		calls++
		if calls == 1 {
			return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(`{"access_token":"token","expires_in":3600}`)), Request: req}, nil
		}
		return nil, errors.New("simulated transport failure")
	})})
	if err != nil { t.Fatal(err) }
	_, err = client.Invoke(context.Background(), "branch-list", map[string]any{}, map[string]string{"tin":"P1","bhfId":"00","cmcKey":"x"}, false)
	apiErr, ok := err.(*OscuError)
	if !ok || apiErr.Code != "oscu_upstream_unreachable" || apiErr.OutcomeUnknown { t.Fatalf("unexpected error: %#v", err) }
}

func TestMutationTransportFailureIsMarkedUnknown(t *testing.T) {
	calls := 0
	client, err := NewClient("key", "secret", "app", &http.Client{Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
		calls++
		if calls == 1 {
			return &http.Response{StatusCode: 200, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(`{"access_token":"token","expires_in":3600}`)), Request: req}, nil
		}
		return nil, errors.New("simulated transport failure")
	})})
	if err != nil { t.Fatal(err) }
	_, err = client.Invoke(context.Background(), "save-item", map[string]any{}, map[string]string{"tin":"P1","bhfId":"00","cmcKey":"x"}, true)
	apiErr, ok := err.(*OscuError)
	if !ok || apiErr.Code != "oscu_outcome_unknown" || !apiErr.OutcomeUnknown { t.Fatalf("unexpected error: %#v", err) }
}
