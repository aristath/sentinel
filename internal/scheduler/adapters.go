package scheduler

import (
	"database/sql"
	"fmt"
	"math"
	"strings"

	"github.com/aristath/sentinel/internal/modules/allocation"
	"github.com/aristath/sentinel/internal/modules/dividends"
	"github.com/aristath/sentinel/internal/modules/optimization"
	"github.com/aristath/sentinel/internal/modules/planning"
	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	planningplanner "github.com/aristath/sentinel/internal/modules/planning/planner"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/aristath/sentinel/internal/modules/planning/repository"
	"github.com/aristath/sentinel/internal/modules/portfolio"
	"github.com/aristath/sentinel/internal/modules/settings"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

// PositionRepositoryAdapter adapts *portfolio.PositionRepository to PositionRepositoryInterface
type PositionRepositoryAdapter struct {
	repo *portfolio.PositionRepository
}

func NewPositionRepositoryAdapter(repo *portfolio.PositionRepository) *PositionRepositoryAdapter {
	return &PositionRepositoryAdapter{repo: repo}
}

func (a *PositionRepositoryAdapter) GetAll() ([]interface{}, error) {
	positions, err := a.repo.GetAll()
	if err != nil {
		return nil, err
	}
	result := make([]interface{}, len(positions))
	for i := range positions {
		result[i] = positions[i]
	}
	return result, nil
}

// SecurityRepositoryAdapter adapts *universe.SecurityRepository to SecurityRepositoryInterface
type SecurityRepositoryAdapter struct {
	repo *universe.SecurityRepository
}

func NewSecurityRepositoryAdapter(repo *universe.SecurityRepository) *SecurityRepositoryAdapter {
	return &SecurityRepositoryAdapter{repo: repo}
}

func (a *SecurityRepositoryAdapter) GetAllActive() ([]interface{}, error) {
	securities, err := a.repo.GetAllActive()
	if err != nil {
		return nil, err
	}
	result := make([]interface{}, len(securities))
	for i := range securities {
		result[i] = securities[i]
	}
	return result, nil
}

// AllocationRepositoryAdapter adapts *allocation.Repository to AllocationRepositoryInterface
type AllocationRepositoryAdapter struct {
	repo *allocation.Repository
}

func NewAllocationRepositoryAdapter(repo *allocation.Repository) *AllocationRepositoryAdapter {
	return &AllocationRepositoryAdapter{repo: repo}
}

func (a *AllocationRepositoryAdapter) GetAll() (map[string]float64, error) {
	return a.repo.GetAll()
}

// PriceClientAdapter adapts broker client to PriceClientInterface
// Uses broker API for batch price quotes
type PriceClientAdapter struct {
	brokerClient BrokerClientForPrices
}

// BrokerClientForPrices defines the interface for broker price operations
type BrokerClientForPrices interface {
	GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error)
}

func NewPriceClientAdapter(client BrokerClientForPrices) *PriceClientAdapter {
	return &PriceClientAdapter{brokerClient: client}
}

func (a *PriceClientAdapter) GetBatchQuotes(symbolMap map[string]*string) (map[string]*float64, error) {
	return a.brokerClient.GetBatchQuotes(symbolMap)
}

// CurrentPriceProviderAdapter adapts broker client to CurrentPriceProviderInterface
// Used by dividend recommendation jobs to get current prices
type CurrentPriceProviderAdapter struct {
	brokerClient BrokerClientForCurrentPrice
}

// BrokerClientForCurrentPrice defines the interface for getting single current prices
type BrokerClientForCurrentPrice interface {
	GetCurrentPrice(symbol string) (*float64, error)
}

func NewCurrentPriceProviderAdapter(client BrokerClientForCurrentPrice) *CurrentPriceProviderAdapter {
	return &CurrentPriceProviderAdapter{brokerClient: client}
}

func (a *CurrentPriceProviderAdapter) GetCurrentPrice(symbol string) (*float64, error) {
	return a.brokerClient.GetCurrentPrice(symbol)
}

// OptimizerServiceAdapter adapts *optimization.OptimizerService to OptimizerServiceInterface
type OptimizerServiceAdapter struct {
	service *optimization.OptimizerService
}

