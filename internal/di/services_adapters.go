/**
 * Package di provides adapter type definitions for service implementations.
 *
 * This file contains all adapter types that bridge interface mismatches between
 * different packages. Adapters are needed because Go doesn't support return type
 * covariance in interfaces, and different packages may define similar but incompatible
 * interfaces for the same concept.
 */
package di

import (
	"database/sql"
	"fmt"
	"math"
	"strings"

	"github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/market_regime"
	"github.com/aristath/sentinel/internal/modules/adaptation"
	"github.com/aristath/sentinel/internal/modules/optimization"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	planningrepo "github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
)

// securitySetupServiceAdapter adapts universe.SecuritySetupService to portfolio.SecuritySetupServiceInterface.
//
// This adapter is needed because Go doesn't support return type covariance in interfaces.
// The portfolio package expects a different interface signature than what universe provides.
//
// Note: User-configurable fields (min_lot, allow_buy, allow_sell) are set via security_overrides
// after security creation, not during the AddSecurityByIdentifier call.
type securitySetupServiceAdapter struct {
	service *universe.SecuritySetupService
}

// AddSecurityByIdentifier implements portfolio.SecuritySetupServiceInterface.
//
// Delegates to the underlying universe.SecuritySetupService.
func (a *securitySetupServiceAdapter) AddSecurityByIdentifier(identifier string) (interface{}, error) {
	return a.service.AddSecurityByIdentifier(identifier)
}

// qualityGatesAdapter adapts adaptation.AdaptiveMarketService to universe.AdaptiveQualityGatesProvider
type qualityGatesAdapter struct {
	service *adaptation.AdaptiveMarketService
}

func (a *qualityGatesAdapter) CalculateAdaptiveQualityGates(regimeScore float64) universe.QualityGateThresholdsProvider {
	thresholds := a.service.CalculateAdaptiveQualityGates(regimeScore)
	return thresholds // *adaptation.QualityGateThresholds implements the interface via GetStability/GetLongTerm
}

// kellySettingsAdapter adapts settings.Service to optimization.KellySettingsService
type kellySettingsAdapter struct {
	service *settings.Service
}

func (a *kellySettingsAdapter) GetAdjustedKellyParams() optimization.KellyParamsConfig {
	params := a.service.GetAdjustedKellyParams()
	return optimization.KellyParamsConfig{
		FixedFractional:           params.FixedFractional,
		MinPositionSize:           params.MinPositionSize,
		MaxPositionSize:           params.MaxPositionSize,
		BearReduction:             params.BearReduction,
		BaseMultiplier:            params.BaseMultiplier,
		ConfidenceAdjustmentRange: params.ConfidenceAdjustmentRange,
		RegimeAdjustmentRange:     params.RegimeAdjustmentRange,
		MinMultiplier:             params.MinMultiplier,
		MaxMultiplier:             params.MaxMultiplier,
		BearMaxReduction:          params.BearMaxReduction,
		BullThreshold:             params.BullThreshold,
		BearThreshold:             params.BearThreshold,
	}
}

// tagSettingsAdapter adapts settings.Service to universe.TagSettingsService
type tagSettingsAdapter struct {
	service *settings.Service
}

