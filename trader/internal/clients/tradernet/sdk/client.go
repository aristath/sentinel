package sdk

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"

	"github.com/rs/zerolog"
)

// Client represents the Tradernet SDK client
type Client struct {
	publicKey  string
	privateKey string
	baseURL    string
	httpClient *http.Client
	log        zerolog.Logger
}

// NewClient creates a new Tradernet SDK client
func NewClient(publicKey, privateKey string, log zerolog.Logger) *Client {
	return &Client{
		publicKey:  publicKey,
		privateKey: privateKey,
		baseURL:    "https://freedom24.com",
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log.With().Str("component", "tradernet-sdk").Logger(),
	}
}

// authorizedRequest makes an authenticated request to the Tradernet API
// This matches the Python SDK's authorized_request() method
func (c *Client) authorizedRequest(cmd string, params interface{}) (interface{}, error) {
	// CRITICAL: Validate credentials (matches Python SDK behavior)
	if c.publicKey == "" || c.privateKey == "" {
		return nil, fmt.Errorf("keypair is not valid")
	}

	// Step 1: JSON stringify params (no spaces, no key sorting)
	// Python SDK does: params = params or {} (handles None/empty)
	// For Go structs, empty structs serialize to {} which is correct
	payload, err := stringify(params)
	if err != nil {
		return nil, fmt.Errorf("failed to stringify params: %w", err)
	}

	// Step 2: Get timestamp in seconds (not milliseconds)
	timestamp := strconv.FormatInt(time.Now().Unix(), 10)

	// Step 3: Create message for signing: payload + timestamp (string concatenation)
	message := payload + timestamp

	// Step 4: Generate signature
	signature := sign(c.privateKey, message)

	// Step 5: Build URL
	requestURL := fmt.Sprintf("%s/api/%s", c.baseURL, cmd)

	// Step 6: Create request with JSON body
	req, err := http.NewRequest("POST", requestURL, bytes.NewReader([]byte(payload)))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Step 7: Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; TradernetSDK/2.0)")
	req.Header.Set("X-NtApi-PublicKey", c.publicKey)
	req.Header.Set("X-NtApi-Timestamp", timestamp)
	req.Header.Set("X-NtApi-Sig", signature)

	// Step 8: Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	// Step 9: Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Check HTTP status
	if resp.StatusCode != http.StatusOK {
		bodyStr := string(body)
		if len(bodyStr) > 500 {
			bodyStr = bodyStr[:500] + "..."
		}
		c.log.Error().
			Int("status_code", resp.StatusCode).
			Str("status", resp.Status).
			Str("response_body", bodyStr).
			Str("url", requestURL).
			Msg("API returned non-200 status")
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, resp.Status)
	}

	// Step 10: Parse JSON response
	// Some endpoints return arrays directly, others return objects with "result" key
	// We need to handle both cases and normalize to a consistent format
	var rawResult interface{}
	if err := json.Unmarshal(body, &rawResult); err != nil {
		bodyStr := string(body)
		if len(bodyStr) > 500 {
			bodyStr = bodyStr[:500] + "..."
		}
		c.log.Error().
			Err(err).
			Str("response_body", bodyStr).
			Str("url", requestURL).
			Msg("Failed to parse JSON response")
		return nil, fmt.Errorf("failed to parse response: %w (body: %s)", err, bodyStr)
	}

	// Step 11: Normalize response format
	// If the response is an array, wrap it in a map with "result" key
	// This ensures transformers can always expect the same format
	var result map[string]interface{}
	switch v := rawResult.(type) {
	case []interface{}:
		// API returned an array directly - wrap it in a map
		result = map[string]interface{}{
			"result": v,
		}
		c.log.Debug().
			Str("cmd", cmd).
			Int("array_length", len(v)).
			Msg("API returned array, wrapped in result key")
	case map[string]interface{}:
		// API returned a map - use as-is
		result = v
	default:
		// Unexpected type - wrap it
		result = map[string]interface{}{
			"result": v,
		}
		c.log.Debug().
			Str("cmd", cmd).
			Str("type", fmt.Sprintf("%T", v)).
			Msg("API returned unexpected type, wrapped in result key")
	}

	// Step 12: Check for error message (log but don't fail)
	if errMsg, ok := result["errMsg"].(string); ok && errMsg != "" {
		c.log.Warn().Str("err_msg", errMsg).Str("cmd", cmd).Msg("API returned error message")
	}

	return result, nil
}

// plainRequest makes an unauthenticated GET request to the Tradernet API
// Used for endpoints like findSymbol that don't require authentication
// CRITICAL: URL is /api (not /api/{cmd}), query parameter is ?q=<json>
func (c *Client) plainRequest(cmd string, params map[string]interface{}) (interface{}, error) {
	// Build message: {'cmd': cmd, 'params': params}
	message := map[string]interface{}{
		"cmd": cmd,
	}
	if len(params) > 0 {
		message["params"] = params
	}

	// JSON stringify the message
	messageJSON, err := stringify(message)
	if err != nil {
		return nil, fmt.Errorf("failed to stringify message: %w", err)
	}

	// Build URL: /api with ?q=<json>
	requestURL := fmt.Sprintf("%s/api", c.baseURL)
	u, err := url.Parse(requestURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse URL: %w", err)
	}

	q := u.Query()
	q.Set("q", messageJSON)
	u.RawQuery = q.Encode()
	requestURL = u.String()

	// Create GET request
	req, err := http.NewRequest("GET", requestURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set User-Agent to avoid Cloudflare bot protection
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; TradernetSDK/2.0)")

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check HTTP status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		bodyStr := string(body)
		if len(bodyStr) > 500 {
			bodyStr = bodyStr[:500] + "..."
		}
		c.log.Error().
			Int("status_code", resp.StatusCode).
			Str("status", resp.Status).
			Str("response_body", bodyStr).
			Str("url", requestURL).
			Msg("API returned non-200 status")
		return nil, fmt.Errorf("API returned status %d: %s", resp.StatusCode, resp.Status)
	}

	// Read response
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Parse JSON response
	// Some endpoints return arrays directly, others return objects with "result" key
	// We need to handle both cases and normalize to a consistent format
	var rawResult interface{}
	if err := json.Unmarshal(body, &rawResult); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Normalize response format
	// If the response is an array, wrap it in a map with "result" key
	var result map[string]interface{}
	switch v := rawResult.(type) {
	case []interface{}:
		// API returned an array directly - wrap it in a map
		result = map[string]interface{}{
			"result": v,
		}
	case map[string]interface{}:
		// API returned a map - use as-is
		result = v
	default:
		// Unexpected type - wrap it
		result = map[string]interface{}{
			"result": v,
		}
	}

	// Check for error message (log but don't fail)
	if errMsg, ok := result["errMsg"].(string); ok && errMsg != "" {
		c.log.Warn().Str("err_msg", errMsg).Str("cmd", cmd).Msg("API returned error message")
	}

	return result, nil
}