func NewOptimizerServiceAdapter(service *optimization.OptimizerService) *OptimizerServiceAdapter {
	return &OptimizerServiceAdapter{service: service}
}

func (a *OptimizerServiceAdapter) Optimize(state interface{}, settings interface{}) (interface{}, error) {
	portfolioState, ok := state.(optimization.PortfolioState)
	if !ok {
		return nil, fmt.Errorf("invalid state type")
	}
	optimizerSettings, ok := settings.(optimization.Settings)
	if !ok {
		return nil, fmt.Errorf("invalid settings type")
	}
	return a.service.Optimize(portfolioState, optimizerSettings)
}

// PriceConversionServiceAdapter adapts PriceConversionService to PriceConversionServiceInterface
type PriceConversionServiceAdapter struct {
	service *services.PriceConversionService
}

func NewPriceConversionServiceAdapter(service *services.PriceConversionService) *PriceConversionServiceAdapter {
	return &PriceConversionServiceAdapter{service: service}
}

func (a *PriceConversionServiceAdapter) ConvertPricesToEUR(prices map[string]float64, securities []universe.Security) map[string]float64 {
	return a.service.ConvertPricesToEUR(prices, securities)
}

// ScoresRepositoryAdapter adapts database connection to ScoresRepositoryInterface
type ScoresRepositoryAdapter struct {
	db  *sql.DB
	log zerolog.Logger
}

func NewScoresRepositoryAdapter(db *sql.DB, log zerolog.Logger) *ScoresRepositoryAdapter {
	return &ScoresRepositoryAdapter{db: db, log: log}
}

func (a *ScoresRepositoryAdapter) GetCAGRs(isinList []string) (map[string]float64, error) {
	cagrs := make(map[string]float64)
	if len(isinList) == 0 {
		return cagrs, nil
	}

	query := `
		SELECT isin, cagr_score
		FROM scores
		WHERE cagr_score IS NOT NULL AND cagr_score > 0
	`
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
			cagrValue := convertCAGRScoreToCAGRAdapter(cagrScore.Float64)
			if cagrValue > 0 {
				cagrs[isin] = cagrValue
			}
		}
	}
	return cagrs, nil
}

func (a *ScoresRepositoryAdapter) GetQualityScores(isinList []string) (map[string]float64, map[string]float64, error) {
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

func (a *ScoresRepositoryAdapter) GetValueTrapData(isinList []string) (map[string]float64, map[string]float64, map[string]float64, error) {
	opportunityScores := make(map[string]float64)
	momentumScores := make(map[string]float64)
	volatility := make(map[string]float64)
	if len(isinList) == 0 {
		return opportunityScores, momentumScores, volatility, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`
		SELECT isin, opportunity_score, volatility, drawdown_score
		FROM scores
		WHERE isin IN (%s)
	`, placeholders)

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
			normalized := math.Max(0.0, math.Min(1.0, opportunityScore.Float64))
			opportunityScores[isin] = normalized
		}
		if vol.Valid && vol.Float64 > 0 {
			volatility[isin] = vol.Float64
		}
		if drawdownScore.Valid {
			rawDrawdown := math.Max(-1.0, math.Min(0.0, drawdownScore.Float64))
			momentum := 1.0 + rawDrawdown
			momentum = (momentum * 2.0) - 1.0
			momentum = math.Max(-1.0, math.Min(1.0, momentum))
			momentumScores[isin] = momentum
		}
	}
	return opportunityScores, momentumScores, volatility, nil
}

func (a *ScoresRepositoryAdapter) GetTotalScores(isinList []string) (map[string]float64, error) {
	totalScores := make(map[string]float64)
	if len(isinList) == 0 {
		return totalScores, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`
		SELECT isin, total_score
		FROM scores
		WHERE isin IN (%s) AND total_score IS NOT NULL
	`, placeholders)

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

// GetRiskMetrics retrieves Sharpe ratio and max drawdown from the scores database
func (a *ScoresRepositoryAdapter) GetRiskMetrics(isinList []string) (map[string]float64, map[string]float64, error) {
	sharpe := make(map[string]float64)
	maxDrawdown := make(map[string]float64)
	if len(isinList) == 0 {
		return sharpe, maxDrawdown, nil
	}

	placeholders := strings.Repeat("?,", len(isinList))
	placeholders = placeholders[:len(placeholders)-1]
	query := fmt.Sprintf(`
		SELECT isin, sharpe_score, drawdown_score
		FROM scores
		WHERE isin IN (%s)
	`, placeholders)

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
			sharpe[isin] = sharpeScore.Float64
		}
		if drawdownScore.Valid {
			// drawdown_score is stored as negative percentage (e.g., -0.25 for 25% drawdown)
			maxDrawdown[isin] = drawdownScore.Float64
		}
	}
	return sharpe, maxDrawdown, nil
}

