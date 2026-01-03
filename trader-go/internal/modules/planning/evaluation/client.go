package evaluation

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/rs/zerolog"
)

// Client communicates with the Go evaluation service (evaluator on port 8001).
type Client struct {
	baseURL    string
	httpClient *http.Client
	log        zerolog.Logger
}

// NewClient creates a new evaluation service client.
func NewClient(baseURL string, log zerolog.Logger) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 60 * time.Second, // Evaluation can take time
		},
		log: log.With().Str("component", "evaluation_client").Logger(),
	}
}

// BatchEvaluateRequest represents the request payload for batch evaluation.
type BatchEvaluateRequest struct {
	Sequences       []domain.ActionSequence `json:"sequences"`
	PortfolioHash   string                  `json:"portfolio_hash"`
	UseMonteCarlo   bool                    `json:"use_monte_carlo,omitempty"`
	UseStochastic   bool                    `json:"use_stochastic,omitempty"`
	ParallelWorkers int                     `json:"parallel_workers,omitempty"`
}

// BatchEvaluateResponse represents the response from batch evaluation.
type BatchEvaluateResponse struct {
	Results []domain.EvaluationResult `json:"results"`
	Elapsed float64                   `json:"elapsed_seconds"`
}

// BatchEvaluate sends a batch of sequences to the evaluation service.
func (c *Client) BatchEvaluate(ctx context.Context, sequences []domain.ActionSequence, portfolioHash string) ([]domain.EvaluationResult, error) {
	if len(sequences) == 0 {
		return nil, fmt.Errorf("no sequences to evaluate")
	}

	c.log.Debug().
		Int("sequence_count", len(sequences)).
		Str("portfolio_hash", portfolioHash).
		Msg("Sending batch evaluation request")

	// Prepare request
	req := BatchEvaluateRequest{
		Sequences:       sequences,
		PortfolioHash:   portfolioHash,
		UseMonteCarlo:   false, // Default to faster evaluation
		UseStochastic:   false,
		ParallelWorkers: 4, // Use 4 workers by default
	}

	// Marshal request
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	url := fmt.Sprintf("%s/api/v1/evaluate/batch", c.baseURL)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Send request
	startTime := time.Now()
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	// Check status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("evaluation service returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var response BatchEvaluateResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	c.log.Info().
		Int("sequence_count", len(sequences)).
		Int("result_count", len(response.Results)).
		Float64("elapsed_seconds", time.Since(startTime).Seconds()).
		Float64("service_elapsed", response.Elapsed).
		Msg("Batch evaluation complete")

	return response.Results, nil
}

// EvaluateSingleSequence evaluates a single sequence and returns the result.
func (c *Client) EvaluateSingleSequence(ctx context.Context, sequence domain.ActionSequence, portfolioHash string) (*domain.EvaluationResult, error) {
	results, err := c.BatchEvaluate(ctx, []domain.ActionSequence{sequence}, portfolioHash)
	if err != nil {
		return nil, err
	}

	if len(results) == 0 {
		return nil, fmt.Errorf("no evaluation result returned")
	}

	return &results[0], nil
}

// HealthCheck checks if the evaluation service is available.
func (c *Client) HealthCheck(ctx context.Context) error {
	url := fmt.Sprintf("%s/health", c.baseURL)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("failed to create health check request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned status %d", resp.StatusCode)
	}

	c.log.Debug().Msg("Evaluation service health check passed")
	return nil
}

// BatchEvaluateWithOptions provides more control over evaluation parameters.
func (c *Client) BatchEvaluateWithOptions(ctx context.Context, sequences []domain.ActionSequence, portfolioHash string, opts EvaluationOptions) ([]domain.EvaluationResult, error) {
	if len(sequences) == 0 {
		return nil, fmt.Errorf("no sequences to evaluate")
	}

	c.log.Debug().
		Int("sequence_count", len(sequences)).
		Str("portfolio_hash", portfolioHash).
		Bool("monte_carlo", opts.UseMonteCarlo).
		Bool("stochastic", opts.UseStochastic).
		Msg("Sending batch evaluation request with options")

	// Prepare request
	req := BatchEvaluateRequest{
		Sequences:       sequences,
		PortfolioHash:   portfolioHash,
		UseMonteCarlo:   opts.UseMonteCarlo,
		UseStochastic:   opts.UseStochastic,
		ParallelWorkers: opts.ParallelWorkers,
	}

	// Marshal request
	reqBody, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create HTTP request
	url := fmt.Sprintf("%s/api/v1/evaluate/batch", c.baseURL)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Send request
	startTime := time.Now()
	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	// Check status
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("evaluation service returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse response
	var response BatchEvaluateResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	c.log.Info().
		Int("sequence_count", len(sequences)).
		Int("result_count", len(response.Results)).
		Float64("elapsed_seconds", time.Since(startTime).Seconds()).
		Float64("service_elapsed", response.Elapsed).
		Msg("Batch evaluation with options complete")

	return response.Results, nil
}

// EvaluationOptions configures evaluation behavior.
type EvaluationOptions struct {
	UseMonteCarlo   bool
	UseStochastic   bool
	ParallelWorkers int
}

// DefaultEvaluationOptions returns sensible defaults for evaluation.
func DefaultEvaluationOptions() EvaluationOptions {
	return EvaluationOptions{
		UseMonteCarlo:   false, // Faster without Monte Carlo
		UseStochastic:   false, // Faster without stochastic scenarios
		ParallelWorkers: 4,     // 4 workers for good parallelism
	}
}
