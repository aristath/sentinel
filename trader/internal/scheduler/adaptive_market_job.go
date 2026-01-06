package scheduler

import (
	"database/sql"
	"encoding/json"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/adaptation"
	"github.com/aristath/arduino-trader/internal/modules/portfolio"
	"github.com/rs/zerolog"
)

// AdaptiveMarketJob checks for regime changes and triggers adaptation
// Runs daily to monitor market conditions and adapt portfolio strategy
type AdaptiveMarketJob struct {
	log                 zerolog.Logger
	regimeDetector      *portfolio.MarketRegimeDetector
	regimePersistence   *portfolio.RegimePersistence
	adaptiveService     *adaptation.AdaptiveMarketService
	adaptationThreshold float64 // Threshold for triggering adaptation (default: 0.1)
	configDB            *sql.DB // Database connection for storing adaptive parameters
}

// AdaptiveMarketJobConfig holds configuration for adaptive market job
type AdaptiveMarketJobConfig struct {
	Log                 zerolog.Logger
	RegimeDetector      *portfolio.MarketRegimeDetector
	RegimePersistence   *portfolio.RegimePersistence
	AdaptiveService     *adaptation.AdaptiveMarketService
	AdaptationThreshold float64 // Default: 0.1
	ConfigDB            *sql.DB // Database connection for storing adaptive parameters
}

// NewAdaptiveMarketJob creates a new adaptive market check job
func NewAdaptiveMarketJob(cfg AdaptiveMarketJobConfig) *AdaptiveMarketJob {
	threshold := cfg.AdaptationThreshold
	if threshold == 0 {
		threshold = 0.1 // Default threshold
	}

	return &AdaptiveMarketJob{
		log:                 cfg.Log.With().Str("job", "adaptive_market_check").Logger(),
		regimeDetector:      cfg.RegimeDetector,
		regimePersistence:   cfg.RegimePersistence,
		adaptiveService:     cfg.AdaptiveService,
		adaptationThreshold: threshold,
		configDB:            cfg.ConfigDB,
	}
}

// Name returns the job name
func (j *AdaptiveMarketJob) Name() string {
	return "adaptive_market_check"
}

// Run executes the adaptive market check
func (j *AdaptiveMarketJob) Run() error {
	j.log.Info().Msg("Starting adaptive market check")
	startTime := time.Now()

	// Step 1: Calculate current regime score from market indices
	currentScore, err := j.regimeDetector.GetRegimeScore()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get current regime score, skipping adaptation check")
		return nil // Non-critical error, don't fail the job
	}

	j.log.Info().
		Float64("current_score", float64(currentScore)).
		Msg("Calculated current regime score")

	// Step 2: Get last smoothed score for comparison
	lastScore, err := j.regimePersistence.GetCurrentRegimeScore()
	if err != nil {
		j.log.Warn().Err(err).Msg("Failed to get last regime score, using current as baseline")
		lastScore = currentScore
	}

	// Step 3: Check if adaptation is needed
	shouldAdapt := j.adaptiveService.ShouldAdapt(
		float64(currentScore),
		float64(lastScore),
		j.adaptationThreshold,
	)

	if !shouldAdapt {
		j.log.Info().
			Float64("current_score", float64(currentScore)).
			Float64("last_score", float64(lastScore)).
			Float64("threshold", j.adaptationThreshold).
			Msg("No adaptation needed - regime score change below threshold")

		duration := time.Since(startTime)
		j.log.Info().
			Dur("duration", duration).
			Msg("Adaptive market check completed (no adaptation)")
		return nil
	}

	// Step 4: Calculate and store adaptive parameters
	j.log.Info().
		Float64("current_score", float64(currentScore)).
		Float64("last_score", float64(lastScore)).
		Msg("Regime change detected - calculating adaptive parameters")

	// Calculate adaptive weights
	adaptiveWeights := j.adaptiveService.CalculateAdaptiveWeights(float64(currentScore))
	j.log.Info().
		Interface("weights", adaptiveWeights).
		Msg("Calculated adaptive scoring weights")

	// Calculate adaptive blend
	adaptiveBlend := j.adaptiveService.CalculateAdaptiveBlend(float64(currentScore))
	j.log.Info().
		Float64("blend", adaptiveBlend).
		Msg("Calculated adaptive optimizer blend")

	// Calculate adaptive quality gates
	adaptiveGates := j.adaptiveService.CalculateAdaptiveQualityGates(float64(currentScore))
	j.log.Info().
		Float64("fundamentals_threshold", adaptiveGates.GetFundamentals()).
		Float64("long_term_threshold", adaptiveGates.GetLongTerm()).
		Msg("Calculated adaptive quality gate thresholds")

	// Store adaptive parameters in database
	if j.configDB != nil {
		now := time.Now().Format(time.RFC3339)

		// Store scoring weights
		weightsJSON, err := json.Marshal(adaptiveWeights)
		if err == nil {
			_, err = j.configDB.Exec(
				`INSERT OR REPLACE INTO adaptive_parameters
				 (parameter_type, parameter_value, regime_score, adapted_at)
				 VALUES (?, ?, ?, ?)`,
				"scoring_weights", string(weightsJSON), float64(currentScore), now,
			)
			if err != nil {
				j.log.Warn().Err(err).Msg("Failed to store scoring weights")
			}
		}

		// Store optimizer blend
		blendJSON, err := json.Marshal(adaptiveBlend)
		if err == nil {
			_, err = j.configDB.Exec(
				`INSERT OR REPLACE INTO adaptive_parameters
				 (parameter_type, parameter_value, regime_score, adapted_at)
				 VALUES (?, ?, ?, ?)`,
				"optimizer_blend", string(blendJSON), float64(currentScore), now,
			)
			if err != nil {
				j.log.Warn().Err(err).Msg("Failed to store optimizer blend")
			}
		}

		// Store quality gates
		gatesJSON, err := json.Marshal(map[string]float64{
			"fundamentals": adaptiveGates.GetFundamentals(),
			"long_term":    adaptiveGates.GetLongTerm(),
		})
		if err == nil {
			_, err = j.configDB.Exec(
				`INSERT OR REPLACE INTO adaptive_parameters
				 (parameter_type, parameter_value, regime_score, adapted_at)
				 VALUES (?, ?, ?, ?)`,
				"quality_gates", string(gatesJSON), float64(currentScore), now,
			)
			if err != nil {
				j.log.Warn().Err(err).Msg("Failed to store quality gates")
			}
		}

		j.log.Info().
			Float64("regime_score", float64(currentScore)).
			Msg("Adaptive parameters stored in database")
	} else {
		j.log.Warn().Msg("ConfigDB not available - adaptive parameters not stored")
	}

	duration := time.Since(startTime)
	j.log.Info().
		Dur("duration", duration).
		Msg("Adaptive market check completed (adaptation triggered)")

	return nil
}