// convertCAGRScoreToCAGRAdapter converts normalized cagr_score to CAGR percentage
func convertCAGRScoreToCAGRAdapter(cagrScore float64) float64 {
	if cagrScore <= 0 {
		return 0.0
	}
	if cagrScore >= 0.8 {
		return 0.11 + (cagrScore-0.8)*(0.20-0.11)/(1.0-0.8)
	} else if cagrScore >= 0.15 {
		return 0.0 + (cagrScore-0.15)*(0.11-0.0)/(0.8-0.15)
	}
	return 0.0
}

// SettingsRepositoryAdapter adapts database connection to SettingsRepositoryInterface
type SettingsRepositoryAdapter struct {
	db  *sql.DB
	log zerolog.Logger
}

func NewSettingsRepositoryAdapter(db *sql.DB, log zerolog.Logger) *SettingsRepositoryAdapter {
	return &SettingsRepositoryAdapter{db: db, log: log}
}

func (a *SettingsRepositoryAdapter) GetTargetReturnSettings() (float64, float64, error) {
	targetReturn := 0.11
	thresholdPct := 0.80

	var targetReturnStr string
	err := a.db.QueryRow("SELECT value FROM settings WHERE key = 'target_annual_return'").Scan(&targetReturnStr)
	if err == nil {
		if val, err := parseFloatAdapter(targetReturnStr); err == nil {
			targetReturn = val
		} else if val, ok := settings.SettingDefaults["target_annual_return"]; ok {
			if fval, ok := val.(float64); ok {
				targetReturn = fval
			}
		}
	} else if val, ok := settings.SettingDefaults["target_annual_return"]; ok {
		if fval, ok := val.(float64); ok {
			targetReturn = fval
		}
	}

	var thresholdStr string
	err = a.db.QueryRow("SELECT value FROM settings WHERE key = 'target_return_threshold_pct'").Scan(&thresholdStr)
	if err == nil {
		if val, err := parseFloatAdapter(thresholdStr); err == nil {
			thresholdPct = val
		} else if val, ok := settings.SettingDefaults["target_return_threshold_pct"]; ok {
			if fval, ok := val.(float64); ok {
				thresholdPct = fval
			}
		}
	} else if val, ok := settings.SettingDefaults["target_return_threshold_pct"]; ok {
		if fval, ok := val.(float64); ok {
			thresholdPct = fval
		}
	}

	return targetReturn, thresholdPct, nil
}

func (a *SettingsRepositoryAdapter) GetVirtualTestCash() (float64, error) {
	var tradingMode string
	err := a.db.QueryRow("SELECT value FROM settings WHERE key = 'trading_mode'").Scan(&tradingMode)
	if err != nil {
		return 0.0, nil // Not in research mode
	}
	if tradingMode != "research" {
		return 0.0, nil
	}

	var virtualTestCashStr string
	err = a.db.QueryRow("SELECT value FROM settings WHERE key = 'virtual_test_cash'").Scan(&virtualTestCashStr)
	if err != nil {
		return 0.0, nil
	}

	virtualTestCash, err := parseFloatAdapter(virtualTestCashStr)
	if err != nil {
		return 0.0, err
	}
	return virtualTestCash, nil
}

func parseFloatAdapter(s string) (float64, error) {
	var result float64
	_, err := fmt.Sscanf(s, "%f", &result)
	return result, err
}

// RegimeRepositoryAdapter adapts database connection to RegimeRepositoryInterface
type RegimeRepositoryAdapter struct {
	db *sql.DB
}

