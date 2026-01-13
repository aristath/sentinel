// Package constraints provides portfolio constraint enforcement for planning.
package constraints

import (
	"fmt"

	planningdomain "github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/rs/zerolog"
)

// SecurityLookupFunc is a function that looks up full security information by symbol or ISIN
type SecurityLookupFunc func(symbol, isin string) (*universe.Security, bool)

// Enforcer validates and adjusts actions based on security constraints.
// Enforces:
// - Per-security allow_buy/allow_sell flags
// - Max sell percentage limits
// - Lot size rounding
// - Cooloff periods (recently sold/bought)
// - Ineligible ISINs (pending orders, etc.)
// - Global allow_buy/allow_sell settings
type Enforcer struct {
	log            zerolog.Logger
	securityLookup SecurityLookupFunc
}

// FilteredAction represents an action that was filtered out with a reason
type FilteredAction struct {
	Action planningdomain.ActionCandidate
	Reason string
}

// NewEnforcer creates a new constraint enforcer
func NewEnforcer(log zerolog.Logger, securityLookup SecurityLookupFunc) *Enforcer {
	return &Enforcer{
		log:            log.With().Str("component", "constraint_enforcer").Logger(),
		securityLookup: securityLookup,
	}
}

// EnforceConstraints validates and adjusts actions based on security constraints
// Returns validated/adjusted actions and list of filtered actions with reasons
func (e *Enforcer) EnforceConstraints(
	actions []planningdomain.ActionCandidate,
	ctx *planningdomain.OpportunityContext,
	config *planningdomain.PlannerConfiguration,
) ([]planningdomain.ActionCandidate, []FilteredAction) {
	var validated []planningdomain.ActionCandidate
	var filtered []FilteredAction

	for _, action := range actions {
		valid, adjusted, reason := e.validateAndAdjustAction(action, ctx, config)
		if valid {
			validated = append(validated, adjusted)
		} else {
			filtered = append(filtered, FilteredAction{
				Action: action,
				Reason: reason,
			})
			e.log.Debug().
				Str("symbol", action.Symbol).
				Str("side", action.Side).
				Str("reason", reason).
				Msg("Action filtered by constraints")
		}
	}

	return validated, filtered
}

// validateAndAdjustAction checks constraints and adjusts quantity
// Returns: (valid, adjustedAction, reason)
func (e *Enforcer) validateAndAdjustAction(
	action planningdomain.ActionCandidate,
	ctx *planningdomain.OpportunityContext,
	config *planningdomain.PlannerConfiguration,
) (bool, planningdomain.ActionCandidate, string) {
	// Get ISIN from action (now always present)
	isin := action.ISIN
	if isin == "" {
		return false, action, fmt.Sprintf("action missing ISIN for symbol: %s", action.Symbol)
	}

	// ==========================================================================
	// GLOBAL CONSTRAINTS (from context)
	// ==========================================================================

	// Check global allow_sell/allow_buy flags
	if action.Side == "SELL" && !ctx.AllowSell {
		return false, action, "global allow_sell=false"
	}
	if action.Side == "BUY" && !ctx.AllowBuy {
		return false, action, "global allow_buy=false"
	}

	// ==========================================================================
	// COOLOFF PERIODS (recently traded)
	// ==========================================================================

	// Check if ISIN was recently sold (can't sell again during cooloff)
	if action.Side == "SELL" && ctx.RecentlySoldISINs[isin] {
		return false, action, "cooloff: recently sold"
	}

	// Check if ISIN was recently bought (can't buy again during cooloff)
	if action.Side == "BUY" && ctx.RecentlyBoughtISINs[isin] {
		return false, action, "cooloff: recently bought"
	}

	// ==========================================================================
	// INELIGIBLE ISINs (pending orders, etc.)
	// ==========================================================================

	// Check if ISIN is marked as ineligible (e.g., has pending order)
	if ctx.IneligibleISINs[isin] {
		return false, action, "ineligible: pending order or other constraint"
	}

	// ==========================================================================
	// SECURITY-SPECIFIC CONSTRAINTS (from security lookup)
	// ==========================================================================

	// Look up security using ISIN (preferred) or symbol (fallback)
	security, found := e.securityLookup(action.Symbol, isin)
	if !found {
		return false, action, fmt.Sprintf("security not found: %s", action.Symbol)
	}

	// Check per-security allow_sell/allow_buy constraints
	if action.Side == "SELL" {
		if !security.AllowSell {
			return false, action, "security allow_sell=false"
		}

		// Validate MaxSellPercentage for SELL actions (safety net)
		if config != nil && config.MaxSellPercentage > 0 && config.MaxSellPercentage < 1.0 {
			// Find the position for this symbol/ISIN
			var position *planningdomain.EnrichedPosition
			for i := range ctx.EnrichedPositions {
				pos := &ctx.EnrichedPositions[i]
				if pos.Symbol == action.Symbol || (isin != "" && pos.ISIN == isin) {
					position = pos
					break
				}
			}

			if position == nil {
				return false, action, "no position found for sell action"
			}

			// Calculate maximum allowed sell quantity
			maxAllowedQuantity := int(position.Quantity * config.MaxSellPercentage)
			if action.Quantity > maxAllowedQuantity {
				// Adjust quantity down to max allowed
				e.log.Debug().
					Str("symbol", action.Symbol).
					Int("requested_quantity", action.Quantity).
					Int("max_allowed_quantity", maxAllowedQuantity).
					Float64("max_sell_percentage", config.MaxSellPercentage).
					Float64("position_quantity", position.Quantity).
					Msg("Adjusting sell quantity to respect max_sell_percentage")

				action.Quantity = maxAllowedQuantity
				// Recalculate value
				if action.Price > 0 {
					action.ValueEUR = float64(action.Quantity) * action.Price
				}
			}
		}
	} else if action.Side == "BUY" {
		if !security.AllowBuy {
			return false, action, "security allow_buy=false"
		}
	} else {
		// Invalid side value - reject the action
		return false, action, fmt.Sprintf("invalid side: %s (must be BUY or SELL)", action.Side)
	}

	// ==========================================================================
	// LOT SIZE ADJUSTMENT
	// ==========================================================================

	// Round quantity to lot size
	adjustedQuantity := e.roundToLotSize(action.Quantity, security.MinLot)

	// If quantity becomes 0 or invalid after rounding, filter out
	if adjustedQuantity <= 0 {
		return false, action, fmt.Sprintf("quantity below minimum lot size (min_lot=%d, requested=%d)", security.MinLot, action.Quantity)
	}

	// If quantity changed, update the action
	if adjustedQuantity != action.Quantity {
		// Validate price before recalculating
		if action.Price <= 0 {
			return false, action, fmt.Sprintf("invalid price: %.2f (must be positive)", action.Price)
		}

		// Recalculate value based on adjusted quantity
		adjustedValue := float64(adjustedQuantity) * action.Price

		adjustedAction := action
		adjustedAction.Quantity = adjustedQuantity
		adjustedAction.ValueEUR = adjustedValue

		e.log.Debug().
			Str("symbol", action.Symbol).
			Int("original_quantity", action.Quantity).
			Int("adjusted_quantity", adjustedQuantity).
			Int("min_lot", security.MinLot).
			Msg("Adjusted quantity to lot size")

		return true, adjustedAction, ""
	}

	// No adjustment needed
	return true, action, ""
}

