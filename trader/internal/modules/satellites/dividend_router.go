package satellites

import (
	"fmt"

	"github.com/rs/zerolog"
)

// DividendRoutingResult contains the result of dividend routing
type DividendRoutingResult struct {
	SourceBucket      string  `json:"source_bucket"`
	DestinationBucket string  `json:"destination_bucket"`
	Amount            float64 `json:"amount"`
	Currency          string  `json:"currency"`
	Action            string  `json:"action"` // "kept" | "transferred"
	DividendHandling  string  `json:"dividend_handling"`
}

// DividendRouter routes dividends to appropriate buckets based on settings.
//
// Routes dividends according to satellite configuration:
// - reinvest_same: Keep dividend in satellite's cash balance (for reinvestment)
// - send_to_core: Transfer dividend to core bucket
// - accumulate_cash: Keep in satellite (same as reinvest_same)
//
// Faithful translation from Python: app/modules/satellites/services/dividend_router.py
type DividendRouter struct {
	bucketService  *BucketService
	balanceService *BalanceService
	log            zerolog.Logger
}

// NewDividendRouter creates a new dividend router
func NewDividendRouter(
	bucketService *BucketService,
	balanceService *BalanceService,
	log zerolog.Logger,
) *DividendRouter {
	return &DividendRouter{
		bucketService:  bucketService,
		balanceService: balanceService,
		log:            log,
	}
}

// RouteDividend routes a dividend payment based on satellite settings.
//
// Args:
//
//	bucketID: The bucket that owns the position generating the dividend
//	amount: Dividend amount
//	currency: Currency code (EUR, USD, etc.)
//	symbol: Stock symbol that generated the dividend
//	paymentDate: Dividend payment date
//	description: Optional description
//
// Returns:
//
//	DividendRoutingResult with routing details
func (r *DividendRouter) RouteDividend(
	bucketID string,
	amount float64,
	currency string,
	symbol string,
	paymentDate string,
	description *string,
) (*DividendRoutingResult, error) {
	// Get bucket to determine routing
	bucket, err := r.bucketService.GetBucket(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}

	if bucket == nil {
		r.log.Warn().
			Str("bucket_id", bucketID).
			Msg("Bucket not found, routing dividend to core")

		// Default to core if bucket not found
		desc := fmt.Sprintf("Dividend from %s (orphaned from %s)", symbol, bucketID)
		_, err := r.balanceService.RecordDividend("core", amount, currency, &desc)
		if err != nil {
			return nil, fmt.Errorf("failed to record dividend to core: %w", err)
		}

		return &DividendRoutingResult{
			SourceBucket:      bucketID,
			DestinationBucket: "core",
			Amount:            amount,
			Currency:          currency,
			Action:            "transferred",
			DividendHandling:  "default_to_core",
		}, nil
	}

	// For core bucket, always keep dividends
	if bucketID == "core" {
		desc := fmt.Sprintf("Dividend from %s", symbol)
		if description != nil {
			desc = *description
		}

		_, err := r.balanceService.RecordDividend("core", amount, currency, &desc)
		if err != nil {
			return nil, fmt.Errorf("failed to record dividend to core: %w", err)
		}

		return &DividendRoutingResult{
			SourceBucket:      "core",
			DestinationBucket: "core",
			Amount:            amount,
			Currency:          currency,
			Action:            "kept",
			DividendHandling:  "core_default",
		}, nil
	}

	// For satellites, get settings to determine routing
	settings, err := r.bucketService.GetSettings(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get settings: %w", err)
	}

	dividendHandling := "send_to_core"
	if settings == nil {
		r.log.Warn().
			Str("bucket_id", bucketID).
			Msg("No settings for satellite, defaulting to send_to_core")
	} else {
		dividendHandling = settings.DividendHandling
	}

	// Route based on setting
	if dividendHandling == "send_to_core" {
		// Transfer to core bucket
		desc := fmt.Sprintf("Dividend from %s (routed to core)", symbol)
		_, _, err := r.balanceService.TransferBetweenBuckets(
			bucketID,
			"core",
			amount,
			currency,
			&desc,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to transfer dividend to core: %w", err)
		}

		r.log.Info().
			Str("symbol", symbol).
			Str("bucket_id", bucketID).
			Float64("amount", amount).
			Str("currency", currency).
			Msg("Routed dividend to core")

		return &DividendRoutingResult{
			SourceBucket:      bucketID,
			DestinationBucket: "core",
			Amount:            amount,
			Currency:          currency,
			Action:            "transferred",
			DividendHandling:  dividendHandling,
		}, nil
	}

	// reinvest_same or accumulate_cash - keep in satellite's cash balance
	desc := fmt.Sprintf("Dividend from %s (kept in %s)", symbol, bucketID)
	if description != nil {
		desc = *description
	}

	_, err = r.balanceService.RecordDividend(bucketID, amount, currency, &desc)
	if err != nil {
		return nil, fmt.Errorf("failed to record dividend to %s: %w", bucketID, err)
	}

	r.log.Info().
		Str("symbol", symbol).
		Str("bucket_id", bucketID).
		Float64("amount", amount).
		Str("currency", currency).
		Str("handling", dividendHandling).
		Msg("Kept dividend in satellite")

	return &DividendRoutingResult{
		SourceBucket:      bucketID,
		DestinationBucket: bucketID,
		Amount:            amount,
		Currency:          currency,
		Action:            "kept",
		DividendHandling:  dividendHandling,
	}, nil
}

// GetDividendRoutingSummary gets summary of how dividends will be routed for a bucket.
//
// Args:
//
//	bucketID: Bucket ID
//
// Returns:
//
//	Map with routing configuration and stats
func (r *DividendRouter) GetDividendRoutingSummary(bucketID string) (map[string]interface{}, error) {
	bucket, err := r.bucketService.GetBucket(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get bucket: %w", err)
	}

	if bucket == nil {
		return map[string]interface{}{
			"error": "Bucket not found",
		}, nil
	}

	if bucketID == "core" {
		return map[string]interface{}{
			"bucket_id":         "core",
			"dividend_handling": "core_default",
			"destination":       "core",
			"description":       "Core bucket keeps all dividends",
		}, nil
	}

	settings, err := r.bucketService.GetSettings(bucketID)
	if err != nil {
		return nil, fmt.Errorf("failed to get settings: %w", err)
	}

	if settings == nil {
		return map[string]interface{}{
			"bucket_id":         bucketID,
			"dividend_handling": "send_to_core",
			"destination":       "core",
			"description":       "No settings - defaults to sending to core",
		}, nil
	}

	handling := settings.DividendHandling
	destination := "core"
	if handling != "send_to_core" {
		destination = bucketID
	}

	descriptions := map[string]string{
		"reinvest_same":   fmt.Sprintf("Dividends stay in %s for reinvestment in same satellite", bucketID),
		"send_to_core":    "Dividends transferred to core bucket",
		"accumulate_cash": fmt.Sprintf("Dividends accumulated as cash in %s", bucketID),
	}

	description := descriptions[handling]
	if description == "" {
		description = fmt.Sprintf("Dividends handled as: %s", handling)
	}

	return map[string]interface{}{
		"bucket_id":         bucketID,
		"dividend_handling": handling,
		"destination":       destination,
		"description":       description,
	}, nil
}