func NewRegimeRepositoryAdapter(db *sql.DB) *RegimeRepositoryAdapter {
	return &RegimeRepositoryAdapter{db: db}
}

func (a *RegimeRepositoryAdapter) GetCurrentRegimeScore() (float64, error) {
	var regimeScore sql.NullFloat64
	err := a.db.QueryRow(`
		SELECT smoothed_score FROM market_regime_history
		ORDER BY id DESC LIMIT 1
	`).Scan(&regimeScore)
	if err != nil {
		return 0.0, err
	}
	if regimeScore.Valid {
		return regimeScore.Float64, nil
	}
	return 0.0, nil
}

// ConfigRepositoryAdapter adapts *repository.ConfigRepository to ConfigRepositoryInterface
type ConfigRepositoryAdapter struct {
	repo *repository.ConfigRepository
}

func NewConfigRepositoryAdapter(repo *repository.ConfigRepository) *ConfigRepositoryAdapter {
	return &ConfigRepositoryAdapter{repo: repo}
}

func (a *ConfigRepositoryAdapter) GetDefaultConfig() (interface{}, error) {
	return a.repo.GetDefaultConfig()
}

// PlannerConfigRepositoryAdapter adapts *repository.ConfigRepository to PlannerConfigRepositoryInterface
type PlannerConfigRepositoryAdapter struct {
	repo *repository.ConfigRepository
}

func NewPlannerConfigRepositoryAdapter(repo *repository.ConfigRepository) *PlannerConfigRepositoryAdapter {
	return &PlannerConfigRepositoryAdapter{repo: repo}
}

func (a *PlannerConfigRepositoryAdapter) GetDefaultConfig() (*planningdomain.PlannerConfiguration, error) {
	return a.repo.GetDefaultConfig()
}

// PlannerServiceAdapter adapts *planningplanner.Planner to PlannerServiceInterface
type PlannerServiceAdapter struct {
	service *planningplanner.Planner
}

func NewPlannerServiceAdapter(service *planningplanner.Planner) *PlannerServiceAdapter {
	return &PlannerServiceAdapter{service: service}
}

func (a *PlannerServiceAdapter) CreatePlan(ctx interface{}, config interface{}) (interface{}, error) {
	opportunityContext, ok := ctx.(*planningdomain.OpportunityContext)
	if !ok {
		return nil, fmt.Errorf("invalid context type")
	}
	plannerConfig, ok := config.(*planningdomain.PlannerConfiguration)
	if !ok {
		return nil, fmt.Errorf("invalid config type")
	}
	return a.service.CreatePlan(opportunityContext, plannerConfig)
}

func (a *PlannerServiceAdapter) CreatePlanWithRejections(ctx interface{}, config interface{}, progressCallback interface{}) (interface{}, error) {
	opportunityContext, ok := ctx.(*planningdomain.OpportunityContext)
	if !ok {
		return nil, fmt.Errorf("invalid context type")
	}
	plannerConfig, ok := config.(*planningdomain.PlannerConfiguration)
	if !ok {
		return nil, fmt.Errorf("invalid config type")
	}
	// Convert progress callback interface to typed callback
	var cb progress.Callback
	if progressCallback != nil {
		if typedCb, ok := progressCallback.(progress.Callback); ok {
			cb = typedCb
		} else if funcCb, ok := progressCallback.(func(int, int, string)); ok {
			cb = progress.Callback(funcCb)
		}
	}
	return a.service.CreatePlanWithRejections(opportunityContext, plannerConfig, cb)
}

func (a *PlannerServiceAdapter) CreatePlanWithDetailedProgress(ctx interface{}, config interface{}, detailedCallback interface{}) (interface{}, error) {
	opportunityContext, ok := ctx.(*planningdomain.OpportunityContext)
	if !ok {
		return nil, fmt.Errorf("invalid context type")
	}
	plannerConfig, ok := config.(*planningdomain.PlannerConfiguration)
	if !ok {
		return nil, fmt.Errorf("invalid config type")
	}
	// Convert detailed callback interface to typed callback
	var cb progress.DetailedCallback
	if detailedCallback != nil {
		if typedCb, ok := detailedCallback.(progress.DetailedCallback); ok {
			cb = typedCb
		} else if funcCb, ok := detailedCallback.(func(progress.Update)); ok {
			cb = progress.DetailedCallback(funcCb)
		}
	}
	return a.service.CreatePlanWithDetailedProgress(opportunityContext, plannerConfig, cb)
}

