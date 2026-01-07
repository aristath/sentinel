package symbolic_regression

import (
	"fmt"
	"time"

	"github.com/rs/zerolog"
)

// DiscoveryService orchestrates formula discovery using genetic programming
type DiscoveryService struct {
	dataPrep *DataPrep
	storage  *FormulaStorage
	log      zerolog.Logger
}

// NewDiscoveryService creates a new discovery service
func NewDiscoveryService(
	dataPrep *DataPrep,
	storage *FormulaStorage,
	log zerolog.Logger,
) *DiscoveryService {
	return &DiscoveryService{
		dataPrep: dataPrep,
		storage:  storage,
		log:      log.With().Str("component", "formula_discovery").Logger(),
	}
}

// DiscoverExpectedReturnFormula discovers optimal expected return formula
// If regimeRanges is provided, discovers separate formulas for each regime range
func (ds *DiscoveryService) DiscoverExpectedReturnFormula(
	securityType SecurityType,
	startDate time.Time,
	endDate time.Time,
	forwardMonths int,
	regimeRanges []RegimeRange, // Optional: if nil, discovers single formula; if provided, discovers per regime
) ([]*DiscoveredFormula, error) {
	ds.log.Info().
		Str("security_type", string(securityType)).
		Str("start_date", startDate.Format("2006-01-02")).
		Str("end_date", endDate.Format("2006-01-02")).
		Int("forward_months", forwardMonths).
		Int("regime_ranges", len(regimeRanges)).
		Msg("Starting expected return formula discovery")

	// Extract training examples
	examplesByDate, err := ds.dataPrep.ExtractAllTrainingExamples(
		startDate,
		endDate,
		1, // Extract monthly
		forwardMonths,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to extract training examples: %w", err)
	}

	// Flatten examples and filter by security type
	var allExamples []TrainingExample
	for _, examples := range examplesByDate {
		filtered := FilterBySecurityType(examples, securityType)
		allExamples = append(allExamples, filtered...)
	}

	if len(allExamples) == 0 {
		return nil, fmt.Errorf("no training examples found for security type %s", securityType)
	}

	// Normalize features
	normalized := NormalizeFeatures(allExamples)
	validated := ValidateTrainingExamples(normalized)

	if len(validated) == 0 {
		return nil, fmt.Errorf("no valid training examples after validation")
	}

	ds.log.Info().
		Int("total_examples", len(validated)).
		Msg("Extracted and validated training examples")

	var discoveredFormulas []*DiscoveredFormula

	// If regime ranges provided, discover separate formulas for each regime
	if len(regimeRanges) > 0 {
		splitExamples := SplitByRegime(validated, regimeRanges)

		for _, regimeRange := range regimeRanges {
			regimeExamples := splitExamples[regimeRange]

			if len(regimeExamples) < 10 {
				ds.log.Debug().
					Str("regime", regimeRange.Name).
					Int("examples", len(regimeExamples)).
					Msg("Insufficient examples for regime, skipping")
				continue
			}

			ds.log.Info().
				Str("regime", regimeRange.Name).
				Float64("min", regimeRange.Min).
				Float64("max", regimeRange.Max).
				Int("examples", len(regimeExamples)).
				Msg("Discovering formula for regime range")

			// Define variables for formula discovery
			variables := ExtractFeatureNames(regimeExamples[0].Inputs)

			// Configure evolution
			config := EvolutionConfig{
				PopulationSize:   100,
				MaxGenerations:   50,
				MaxDepth:         4,
				MaxNodes:         10,
				MutationRate:     0.1,
				CrossoverRate:    0.7,
				TournamentSize:   3,
				ElitismCount:     5,
				FitnessType:      FitnessTypeMAE, // Minimize prediction error
				ComplexityWeight: 0.01,           // Small complexity penalty
			}

			// Run evolution
			best := RunEvolution(variables, regimeExamples, config)

			if best == nil || best.Formula == nil {
				ds.log.Warn().
					Str("regime", regimeRange.Name).
					Msg("Evolution failed for regime, skipping")
				continue
			}

			ds.log.Info().
				Str("regime", regimeRange.Name).
				Float64("fitness", best.Fitness).
				Int("complexity", best.Complexity).
				Str("formula", best.Formula.String()).
				Msg("Discovered expected return formula for regime")

			// Calculate validation metrics
			metrics := ds.calculateValidationMetrics(best.Formula, regimeExamples)

			// Validate against static formula
			validationResult, validationErr := ds.validateAgainstStaticFormula(
				best.Formula,
				regimeExamples,
				FormulaTypeExpectedReturn,
				FitnessTypeMAE,
			)

			// Determine if formula should be active based on validation
			isActive := false
			if validationErr == nil && validationResult != nil && validationResult.IsBetter {
				isActive = true
				ds.log.Info().
					Str("regime", regimeRange.Name).
					Float64("improvement_pct", validationResult.ImprovementPct).
					Msg("Discovered formula outperforms static formula, activating")
			} else {
				if validationErr != nil {
					ds.log.Warn().
						Str("regime", regimeRange.Name).
						Err(validationErr).
						Msg("Validation failed, saving formula as inactive")
				} else if validationResult != nil && !validationResult.IsBetter {
					ds.log.Warn().
						Str("regime", regimeRange.Name).
						Float64("improvement_pct", validationResult.ImprovementPct).
						Msg("Discovered formula does not outperform static formula, saving as inactive")
				}
			}

			// Create discovered formula with regime range
			// Ensure fitness and complexity are in metrics (used by SaveFormula)
			metrics["fitness"] = best.Fitness
			metrics["complexity"] = float64(best.Complexity)
			discovered := &DiscoveredFormula{
				FormulaType:       FormulaTypeExpectedReturn,
				SecurityType:      securityType,
				RegimeRangeMin:    &regimeRange.Min,
				RegimeRangeMax:    &regimeRange.Max,
				FormulaExpression: best.Formula.String(),
				ValidationMetrics: metrics,
				DiscoveredAt:      time.Now(),
			}

			// Save to database with appropriate is_active status
			_, err = ds.storage.SaveFormula(discovered, isActive)
			if err != nil {
				ds.log.Warn().Err(err).Str("regime", regimeRange.Name).Msg("Failed to save discovered formula")
				continue
			}

			discoveredFormulas = append(discoveredFormulas, discovered)
		}
	} else {
		// No regime ranges - discover single formula for all data
		// Define variables for formula discovery
		variables := ExtractFeatureNames(validated[0].Inputs)

		// Configure evolution
		config := EvolutionConfig{
			PopulationSize:   100,
			MaxGenerations:   50,
			MaxDepth:         4,
			MaxNodes:         10,
			MutationRate:     0.1,
			CrossoverRate:    0.7,
			TournamentSize:   3,
			ElitismCount:     5,
			FitnessType:      FitnessTypeMAE, // Minimize prediction error
			ComplexityWeight: 0.01,           // Small complexity penalty
		}

		// Run evolution
		best := RunEvolution(variables, validated, config)

		if best == nil || best.Formula == nil {
			return nil, fmt.Errorf("evolution failed to produce a valid formula")
		}

		ds.log.Info().
			Float64("fitness", best.Fitness).
			Int("complexity", best.Complexity).
			Str("formula", best.Formula.String()).
			Msg("Discovered expected return formula")

		// Calculate validation metrics
		metrics := ds.calculateValidationMetrics(best.Formula, validated)

		// Validate against static formula
		validationResult, validationErr := ds.validateAgainstStaticFormula(
			best.Formula,
			validated,
			FormulaTypeExpectedReturn,
			FitnessTypeMAE,
		)

		// Determine if formula should be active based on validation
		isActive := false
		if validationErr == nil && validationResult != nil && validationResult.IsBetter {
			isActive = true
			ds.log.Info().
				Float64("improvement_pct", validationResult.ImprovementPct).
				Msg("Discovered formula outperforms static formula, activating")
		} else {
			if validationErr != nil {
				ds.log.Warn().
					Err(validationErr).
					Msg("Validation failed, saving formula as inactive")
			} else if validationResult != nil && !validationResult.IsBetter {
				ds.log.Warn().
					Float64("improvement_pct", validationResult.ImprovementPct).
					Msg("Discovered formula does not outperform static formula, saving as inactive")
			}
		}

		// Create discovered formula (no regime range)
		// Ensure fitness and complexity are in metrics (used by SaveFormula)
		metrics["fitness"] = best.Fitness
		metrics["complexity"] = float64(best.Complexity)
		discovered := &DiscoveredFormula{
			FormulaType:       FormulaTypeExpectedReturn,
			SecurityType:      securityType,
			FormulaExpression: best.Formula.String(),
			ValidationMetrics: metrics,
			DiscoveredAt:      time.Now(),
		}

		// Save to database with appropriate is_active status
		_, err = ds.storage.SaveFormula(discovered, isActive)
		if err != nil {
			ds.log.Warn().Err(err).Msg("Failed to save discovered formula")
		}

		discoveredFormulas = append(discoveredFormulas, discovered)
	}

	if len(discoveredFormulas) == 0 {
		return nil, fmt.Errorf("no formulas discovered")
	}

	return discoveredFormulas, nil
}

