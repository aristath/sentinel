package handlers

import (
	"log"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/services/evaluator-go/internal/models"
	"github.com/aristath/arduino-trader/services/evaluator-go/internal/workers"
	"github.com/gin-gonic/gin"
)

// BatchEvaluator handles batch evaluation requests
type BatchEvaluator struct {
	workerPool *workers.WorkerPool
}

// NewBatchEvaluator creates a new batch evaluator handler
func NewBatchEvaluator(numWorkers int) *BatchEvaluator {
	return &BatchEvaluator{
		workerPool: workers.NewWorkerPool(numWorkers),
	}
}

// EvaluateBatch handles POST /api/v1/evaluate/batch
func (be *BatchEvaluator) EvaluateBatch(c *gin.Context) {
	var request models.BatchEvaluationRequest

	// Parse request body
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body: " + err.Error(),
		})
		return
	}

	// Validate request
	if len(request.Sequences) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No sequences provided",
		})
		return
	}

	// Validate reasonable batch size to prevent resource exhaustion
	if len(request.Sequences) > 10000 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Too many sequences (max 10000)",
		})
		return
	}

	// Validate transaction costs are non-negative
	if request.EvaluationContext.TransactionCostFixed < 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Transaction cost fixed cannot be negative",
		})
		return
	}

	if request.EvaluationContext.TransactionCostPercent < 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Transaction cost percent cannot be negative",
		})
		return
	}

	// Evaluate sequences using worker pool
	startTime := time.Now()
	results := be.workerPool.EvaluateBatch(
		request.Sequences,
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	// Log performance metrics
	log.Printf(
		"Batch evaluation completed: %d sequences in %v (%.2f ms/sequence)",
		len(request.Sequences),
		elapsed,
		float64(elapsed.Milliseconds())/float64(len(request.Sequences)),
	)

	// Build response
	response := models.BatchEvaluationResponse{
		Results: results,
		Errors:  []string{}, // Errors per sequence (if any)
	}

	c.JSON(http.StatusOK, response)
}

// SimulateBatch handles POST /api/v1/simulate/batch
func (be *BatchEvaluator) SimulateBatch(c *gin.Context) {
	var request models.BatchSimulationRequest

	// Parse request body
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body: " + err.Error(),
		})
		return
	}

	// Validate request
	if len(request.Sequences) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No sequences provided",
		})
		return
	}

	// Validate reasonable batch size to prevent resource exhaustion
	if len(request.Sequences) > 10000 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Too many sequences (max 10000)",
		})
		return
	}

	// Simulate sequences using worker pool (parallel)
	startTime := time.Now()
	results := be.workerPool.SimulateBatch(
		request.Sequences,
		request.EvaluationContext,
	)
	elapsed := time.Since(startTime)

	// Log performance metrics
	log.Printf(
		"Batch simulation completed: %d sequences in %v (%.2f ms/sequence)",
		len(request.Sequences),
		elapsed,
		float64(elapsed.Milliseconds())/float64(len(request.Sequences)),
	)

	// Build response
	response := models.BatchSimulationResponse{
		Results: results,
	}

	c.JSON(http.StatusOK, response)
}