// roundToLotSize intelligently rounds quantity to lot size
// Strategy:
//  1. Try rounding down: floor(quantity/lotSize) * lotSize
//  2. If result is 0 or invalid, try rounding up: ceil(quantity/lotSize) * lotSize
//  3. Return the valid rounded quantity, or 0 if both fail
func (e *Enforcer) roundToLotSize(quantity int, lotSize int) int {
	if lotSize <= 0 {
		return quantity // No rounding needed
	}

	// Strategy 1: Round down
	roundedDown := (quantity / lotSize) * lotSize

	// If rounding down gives valid result (>= lotSize), use it
	if roundedDown >= lotSize {
		return roundedDown
	}

	// Strategy 2: Round up (only if rounding down failed)
	// Using ceiling: (quantity + lotSize - 1) / lotSize * lotSize
	roundedUp := ((quantity + lotSize - 1) / lotSize) * lotSize

	// Use rounded up if it's valid, otherwise return 0
	if roundedUp >= lotSize {
		return roundedUp
	}

	return 0 // Cannot make valid
}

// IsActionFeasible performs a fast feasibility check without adjusting the action.
// Used for pruning during sequence generation.
// Returns (feasible, reason).
func (e *Enforcer) IsActionFeasible(
	action planningdomain.ActionCandidate,
	ctx *planningdomain.OpportunityContext,
) (bool, string) {
	isin := action.ISIN
	if isin == "" {
		return false, "missing ISIN"
	}

	// Global constraints
	if action.Side == "SELL" && !ctx.AllowSell {
		return false, "global allow_sell=false"
	}
	if action.Side == "BUY" && !ctx.AllowBuy {
		return false, "global allow_buy=false"
	}

	// Cooloff periods
	if action.Side == "SELL" && ctx.RecentlySoldISINs[isin] {
		return false, "cooloff: recently sold"
	}
	if action.Side == "BUY" && ctx.RecentlyBoughtISINs[isin] {
		return false, "cooloff: recently bought"
	}

	// Ineligible ISINs
	if ctx.IneligibleISINs[isin] {
		return false, "ineligible"
	}

	// Security-specific constraints (if lookup available)
	if e.securityLookup != nil {
		security, found := e.securityLookup(action.Symbol, isin)
		if !found {
			return false, "security not found"
		}
		if action.Side == "SELL" && !security.AllowSell {
			return false, "security allow_sell=false"
		}
		if action.Side == "BUY" && !security.AllowBuy {
			return false, "security allow_buy=false"
		}
	}

	return true, ""
}