// DiscoverScoringFormula discovers optimal scoring formula
// If regimeRanges is provided, discovers separate formulas for each regime range
func (ds *DiscoveryService) DiscoverScoringFormula(
	securityType SecurityType,
	startDate time.Time,
	endDate time.Time,
	forwardMonths int,
	regimeRanges []RegimeRange, // Optional: if nil, discovers single formula; if provided, discovers per regime
) ([]*DiscoveredFormula, error) {
	ds.log.Info().
		Str("security_type", string(securityType)).
		Int("regime_ranges", len(regimeRanges)).
		Msg("Starting scoring formula discovery")

	// Extract training examples
	examplesByDate, err := ds.dataPrep.ExtractAllTrainingExamples(
		startDate,
		endDate,
		1, // Extract monthly
		forwardMonths,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to extract training examples: %w", err)
	}

	// Flatten and filter
	var allExamples []TrainingExample
	for _, examples := range examplesByDate {
		filtered := FilterBySecurityType(examples, securityType)
		allExamples = append(allExamples, filtered...)
	}

	if len(allExamples) == 0 {
		return nil, fmt.Errorf("no training examples found")
	}

	// Normalize features
	normalized := NormalizeFeatures(allExamples)
	validated := ValidateTrainingExamples(normalized)

	if len(validated) == 0 {
		return nil, fmt.Errorf("no valid training examples")
	}

	var discoveredFormulas []*DiscoveredFormula

	// For scoring, we optimize ranking quality (Spearman correlation)
	// Variables are scoring components
	variables := []string{
		"long_term", "fundamentals", "dividends", "opportunity",
		"short_term", "technicals", "opinion", "diversification",
	}

	// If regime ranges provided, discover separate formulas for each regime
	if len(regimeRanges) > 0 {
		splitExamples := SplitByRegime(validated, regimeRanges)

		for _, regimeRange := range regimeRanges {
			regimeExamples := splitExamples[regimeRange]

			if len(regimeExamples) < 10 {
				ds.log.Debug().
					Str("regime", regimeRange.Name).
					Int("examples", len(regimeExamples)).
					Msg("Insufficient examples for regime, skipping")
				continue
			}

			ds.log.Info().
				Str("regime", regimeRange.Name).
				Float64("min", regimeRange.Min).
				Float64("max", regimeRange.Max).
				Int("examples", len(regimeExamples)).
				Msg("Discovering scoring formula for regime range")

			// Configure evolution for ranking optimization
			config := EvolutionConfig{
				PopulationSize:   100,
				MaxGenerations:   50,
				MaxDepth:         4,
				MaxNodes:         10,
				MutationRate:     0.1,
				CrossoverRate:    0.7,
				TournamentSize:   3,
				ElitismCount:     5,
				FitnessType:      FitnessTypeSpearman, // Maximize ranking correlation
				ComplexityWeight: 0.01,
			}

			// Run evolution
			best := RunEvolution(variables, regimeExamples, config)

			if best == nil || best.Formula == nil {
				ds.log.Warn().
					Str("regime", regimeRange.Name).
					Msg("Evolution failed for regime, skipping")
				continue
			}

			ds.log.Info().
				Str("regime", regimeRange.Name).
				Float64("fitness", best.Fitness).
				Str("formula", best.Formula.String()).
				Msg("Discovered scoring formula for regime")

			// Calculate validation metrics
			metrics := ds.calculateValidationMetrics(best.Formula, regimeExamples)

			// Validate against static formula
			validationResult, validationErr := ds.validateAgainstStaticFormula(
				best.Formula,
				regimeExamples,
				FormulaTypeScoring,
				FitnessTypeSpearman,
			)

			// Determine if formula should be active based on validation
			isActive := false
			if validationErr == nil && validationResult != nil && validationResult.IsBetter {
				isActive = true
				ds.log.Info().
					Str("regime", regimeRange.Name).
					Float64("improvement_pct", validationResult.ImprovementPct).
					Msg("Discovered scoring formula outperforms static formula, activating")
			} else {
				if validationErr != nil {
					ds.log.Warn().
						Str("regime", regimeRange.Name).
						Err(validationErr).
						Msg("Validation failed, saving scoring formula as inactive")
				} else if validationResult != nil && !validationResult.IsBetter {
					ds.log.Warn().
						Str("regime", regimeRange.Name).
						Float64("improvement_pct", validationResult.ImprovementPct).
						Msg("Discovered scoring formula does not outperform static formula, saving as inactive")
				}
			}

			// Create discovered formula with regime range
			// Ensure fitness and complexity are in metrics (used by SaveFormula)
			metrics["fitness"] = best.Fitness
			metrics["complexity"] = float64(best.Complexity)
			discovered := &DiscoveredFormula{
				FormulaType:       FormulaTypeScoring,
				SecurityType:      securityType,
				RegimeRangeMin:    &regimeRange.Min,
				RegimeRangeMax:    &regimeRange.Max,
				FormulaExpression: best.Formula.String(),
				ValidationMetrics: metrics,
				DiscoveredAt:      time.Now(),
			}

			// Save to database with appropriate is_active status
			_, err = ds.storage.SaveFormula(discovered, isActive)
			if err != nil {
				ds.log.Warn().Err(err).Str("regime", regimeRange.Name).Msg("Failed to save discovered formula")
				continue
			}

			discoveredFormulas = append(discoveredFormulas, discovered)
		}
	} else {
		// No regime ranges - discover single formula for all data
		// Configure evolution for ranking optimization
		config := EvolutionConfig{
			PopulationSize:   100,
			MaxGenerations:   50,
			MaxDepth:         4,
			MaxNodes:         10,
			MutationRate:     0.1,
			CrossoverRate:    0.7,
			TournamentSize:   3,
			ElitismCount:     5,
			FitnessType:      FitnessTypeSpearman, // Maximize ranking correlation
			ComplexityWeight: 0.01,
		}

		// Run evolution
		best := RunEvolution(variables, validated, config)

		if best == nil || best.Formula == nil {
			return nil, fmt.Errorf("evolution failed")
		}

		ds.log.Info().
			Float64("fitness", best.Fitness).
			Str("formula", best.Formula.String()).
			Msg("Discovered scoring formula")

		// Calculate validation metrics
		metrics := ds.calculateValidationMetrics(best.Formula, validated)

		// Validate against static formula
		validationResult, validationErr := ds.validateAgainstStaticFormula(
			best.Formula,
			validated,
			FormulaTypeScoring,
			FitnessTypeSpearman,
		)

		// Determine if formula should be active based on validation
		isActive := false
		if validationErr == nil && validationResult != nil && validationResult.IsBetter {
			isActive = true
			ds.log.Info().
				Float64("improvement_pct", validationResult.ImprovementPct).
				Msg("Discovered scoring formula outperforms static formula, activating")
		} else {
			if validationErr != nil {
				ds.log.Warn().
					Err(validationErr).
					Msg("Validation failed, saving scoring formula as inactive")
			} else if validationResult != nil && !validationResult.IsBetter {
				ds.log.Warn().
					Float64("improvement_pct", validationResult.ImprovementPct).
					Msg("Discovered scoring formula does not outperform static formula, saving as inactive")
			}
		}

		// Create discovered formula (no regime range)
		// Ensure fitness and complexity are in metrics (used by SaveFormula)
		metrics["fitness"] = best.Fitness
		metrics["complexity"] = float64(best.Complexity)
		discovered := &DiscoveredFormula{
			FormulaType:       FormulaTypeScoring,
			SecurityType:      securityType,
			FormulaExpression: best.Formula.String(),
			ValidationMetrics: metrics,
			DiscoveredAt:      time.Now(),
		}

		// Save to database with appropriate is_active status
		_, err = ds.storage.SaveFormula(discovered, isActive)
		if err != nil {
			ds.log.Warn().Err(err).Msg("Failed to save discovered formula")
		}

		discoveredFormulas = append(discoveredFormulas, discovered)
	}

	if len(discoveredFormulas) == 0 {
		return nil, fmt.Errorf("no formulas discovered")
	}

	return discoveredFormulas, nil
}

