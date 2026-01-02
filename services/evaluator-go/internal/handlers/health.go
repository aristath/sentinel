package handlers

import (
	"net/http"

	"github.com/aristath/arduino-trader/services/evaluator-go/internal/models"
	"github.com/gin-gonic/gin"
)

const version = "0.1.0"

// HealthCheck returns service health status
func HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, models.HealthResponse{
		Status:  "healthy",
		Version: version,
	})
}
