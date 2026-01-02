package evaluation

// SimulateSequence simulates executing a sequence and returns the resulting portfolio state.
//
// This function applies each action in the sequence to the portfolio,
// updating positions and cash. It supports price adjustments for
// stochastic evaluation scenarios.
//
// Args:
//   - sequence: List of actions to execute in order
//   - portfolioContext: Starting portfolio state
//   - availableCash: Starting cash in EUR
//   - securities: Available securities for metadata lookup
//   - priceAdjustments: Optional map of symbol -> price multiplier
//     (e.g., 1.05 for +5% price increase)
//
// Returns:
//   - Final portfolio context
//   - Final cash in EUR
func SimulateSequence(
	sequence []ActionCandidate,
	portfolioContext PortfolioContext,
	availableCash float64,
	securities []Security,
	priceAdjustments map[string]float64,
) (PortfolioContext, float64) {
	// Build securities lookup map
	securitiesBySymbol := make(map[string]Security)
	for _, s := range securities {
		securitiesBySymbol[s.Symbol] = s
	}

	currentContext := portfolioContext
	currentCash := availableCash

	for _, action := range sequence {
		security, exists := securitiesBySymbol[action.Symbol]
		var country, industry *string
		if exists {
			country = security.Country
			industry = security.Industry
		}

		// Apply price adjustment if provided (for stochastic scenarios)
		adjustedPrice := action.Price
		adjustedValueEUR := action.ValueEUR
		if priceAdjustments != nil {
			if multiplier, hasPriceAdj := priceAdjustments[action.Symbol]; hasPriceAdj {
				adjustedPrice = action.Price * multiplier
				// Recalculate value with adjusted price (maintain same quantity)
				adjustedValueEUR = float64(action.Quantity) * adjustedPrice
				// Note: Currency conversion would happen here if needed
			}
		}

		// Memory optimization: Copy-on-write semantics for portfolio state maps.
		// Positions are always copied (both BUY and SELL modify them).
		// Geography/industry are references until modified (BUY only), reducing allocations.
		// For 5-action sequence: 15 map copies → 8 copies (~50% reduction).
		newPositions := copyMap(currentContext.Positions)
		// Start with references - will copy only if BUY action modifies them
		newGeographies := currentContext.SecurityCountries
		newIndustries := currentContext.SecurityIndustries
		geographiesCopied := false
		industriesCopied := false

		if action.Side.IsSell() {
			// Reduce position (cash is PART of portfolio, so total doesn't change)
			// Use adjusted value if price adjustments provided
			sellValue := action.ValueEUR
			if priceAdjustments != nil {
				if _, hasPriceAdj := priceAdjustments[action.Symbol]; hasPriceAdj {
					sellValue = adjustedValueEUR
				}
			}

			currentValue := newPositions[action.Symbol]
			newValue := max(0, currentValue-sellValue)
			if newValue <= 0 {
				delete(newPositions, action.Symbol)
			} else {
				newPositions[action.Symbol] = newValue
			}
			currentCash += sellValue
			// Total portfolio value stays the same - we just converted security to cash
		} else { // BUY
			// Use adjusted value if price adjustments provided
			buyValue := action.ValueEUR
			if priceAdjustments != nil {
				if _, hasPriceAdj := priceAdjustments[action.Symbol]; hasPriceAdj {
					buyValue = adjustedValueEUR
				}
			}

			if buyValue > currentCash {
				continue // Skip if can't afford
			}

			newPositions[action.Symbol] = newPositions[action.Symbol] + buyValue

			// Copy-on-write: Create copies only for maps we're about to modify.
			// This avoids unnecessary copies when only one type of metadata exists.
			if country != nil {
				if !geographiesCopied {
					if newGeographies == nil {
						newGeographies = make(map[string]string, 1)
					} else {
						newGeographies = copyStringMap(newGeographies)
					}
					geographiesCopied = true
				}
				newGeographies[action.Symbol] = *country
			}
			if industry != nil {
				if !industriesCopied {
					if newIndustries == nil {
						newIndustries = make(map[string]string, 1)
					} else {
						newIndustries = copyStringMap(newIndustries)
					}
					industriesCopied = true
				}
				newIndustries[action.Symbol] = *industry
			}

			currentCash -= buyValue
			// Total portfolio value stays the same - we just converted cash to security
		}

		// Create new context with updated positions
		currentContext = PortfolioContext{
			CountryWeights:     currentContext.CountryWeights,
			IndustryWeights:    currentContext.IndustryWeights,
			Positions:          newPositions,
			TotalValue:         currentContext.TotalValue,
			SecurityCountries:  newGeographies,
			SecurityIndustries: newIndustries,
			SecurityScores:     currentContext.SecurityScores,
			SecurityDividends:  currentContext.SecurityDividends,
			CountryToGroup:     currentContext.CountryToGroup,
			IndustryToGroup:    currentContext.IndustryToGroup,
			PositionAvgPrices:  currentContext.PositionAvgPrices,
			CurrentPrices:      currentContext.CurrentPrices,
		}
	}

	return currentContext, currentCash
}

// SimulateSequenceWithContext simulates sequence using EvaluationContext.
//
// Convenience wrapper around SimulateSequence that extracts parameters
// from the evaluation context.
func SimulateSequenceWithContext(
	sequence []ActionCandidate,
	context EvaluationContext,
) (PortfolioContext, float64) {
	return SimulateSequence(
		sequence,
		context.PortfolioContext,
		context.AvailableCashEUR,
		context.Securities,
		context.PriceAdjustments,
	)
}

// CheckSequenceFeasibility performs a quick check if sequence is feasible without full simulation.
//
// Checks if we have enough cash to execute all buys in the sequence.
// This is a fast pre-filter before expensive simulation.
func CheckSequenceFeasibility(
	sequence []ActionCandidate,
	availableCash float64,
	portfolioContext PortfolioContext,
) bool {
	cash := availableCash

	// Check in sequence order (sells first, then buys)
	for _, action := range sequence {
		if action.Side.IsSell() {
			// Sells add cash
			cash += action.ValueEUR
		} else { // BUY
			// Buys consume cash
			if action.ValueEUR > cash {
				return false // Not enough cash for this buy
			}
			cash -= action.ValueEUR
		}
	}

	return true
}

// CashFlowSummary represents the cash flow summary for a sequence
type CashFlowSummary struct {
	CashGenerated float64 // Total from sells
	CashRequired  float64 // Total for buys
	NetCashFlow   float64 // Difference (positive = net inflow)
}

// CalculateSequenceCashFlow calculates cash flow summary for a sequence.
func CalculateSequenceCashFlow(sequence []ActionCandidate) CashFlowSummary {
	var cashGenerated float64
	var cashRequired float64

	for _, action := range sequence {
		if action.Side.IsSell() {
			cashGenerated += action.ValueEUR
		} else { // BUY
			cashRequired += action.ValueEUR
		}
	}

	return CashFlowSummary{
		CashGenerated: cashGenerated,
		CashRequired:  cashRequired,
		NetCashFlow:   cashGenerated - cashRequired,
	}
}

// Helper functions

func copyMap(m map[string]float64) map[string]float64 {
	if m == nil {
		return make(map[string]float64)
	}
	result := make(map[string]float64, len(m))
	for k, v := range m {
		result[k] = v
	}
	return result
}

func copyStringMap(m map[string]string) map[string]string {
	if m == nil {
		return make(map[string]string)
	}
	result := make(map[string]string, len(m))
	for k, v := range m {
		result[k] = v
	}
	return result
}

func max(a, b float64) float64 {
	if a > b {
		return a
	}
	return b
}