// calculateValidationMetrics calculates comprehensive validation metrics
func (ds *DiscoveryService) calculateValidationMetrics(
	formula *Node,
	examples []TrainingExample,
) map[string]float64 {
	metrics := make(map[string]float64)

	// Calculate MAE
	mae := CalculateFitness(formula, examples, FitnessTypeMAE)
	metrics["mae"] = mae

	// Calculate RMSE
	rmse := CalculateFitness(formula, examples, FitnessTypeRMSE)
	metrics["rmse"] = rmse

	// Calculate Spearman correlation (for ranking quality)
	spearmanFitness := CalculateFitness(formula, examples, FitnessTypeSpearman)
	spearmanCorr := 1.0 - spearmanFitness // Convert back to correlation
	metrics["spearman"] = spearmanCorr

	// Calculate complexity
	complexity := CalculateComplexity(formula)
	metrics["complexity"] = float64(complexity)

	// Store fitness
	metrics["fitness"] = mae // Use MAE as primary fitness

	return metrics
}

// validateAgainstStaticFormula validates a discovered formula against the static formula
// Returns ValidationResult and error. If test set has < 10 examples, returns error.
func (ds *DiscoveryService) validateAgainstStaticFormula(
	discoveredFormula *Node,
	examples []TrainingExample,
	formulaType FormulaType,
	fitnessType FitnessType,
) (*ValidationResult, error) {
	// Split examples into train/test (80/20 split)
	// Need at least 50 examples to guarantee 10 test examples (50 * 0.2 = 10)
	if len(examples) < 50 {
		return nil, fmt.Errorf("insufficient examples for validation: need at least 50 for train/test split (80/20), got %d", len(examples))
	}

	splitIdx := int(float64(len(examples)) * 0.8)
	if splitIdx < 1 {
		splitIdx = 1
	}

	trainExamples := examples[:splitIdx]
	testExamples := examples[splitIdx:]

	// Double-check test set has sufficient examples (should always pass with >= 50 examples)
	if len(testExamples) < 10 {
		return nil, fmt.Errorf("insufficient test examples for validation: need at least 10, got %d (this should not happen with >= 50 examples)", len(testExamples))
	}

	// Build appropriate static formula based on formula type
	var staticFormula *Node
	if formulaType == FormulaTypeExpectedReturn {
		staticFormula = BuildStaticExpectedReturnFormula()
	} else if formulaType == FormulaTypeScoring {
		staticFormula = BuildStaticScoringFormula()
	} else {
		return nil, fmt.Errorf("unknown formula type: %s", formulaType)
	}

	// Validate discovered formula against static formula
	result, err := ValidateDiscoveredFormula(
		discoveredFormula,
		staticFormula,
		trainExamples,
		testExamples,
		fitnessType,
	)
	if err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}

	return result, nil
}
