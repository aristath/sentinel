package handlers

import (
	"log"
	"net/http"
	"time"

	"github.com/aristath/arduino-trader/services/evaluator-go/internal/evaluation"
	"github.com/aristath/arduino-trader/services/evaluator-go/internal/models"
	"github.com/gin-gonic/gin"
)

// AdvancedEvaluator handles advanced evaluation requests (Monte Carlo, Stochastic)
type AdvancedEvaluator struct{}

// NewAdvancedEvaluator creates a new advanced evaluator handler
func NewAdvancedEvaluator() *AdvancedEvaluator {
	return &AdvancedEvaluator{}
}

// EvaluateMonteCarlo handles POST /api/v1/evaluate/monte-carlo
func (ae *AdvancedEvaluator) EvaluateMonteCarlo(c *gin.Context) {
	var request models.MonteCarloRequest

	// Parse request body
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body: " + err.Error(),
		})
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No sequence provided",
		})
		return
	}

	if request.Paths <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Paths must be greater than 0",
		})
		return
	}

	if request.Paths > 1000 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Paths must be 1000 or less (recommended: 100-500)",
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

	// Evaluate using Monte Carlo simulation
	startTime := time.Now()
	result := evaluation.EvaluateMonteCarlo(request)
	elapsed := time.Since(startTime)

	// Log performance metrics
	log.Printf(
		"Monte Carlo evaluation completed: %d paths in %v (%.2f ms/path)",
		request.Paths,
		elapsed,
		float64(elapsed.Milliseconds())/float64(request.Paths),
	)

	c.JSON(http.StatusOK, result)
}

// EvaluateStochastic handles POST /api/v1/evaluate/stochastic
func (ae *AdvancedEvaluator) EvaluateStochastic(c *gin.Context) {
	var request models.StochasticRequest

	// Parse request body
	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request body: " + err.Error(),
		})
		return
	}

	// Validate request
	if len(request.Sequence) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No sequence provided",
		})
		return
	}

	if len(request.Shifts) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "No shifts provided",
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

	// Evaluate using stochastic scenarios
	startTime := time.Now()
	result := evaluation.EvaluateStochastic(request)
	elapsed := time.Since(startTime)

	// Log performance metrics
	log.Printf(
		"Stochastic evaluation completed: %d scenarios in %v (%.2f ms/scenario)",
		len(request.Shifts),
		elapsed,
		float64(elapsed.Milliseconds())/float64(len(request.Shifts)),
	)

	c.JSON(http.StatusOK, result)
}