func (a *tagSettingsAdapter) GetAdjustedValueThresholds() universe.ValueThresholds {
	params := a.service.GetAdjustedValueThresholds()
	return universe.ValueThresholds{
		ValueOpportunityDiscountPct: params.ValueOpportunityDiscountPct,
		DeepValueDiscountPct:        params.DeepValueDiscountPct,
		DeepValueExtremePct:         params.DeepValueExtremePct,
		Below52wHighThreshold:       params.Below52wHighThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityThresholds() universe.QualityThresholds {
	params := a.service.GetAdjustedQualityThresholds()
	return universe.QualityThresholds{
		HighQualityStability:           params.HighQualityStability,
		HighQualityLongTerm:            params.HighQualityLongTerm,
		StableStability:                params.StableStability,
		StableVolatilityMax:            params.StableVolatilityMax,
		StableConsistency:              params.StableConsistency,
		ConsistentGrowerConsistency:    params.ConsistentGrowerConsistency,
		ConsistentGrowerCAGR:           params.ConsistentGrowerCAGR,
		HighStabilityThreshold:         params.HighStabilityThreshold,
		ValueOpportunityScoreThreshold: params.ValueOpportunityScoreThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedTechnicalThresholds() universe.TechnicalThresholds {
	params := a.service.GetAdjustedTechnicalThresholds()
	return universe.TechnicalThresholds{
		RSIOversold:               params.RSIOversold,
		RSIOverbought:             params.RSIOverbought,
		RecoveryMomentumThreshold: params.RecoveryMomentumThreshold,
		RecoveryStabilityMin:      params.RecoveryStabilityMin,
		RecoveryDiscountMin:       params.RecoveryDiscountMin,
	}
}

func (a *tagSettingsAdapter) GetAdjustedDividendThresholds() universe.DividendThresholds {
	params := a.service.GetAdjustedDividendThresholds()
	return universe.DividendThresholds{
		HighDividendYield:        params.HighDividendYield,
		DividendOpportunityScore: params.DividendOpportunityScore,
		DividendOpportunityYield: params.DividendOpportunityYield,
		DividendConsistencyScore: params.DividendConsistencyScore,
	}
}

func (a *tagSettingsAdapter) GetAdjustedDangerThresholds() universe.DangerThresholds {
	params := a.service.GetAdjustedDangerThresholds()
	return universe.DangerThresholds{
		UnsustainableGainsReturn: params.UnsustainableGainsReturn,
		ValuationStretchEMA:      params.ValuationStretchEMA,
		UnderperformingDays:      params.UnderperformingDays,
		StagnantReturnThreshold:  params.StagnantReturnThreshold,
		StagnantDaysThreshold:    params.StagnantDaysThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedPortfolioRiskThresholds() universe.PortfolioRiskThresholds {
	params := a.service.GetAdjustedPortfolioRiskThresholds()
	return universe.PortfolioRiskThresholds{
		OverweightDeviation:        params.OverweightDeviation,
		OverweightAbsolute:         params.OverweightAbsolute,
		ConcentrationRiskThreshold: params.ConcentrationRiskThreshold,
		NeedsRebalanceDeviation:    params.NeedsRebalanceDeviation,
	}
}

func (a *tagSettingsAdapter) GetAdjustedRiskProfileThresholds() universe.RiskProfileThresholds {
	params := a.service.GetAdjustedRiskProfileThresholds()
	return universe.RiskProfileThresholds{
		LowRiskVolatilityMax:        params.LowRiskVolatilityMax,
		LowRiskStabilityMin:         params.LowRiskStabilityMin,
		LowRiskDrawdownMax:          params.LowRiskDrawdownMax,
		MediumRiskVolatilityMin:     params.MediumRiskVolatilityMin,
		MediumRiskVolatilityMax:     params.MediumRiskVolatilityMax,
		MediumRiskStabilityMin:      params.MediumRiskStabilityMin,
		HighRiskVolatilityThreshold: params.HighRiskVolatilityThreshold,
		HighRiskStabilityThreshold:  params.HighRiskStabilityThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedBubbleTrapThresholds() universe.BubbleTrapThresholds {
	params := a.service.GetAdjustedBubbleTrapThresholds()
	return universe.BubbleTrapThresholds{
		BubbleCAGRThreshold:       params.BubbleCAGRThreshold,
		BubbleSharpeThreshold:     params.BubbleSharpeThreshold,
		BubbleVolatilityThreshold: params.BubbleVolatilityThreshold,
		BubbleStabilityThreshold:  params.BubbleStabilityThreshold,
		ValueTrapStability:        params.ValueTrapStability,
		ValueTrapLongTerm:         params.ValueTrapLongTerm,
		ValueTrapMomentum:         params.ValueTrapMomentum,
		ValueTrapVolatility:       params.ValueTrapVolatility,
		QuantumBubbleHighProb:     params.QuantumBubbleHighProb,
		QuantumBubbleWarningProb:  params.QuantumBubbleWarningProb,
		QuantumTrapHighProb:       params.QuantumTrapHighProb,
		QuantumTrapWarningProb:    params.QuantumTrapWarningProb,
		GrowthTagCAGRThreshold:    params.GrowthTagCAGRThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedTotalReturnThresholds() universe.TotalReturnThresholds {
	params := a.service.GetAdjustedTotalReturnThresholds()
	return universe.TotalReturnThresholds{
		ExcellentTotalReturn:     params.ExcellentTotalReturn,
		HighTotalReturn:          params.HighTotalReturn,
		ModerateTotalReturn:      params.ModerateTotalReturn,
		DividendTotalReturnYield: params.DividendTotalReturnYield,
		DividendTotalReturnCAGR:  params.DividendTotalReturnCAGR,
	}
}

func (a *tagSettingsAdapter) GetAdjustedRegimeThresholds() universe.RegimeThresholds {
	params := a.service.GetAdjustedRegimeThresholds()
	return universe.RegimeThresholds{
		BearSafeVolatility:       params.BearSafeVolatility,
		BearSafeStability:        params.BearSafeStability,
		BearSafeDrawdown:         params.BearSafeDrawdown,
		BullGrowthCAGR:           params.BullGrowthCAGR,
		BullGrowthStability:      params.BullGrowthStability,
		RegimeVolatileVolatility: params.RegimeVolatileVolatility,
		SidewaysValueStability:   params.SidewaysValueStability,
	}
}

func (a *tagSettingsAdapter) GetAdjustedQualityGateParams() universe.QualityGateParams {
	params := a.service.GetAdjustedQualityGateParams()
	return universe.QualityGateParams{
		StabilityThreshold:             params.StabilityThreshold,
		LongTermThreshold:              params.LongTermThreshold,
		ExceptionalThreshold:           params.ExceptionalThreshold,
		AbsoluteMinCAGR:                params.AbsoluteMinCAGR,
		ExceptionalExcellenceThreshold: params.ExceptionalExcellenceThreshold,
		QualityValueStabilityMin:       params.QualityValueStabilityMin,
		QualityValueOpportunityMin:     params.QualityValueOpportunityMin,
		QualityValueLongTermMin:        params.QualityValueLongTermMin,
		DividendIncomeStabilityMin:     params.DividendIncomeStabilityMin,
		DividendIncomeScoreMin:         params.DividendIncomeScoreMin,
		DividendIncomeYieldMin:         params.DividendIncomeYieldMin,
		RiskAdjustedLongTermThreshold:  params.RiskAdjustedLongTermThreshold,
		RiskAdjustedSharpeThreshold:    params.RiskAdjustedSharpeThreshold,
		RiskAdjustedSortinoThreshold:   params.RiskAdjustedSortinoThreshold,
		RiskAdjustedVolatilityMax:      params.RiskAdjustedVolatilityMax,
		CompositeStabilityWeight:       params.CompositeStabilityWeight,
		CompositeLongTermWeight:        params.CompositeLongTermWeight,
		CompositeScoreMin:              params.CompositeScoreMin,
		CompositeStabilityFloor:        params.CompositeStabilityFloor,
		GrowthOpportunityCAGRMin:       params.GrowthOpportunityCAGRMin,
		GrowthOpportunityStabilityMin:  params.GrowthOpportunityStabilityMin,
		GrowthOpportunityVolatilityMax: params.GrowthOpportunityVolatilityMax,
		HighScoreThreshold:             params.HighScoreThreshold,
	}
}

func (a *tagSettingsAdapter) GetAdjustedVolatilityParams() universe.VolatilityParams {
	params := a.service.GetAdjustedVolatilityParams()
	return universe.VolatilityParams{
		VolatileThreshold:     params.VolatileThreshold,
		HighThreshold:         params.HighThreshold,
		MaxAcceptable:         params.MaxAcceptable,
		MaxAcceptableDrawdown: params.MaxAcceptableDrawdown,
	}
}

// ==========================================
// Adapters for OpportunityContextBuilder
// ==========================================
// Note: Position, Security, Allocation, and Trade repositories are used directly
// (they implement the service interfaces via Go's structural typing).
// Only adapters with actual logic remain below.

// ocbScoresRepoAdapter adapts database to services.ScoresRepository
// Uses direct database queries like the scheduler adapters
type ocbScoresRepoAdapter struct {
	db *sql.DB // portfolio.db - scores table
}

func (a *ocbScoresRepoAdapter) GetTotalScores(isinList []string) (map[string]float64, error) {
	totalScores := make(map[string]float64)
	if len(isinList) == 0 {
		return totalScores, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, total_score FROM scores WHERE isin IN (%s) AND total_score IS NOT NULL`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var totalScore sql.NullFloat64
		if err := rows.Scan(&isin, &totalScore); err != nil {
			continue
		}
		if totalScore.Valid && totalScore.Float64 > 0 {
			totalScores[isin] = totalScore.Float64
		}
	}
	return totalScores, nil
}

func (a *ocbScoresRepoAdapter) GetCAGRs(isinList []string) (map[string]float64, error) {
	cagrs := make(map[string]float64)
	if len(isinList) == 0 {
		return cagrs, nil
	}

	query := `SELECT isin, cagr_score FROM scores WHERE cagr_score IS NOT NULL AND cagr_score > 0`
	rows, err := a.db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	isinSet := make(map[string]bool)
	for _, isin := range isinList {
		isinSet[isin] = true
	}

	for rows.Next() {
		var isin string
		var cagrScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore); err != nil {
			continue
		}
		if !isinSet[isin] {
			continue
		}
		if cagrScore.Valid && cagrScore.Float64 > 0 {
			// Convert CAGR score (0-100) to CAGR value (e.g., 0.11 for 11%)
			cagrValue := (cagrScore.Float64 / 100.0) * 0.30 // Assuming max 30% CAGR
			if cagrValue > 0 {
				cagrs[isin] = cagrValue
			}
		}
	}
	return cagrs, nil
}

func (a *ocbScoresRepoAdapter) GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error) {
	longTermScores := make(map[string]float64)
	stabilityScores := make(map[string]float64)
	if len(isinList) == 0 {
		return longTermScores, stabilityScores, nil
	}

	query := `SELECT isin, cagr_score, stability_score FROM scores WHERE isin != '' AND isin IS NOT NULL`
	rows, err := a.db.Query(query)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	isinSet := make(map[string]bool)
	for _, isin := range isinList {
		isinSet[isin] = true
	}

	for rows.Next() {
		var isin string
		var cagrScore, stabilityScore sql.NullFloat64
		if err := rows.Scan(&isin, &cagrScore, &stabilityScore); err != nil {
			continue
		}
		if !isinSet[isin] {
			continue
		}
		if cagrScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, cagrScore.Float64))
			longTermScores[isin] = normalized
		}
		if stabilityScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, stabilityScore.Float64))
			stabilityScores[isin] = normalized
		}
	}
	return longTermScores, stabilityScores, nil
}

func (a *ocbScoresRepoAdapter) GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
	opportunityScores := make(map[string]float64)
	momentumScores := make(map[string]float64)
	volatility := make(map[string]float64)
	if len(isinList) == 0 {
		return opportunityScores, momentumScores, volatility, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, opportunity_score, volatility, drawdown_score FROM scores WHERE isin IN (%s)`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, nil, nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var opportunityScore, vol, drawdownScore sql.NullFloat64
		if err := rows.Scan(&isin, &opportunityScore, &vol, &drawdownScore); err != nil {
			continue
		}
		if opportunityScore.Valid {
			normalized := math.Max(0.0, math.Min(1.0, opportunityScore.Float64/100.0))
			opportunityScores[isin] = normalized
		}
		if vol.Valid && vol.Float64 > 0 {
			volatility[isin] = vol.Float64
		}
		if drawdownScore.Valid {
			rawDrawdown := math.Max(-1.0, math.Min(0.0, drawdownScore.Float64/100.0))
			momentum := 1.0 + rawDrawdown
			momentum = (momentum * 2.0) - 1.0
			momentum = math.Max(-1.0, math.Min(1.0, momentum))
			momentumScores[isin] = momentum
		}
	}
	return opportunityScores, momentumScores, volatility, nil
}

func (a *ocbScoresRepoAdapter) GetRiskMetrics(isinList []string) (map[string]float64, map[string]float64, error) {
	sharpe := make(map[string]float64)
	maxDrawdown := make(map[string]float64)
	if len(isinList) == 0 {
		return sharpe, maxDrawdown, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`SELECT isin, sharpe_score, drawdown_score FROM scores WHERE isin IN (%s)`, placeholders)

	args := make([]interface{}, len(isinList))
	for i, isin := range isinList {
		args[i] = isin
	}

	rows, err := a.db.Query(query, args...)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var isin string
		var sharpeScore, drawdownScore sql.NullFloat64
		if err := rows.Scan(&isin, &sharpeScore, &drawdownScore); err != nil {
			continue
		}
		if sharpeScore.Valid {
			// Sharpe score (0-100) to ratio (e.g., 1.5)
			sharpe[isin] = (sharpeScore.Float64 / 100.0) * 3.0 // Max 3.0 Sharpe
		}
		if drawdownScore.Valid {
			// Drawdown score to max drawdown (negative percentage)
			maxDrawdown[isin] = -(100.0 - drawdownScore.Float64) / 100.0
		}
	}
	return sharpe, maxDrawdown, nil
}

// ocbSettingsRepoAdapter adapts settings.Repository to services.SettingsRepository
type ocbSettingsRepoAdapter struct {
	repo       *settings.Repository
	configRepo planningrepo.ConfigRepositoryInterface
}

func (a *ocbSettingsRepoAdapter) GetTargetReturnSettings() (float64, float64, error) {
	// Get from planner config if available
	if a.configRepo != nil {
		config, err := a.configRepo.GetDefaultConfig()
		if err == nil && config != nil {
			return config.OptimizerTargetReturn, 0.80, nil // OptimizerTargetReturn is the target return setting
		}
	}
	return 0.11, 0.80, nil // Defaults: 11% target return, 80% threshold
}

func (a *ocbSettingsRepoAdapter) GetCooloffDays() (int, error) {
	// Read from settings (independent of planner config)
	if a.repo != nil {
		if val, err := a.repo.Get("sell_cooldown_days"); err == nil && val != nil {
			var days float64
			if _, err := fmt.Sscanf(*val, "%f", &days); err == nil && days > 0 {
				return int(days), nil
			}
		}
	}
	return 180, nil // Default
}

func (a *ocbSettingsRepoAdapter) GetVirtualTestCash() (float64, error) {
	if a.repo == nil {
		return 0, nil
	}
	// Check if research mode is enabled
	val, err := a.repo.Get("research_mode")
	if err != nil || val == nil || *val != "true" {
		return 0, nil
	}
	// Get virtual test cash amount
	cashStr, err := a.repo.Get("virtual_test_cash")
	if err != nil || cashStr == nil {
		return 0, nil
	}
	var cash float64
	if _, err := fmt.Sscanf(*cashStr, "%f", &cash); err != nil {
		return 0, nil
	}
	return cash, nil
}

func (a *ocbSettingsRepoAdapter) IsCooloffDisabled() (bool, error) {
	if a.repo == nil {
		return false, nil
	}
	// Check if research mode is enabled - cooloff can only be disabled in research mode
	modeVal, err := a.repo.Get("trading_mode")
	if err != nil || modeVal == nil || *modeVal != "research" {
		return false, nil
	}
	// Check if cooloff checks are disabled
	val, err := a.repo.Get("disable_cooloff_checks")
	if err != nil || val == nil {
		return false, nil
	}
	var disabled float64
	if _, err := fmt.Sscanf(*val, "%f", &disabled); err != nil {
		return false, nil
	}
	return disabled >= 1.0, nil
}

// ocbRegimeRepoAdapter adapts market_regime.RegimeScoreProviderAdapter to services.RegimeRepository
type ocbRegimeRepoAdapter struct {
	adapter *market_regime.RegimeScoreProviderAdapter
}

func (a *ocbRegimeRepoAdapter) GetCurrentRegimeScore() (float64, error) {
	if a.adapter == nil {
		return 0.0, nil
	}
	return a.adapter.GetCurrentRegimeScore()
}

// ocbCashManagerAdapter adapts domain.CashManager to services.CashManager
type ocbCashManagerAdapter struct {
	manager domain.CashManager
}

func (a *ocbCashManagerAdapter) GetAllCashBalances() (map[string]float64, error) {
	return a.manager.GetAllCashBalances()
}

// ocbBrokerClientAdapter adapts domain.BrokerClient to services.BrokerClient (for OCB)
type ocbBrokerClientAdapter struct {
	client domain.BrokerClient
}

func (a *ocbBrokerClientAdapter) IsConnected() bool {
	if a.client == nil {
		return false
	}
	return a.client.IsConnected()
}

func (a *ocbBrokerClientAdapter) GetPendingOrders() ([]domain.BrokerPendingOrder, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	return a.client.GetPendingOrders()
}

// positionValueProviderAdapter adapts PositionRepository to dividends.PositionValueProvider
type positionValueProviderAdapter struct {
	positionRepo *portfolio.PositionRepository
}

func (a *positionValueProviderAdapter) GetMarketValueByISIN(isin string) (float64, error) {
	if a.positionRepo == nil {
		return 0, fmt.Errorf("position repository not available")
	}
	position, err := a.positionRepo.GetByISIN(isin)
	if err != nil {
		return 0, err
	}
	if position == nil {
		return 0, fmt.Errorf("position not found for ISIN: %s", isin)
	}
	return position.MarketValueEUR, nil
}

// brokerPriceClientAdapter adapts domain.BrokerClient to services.PriceClient for OCB
type brokerPriceClientAdapter struct {
	client domain.BrokerClient
}

func (a *brokerPriceClientAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	if a.client == nil {
		return nil, fmt.Errorf("broker client not available")
	}
	// Extract symbols from map
	symbols := make([]string, 0, len(symbolMap))
	for symbol := range symbolMap {
		symbols = append(symbols, symbol)
	}

	// Get quotes from broker
	quotes, err := a.client.GetQuotes(symbols)
	if err != nil {
		return nil, fmt.Errorf("failed to get broker quotes: %w", err)
	}

	// Convert to price map
	prices := make(map[string]*float64)
	for symbol, quote := range quotes {
		if quote != nil && quote.Price > 0 {
			price := quote.Price
			prices[symbol] = &price
		}
	}

	return prices, nil
}

// ============================================================================
// CONFIG REPOSITORY WITH SETTINGS OVERRIDE
// ============================================================================

// plannerConfigWithSettingsOverride wraps a ConfigRepository and overrides
// cooloff period values (min_hold_days, sell_cooldown_days) with values from
// the settings table. This decouples these user-configurable values from
// the planner configuration database table.
type plannerConfigWithSettingsOverride struct {
	repo     *planningrepo.ConfigRepository
	settings *settings.Repository
}

// NewPlannerConfigWithSettingsOverride creates a new config repository wrapper
// that applies settings overrides for cooloff periods.
func NewPlannerConfigWithSettingsOverride(
	repo *planningrepo.ConfigRepository,
	settingsRepo *settings.Repository,
) planningrepo.ConfigRepositoryInterface {
	return &plannerConfigWithSettingsOverride{
		repo:     repo,
		settings: settingsRepo,
	}
}

// GetDefaultConfig retrieves the planner configuration and overrides
// min_hold_days and sell_cooldown_days with values from the settings table.
func (w *plannerConfigWithSettingsOverride) GetDefaultConfig() (*planningdomain.PlannerConfiguration, error) {
	cfg, err := w.repo.GetDefaultConfig()
	if err != nil {
		return nil, err
	}

	// Override cooloff values from settings (these are independent of temperament)
	if w.settings != nil {
		if val, err := w.settings.Get("min_hold_days"); err == nil && val != nil {
			var days float64
			if _, err := fmt.Sscanf(*val, "%f", &days); err == nil && days >= 0 {
				cfg.MinHoldDays = int(days)
			}
		}
		if val, err := w.settings.Get("sell_cooldown_days"); err == nil && val != nil {
			var days float64
			if _, err := fmt.Sscanf(*val, "%f", &days); err == nil && days >= 0 {
				cfg.SellCooldownDays = int(days)
			}
		}
	}

	return cfg, nil
}

// GetConfig delegates to the underlying repository (single config, so ignores ID).
func (w *plannerConfigWithSettingsOverride) GetConfig(id int64) (*planningdomain.PlannerConfiguration, error) {
	return w.GetDefaultConfig() // Apply same overrides
}

// GetConfigByName delegates to the underlying repository (single config, ignores name).
func (w *plannerConfigWithSettingsOverride) GetConfigByName(name string) (*planningdomain.PlannerConfiguration, error) {
	return w.GetDefaultConfig() // Apply same overrides
}

// UpdateConfig delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) UpdateConfig(id int64, cfg *planningdomain.PlannerConfiguration, changedBy, changeNote string) error {
	return w.repo.UpdateConfig(id, cfg, changedBy, changeNote)
}

// CreateConfig delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) CreateConfig(cfg *planningdomain.PlannerConfiguration, isDefault bool) (int64, error) {
	return w.repo.CreateConfig(cfg, isDefault)
}

// ListConfigs delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) ListConfigs() ([]planningrepo.ConfigRecord, error) {
	return w.repo.ListConfigs()
}

// DeleteConfig delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) DeleteConfig(id int64) error {
	return w.repo.DeleteConfig(id)
}

// SetDefaultConfig delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) SetDefaultConfig(id int64) error {
	return w.repo.SetDefaultConfig(id)
}

// GetConfigHistory delegates to the underlying repository.
func (w *plannerConfigWithSettingsOverride) GetConfigHistory(configID int64, limit int) ([]planningrepo.ConfigHistoryRecord, error) {
	return w.repo.GetConfigHistory(configID, limit)
}