// RecommendationRepositoryAdapter adapts *planning.RecommendationRepository to RecommendationRepositoryInterface
type RecommendationRepositoryAdapter struct {
	repo *planning.RecommendationRepository
}

func NewRecommendationRepositoryAdapter(repo *planning.RecommendationRepository) *RecommendationRepositoryAdapter {
	return &RecommendationRepositoryAdapter{repo: repo}
}

func (a *RecommendationRepositoryAdapter) StorePlan(plan *planningdomain.HolisticPlan, portfolioHash string) error {
	if plan == nil {
		return fmt.Errorf("plan cannot be nil")
	}

	if len(plan.Steps) == 0 {
		// If plan has no steps, dismiss all old pending recommendations
		// This ensures old invalid recommendations are cleared when no new plan is generated.
		// We use DismissAllPending() instead of DismissAllByPortfolioHash() because old
		// recommendations may have different portfolio hashes from before portfolio changes.
		_, _ = a.repo.DismissAllPending()
		return nil
	}

	// Dismiss all old pending recommendations before storing new ones
	// This ensures old invalid recommendations (e.g., from before constraint enforcer was added)
	// don't persist when new recommendations are created.
	// We dismiss ALL pending recommendations because old ones may have different portfolio hashes
	// from before portfolio changes, and we want a clean slate for the new plan.
	_, _ = a.repo.DismissAllPending()

	for stepIdx, step := range plan.Steps {
		rec := planning.Recommendation{
			Symbol:                step.Symbol,
			Name:                  step.Name,
			Side:                  step.Side,
			Quantity:              float64(step.Quantity),
			EstimatedPrice:        step.EstimatedPrice,
			EstimatedValue:        step.EstimatedValue,
			Reason:                step.Reason,
			Currency:              step.Currency,
			Priority:              float64(stepIdx),
			CurrentPortfolioScore: plan.CurrentScore,
			NewPortfolioScore:     plan.EndStateScore,
			ScoreChange:           plan.Improvement,
			Status:                "pending",
			PortfolioHash:         portfolioHash,
		}
		if _, err := a.repo.CreateOrUpdate(rec); err != nil {
			return err
		}
	}
	return nil
}

// DividendRepositoryAdapter adapts *dividends.DividendRepository to DividendRepositoryInterface
type DividendRepositoryAdapter struct {
	repo *dividends.DividendRepository
}

func NewDividendRepositoryAdapter(repo *dividends.DividendRepository) *DividendRepositoryAdapter {
	return &DividendRepositoryAdapter{repo: repo}
}

func (a *DividendRepositoryAdapter) GetUnreinvestedDividends(minAmountEUR float64) ([]interface{}, error) {
	dividendRecords, err := a.repo.GetUnreinvestedDividends(minAmountEUR)
	if err != nil {
		return nil, err
	}
	result := make([]interface{}, len(dividendRecords))
	for i := range dividendRecords {
		result[i] = dividendRecords[i]
	}
	return result, nil
}

func (a *DividendRepositoryAdapter) SetPendingBonus(dividendID int, bonus float64) error {
	return a.repo.SetPendingBonus(dividendID, bonus)
}

func (a *DividendRepositoryAdapter) MarkReinvested(dividendID int, quantity int) error {
	return a.repo.MarkReinvested(dividendID, quantity)
}

// SecurityRepositoryForDividendsAdapter adapts *universe.SecurityRepository to SecurityRepositoryForDividendsInterface
type SecurityRepositoryForDividendsAdapter struct {
	repo *universe.SecurityRepository
}

func NewSecurityRepositoryForDividendsAdapter(repo *universe.SecurityRepository) *SecurityRepositoryForDividendsAdapter {
	return &SecurityRepositoryForDividendsAdapter{repo: repo}
}

