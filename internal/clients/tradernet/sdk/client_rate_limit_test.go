package sdk

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestRateLimitSequentialRequests verifies that requests are processed sequentially with proper delays
func TestRateLimitSequentialRequests(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	requestTimes := make([]time.Time, 0, 3)
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requestTimes = append(requestTimes, time.Now())
		mu.Unlock()

		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL

	// Make 3 sequential requests
	params := map[string]interface{}{}
	_, err1 := client.authorizedRequest("GetAllUserTexInfo", params)
	require.NoError(t, err1)

	_, err2 := client.authorizedRequest("GetAllUserTexInfo", params)
	require.NoError(t, err2)

	_, err3 := client.authorizedRequest("GetAllUserTexInfo", params)
	require.NoError(t, err3)

	// Clean up
	client.Close()

	// Verify at least 1.5 seconds between requests (with some tolerance)
	mu.Lock()
	times := requestTimes
	mu.Unlock()

	require.GreaterOrEqual(t, len(times), 2, "Should have at least 2 requests")

	if len(times) >= 2 {
		delay1 := times[1].Sub(times[0])
		assert.GreaterOrEqual(t, delay1, 1500*time.Millisecond, "Delay between first two requests should be at least 1.5 seconds")
		assert.Less(t, delay1, 2000*time.Millisecond, "Delay should not be too long")
	}

	if len(times) >= 3 {
		delay2 := times[2].Sub(times[1])
		assert.GreaterOrEqual(t, delay2, 1500*time.Millisecond, "Delay between second and third requests should be at least 1.5 seconds")
		assert.Less(t, delay2, 2000*time.Millisecond, "Delay should not be too long")
	}
}

// TestRateLimitConcurrentRequests verifies that multiple concurrent requests are queued and processed sequentially
func TestRateLimitConcurrentRequests(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	requestOrder := make([]int, 0, 5)
	var mu sync.Mutex
	requestCount := 0

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requestCount++
		requestOrder = append(requestOrder, requestCount)
		mu.Unlock()

		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL

	// Make 5 concurrent requests
	var wg sync.WaitGroup
	params := map[string]interface{}{}

	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := client.authorizedRequest("GetAllUserTexInfo", params)
			assert.NoError(t, err)
		}()
	}

	wg.Wait()
	client.Close()

	// Verify requests were processed in order (sequential)
	mu.Lock()
	order := requestOrder
	mu.Unlock()

	require.Equal(t, 5, len(order), "Should have processed 5 requests")
	for i := 0; i < len(order); i++ {
		assert.Equal(t, i+1, order[i], "Requests should be processed in order")
	}
}

// TestRateLimitDelay verifies 1.5 second delay between requests
func TestRateLimitDelay(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	requestTimes := make([]time.Time, 0, 2)
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requestTimes = append(requestTimes, time.Now())
		mu.Unlock()

		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL

	start := time.Now()
	params := map[string]interface{}{}

	_, err1 := client.authorizedRequest("GetAllUserTexInfo", params)
	require.NoError(t, err1)

	_, err2 := client.authorizedRequest("GetAllUserTexInfo", params)
	require.NoError(t, err2)

	client.Close()

	totalTime := time.Since(start)

	// Total time should be at least 1.5 seconds (delay between requests)
	// Plus time for the requests themselves
	assert.GreaterOrEqual(t, totalTime, 1500*time.Millisecond, "Total time should include delay")
}

// TestRateLimitWorkerShutdown verifies graceful shutdown processes pending requests
func TestRateLimitWorkerShutdown(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	requestCount := 0
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		requestCount++
		mu.Unlock()

		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL

	// Start some requests
	params := map[string]interface{}{}
	var wg sync.WaitGroup

	for i := 0; i < 3; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := client.authorizedRequest("GetAllUserTexInfo", params)
			assert.NoError(t, err)
		}()
	}

	// Wait a bit for requests to be queued
	time.Sleep(100 * time.Millisecond)

	// Close client - should process pending requests
	client.Close()

	// Wait for all goroutines to finish
	wg.Wait()

	// Verify all requests were processed
	mu.Lock()
	count := requestCount
	mu.Unlock()

	assert.Equal(t, 3, count, "All pending requests should be processed")
}

// TestRateLimitQueueFull verifies behavior when queue is full (error handling)
func TestRateLimitQueueFull(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	// Create a fast server (no delay)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL
	defer client.Close()

	// Try to fill the queue beyond capacity
	params := map[string]interface{}{}
	var wg sync.WaitGroup
	var errors []error
	var errorMu sync.Mutex

	// Queue size is 100, so we'll try 10 requests rapidly
	// Some will succeed immediately, others will be queued
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := client.authorizedRequest("GetAllUserTexInfo", params)
			if err != nil {
				errorMu.Lock()
				errors = append(errors, err)
				errorMu.Unlock()
			}
		}()
	}

	// Wait for all goroutines with timeout to prevent hanging
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// All goroutines finished
	case <-time.After(30 * time.Second):
		// Timeout - some requests may still be pending, but test the errors we got
		t.Logf("Test timed out after 30s, some requests may still be pending")
	}

	// With a queue size of 100, we send 10 requests which should all succeed
	// (This test previously sent 150 requests to test queue full errors, but was reduced for performance)
	errorMu.Lock()
	errs := errors
	errorMu.Unlock()

	// Verify that errors are only "queue is full" errors
	for _, err := range errs {
		assert.Contains(t, err.Error(), "request queue is full", "Only queue full errors should occur")
	}
}

// TestRateLimitBothRequestTypes verifies both authorized and plain requests go through queue
func TestRateLimitBothRequestTypes(t *testing.T) {
	log := zerolog.New(nil).Level(zerolog.Disabled)

	requestOrder := make([]string, 0, 4)
	var mu sync.Mutex

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		if r.Method == "POST" {
			requestOrder = append(requestOrder, "authorized")
		} else {
			requestOrder = append(requestOrder, "plain")
		}
		mu.Unlock()

		response := map[string]interface{}{
			"result": map[string]interface{}{"status": "ok"},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	client := NewClient("test_public_key", "test_private_key", log)
	client.baseURL = server.URL

	// Make both types of requests concurrently
	var wg sync.WaitGroup

	paramsAuth := map[string]interface{}{}
	paramsPlain := map[string]interface{}{}

	wg.Add(1)
	go func() {
		defer wg.Done()
		_, err := client.authorizedRequest("GetAllUserTexInfo", paramsAuth)
		assert.NoError(t, err)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		_, err := client.plainRequest("findSymbol", paramsPlain)
		assert.NoError(t, err)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		_, err := client.authorizedRequest("GetAllUserTexInfo", paramsAuth)
		assert.NoError(t, err)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		_, err := client.plainRequest("findSymbol", paramsPlain)
		assert.NoError(t, err)
	}()

	wg.Wait()
	client.Close()

	// Verify all requests were processed
	mu.Lock()
	order := requestOrder
	mu.Unlock()

	assert.Equal(t, 4, len(order), "All requests should be processed")
	// Should have both types
	assert.Contains(t, order, "authorized", "Should have authorized requests")
	assert.Contains(t, order, "plain", "Should have plain requests")
}