func (a *SecurityRepositoryForDividendsAdapter) GetBySymbol(symbol string) (*SecurityForDividends, error) {
	security, err := a.repo.GetBySymbol(symbol)
	if err != nil || security == nil {
		return nil, err
	}
	return &SecurityForDividends{
		ISIN:     security.ISIN,
		Symbol:   security.Symbol,
		Name:     security.Name,
		Currency: security.Currency,
		MinLot:   security.MinLot,
	}, nil
}

// NOTE: YahooClientForDividendsAdapter has been removed.
// Dividend yields are now calculated internally using DividendYieldCalculator.

// TradeExecutionServiceAdapter adapts *services.TradeExecutionService to TradeExecutionServiceInterface
type TradeExecutionServiceAdapter struct {
	service *services.TradeExecutionService
}

func NewTradeExecutionServiceAdapter(service *services.TradeExecutionService) *TradeExecutionServiceAdapter {
	return &TradeExecutionServiceAdapter{service: service}
}

func (a *TradeExecutionServiceAdapter) ExecuteTrades(recommendations []TradeRecommendationForDividends) []TradeResultForDividends {
	tradeRecs := make([]services.TradeRecommendation, 0, len(recommendations))
	for _, rec := range recommendations {
		tradeRecs = append(tradeRecs, services.TradeRecommendation{
			Symbol:         rec.Symbol,
			Side:           rec.Side,
			Quantity:       rec.Quantity,
			EstimatedPrice: rec.EstimatedPrice,
			Currency:       rec.Currency,
			Reason:         rec.Reason,
		})
	}

	results := a.service.ExecuteTrades(tradeRecs)
	tradeResults := make([]TradeResultForDividends, 0, len(results))
	for _, result := range results {
		tradeResults = append(tradeResults, TradeResultForDividends{
			Symbol: result.Symbol,
			Status: result.Status,
			Error:  result.Error,
		})
	}
	return tradeResults
}

// TradingServiceAdapter adapts *trading.TradingService to TradingServiceInterface
type TradingServiceAdapter struct {
	service interface {
		SyncFromTradernet() error
	}
}

func NewTradingServiceAdapter(service interface {
	SyncFromTradernet() error
}) *TradingServiceAdapter {
	return &TradingServiceAdapter{service: service}
}

func (a *TradingServiceAdapter) SyncFromTradernet() error {
	return a.service.SyncFromTradernet()
}

// CashFlowsServiceAdapter adapts *cash_flows.CashFlowsService to CashFlowsServiceInterface
type CashFlowsServiceAdapter struct {
	service interface {
		SyncFromTradernet() error
	}
}

func NewCashFlowsServiceAdapter(service interface {
	SyncFromTradernet() error
}) *CashFlowsServiceAdapter {
	return &CashFlowsServiceAdapter{service: service}
}

func (a *CashFlowsServiceAdapter) SyncFromTradernet() error {
	return a.service.SyncFromTradernet()
}

// PortfolioServiceAdapter adapts *portfolio.PortfolioService to PortfolioServiceInterface
type PortfolioServiceAdapter struct {
	service interface {
		SyncFromTradernet() error
	}
}

func NewPortfolioServiceAdapter(service interface {
	SyncFromTradernet() error
}) *PortfolioServiceAdapter {
	return &PortfolioServiceAdapter{service: service}
}

func (a *PortfolioServiceAdapter) SyncFromTradernet() error {
	return a.service.SyncFromTradernet()
}

// UniverseServiceAdapter adapts *universe.UniverseService to UniverseServiceInterface
type UniverseServiceAdapter struct {
	service interface {
		SyncPrices() error
	}
}

func NewUniverseServiceAdapter(service interface {
	SyncPrices() error
}) *UniverseServiceAdapter {
	return &UniverseServiceAdapter{service: service}
}

func (a *UniverseServiceAdapter) SyncPrices() error {
	return a.service.SyncPrices()
}

// DisplayManagerAdapter adapts display manager to DisplayManagerInterface
type DisplayManagerAdapter struct {
	updateTicker func() error
}

func NewDisplayManagerAdapter(updateTicker func() error) *DisplayManagerAdapter {
	return &DisplayManagerAdapter{updateTicker: updateTicker}
}

func (a *DisplayManagerAdapter) UpdateTicker() error {
	return a.updateTicker()
}
