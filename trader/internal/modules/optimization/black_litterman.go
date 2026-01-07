package optimization

import (
	"fmt"

	"gonum.org/v1/gonum/mat"

	"github.com/rs/zerolog"
)

// View represents a Black-Litterman view (investor opinion).
type View struct {
	Type       string  // "absolute" or "relative"
	Symbol     string  // For absolute views
	Symbol1    string  // For relative views (outperformer)
	Symbol2    string  // For relative views (underperformer)
	Return     float64 // Expected return (absolute) or outperformance (relative)
	Confidence float64 // Confidence level (0.0 to 1.0)
}

// BlackLittermanOptimizer implements the Black-Litterman model for portfolio optimization.
type BlackLittermanOptimizer struct {
	viewGenerator interface{} // Optional: view generator from scores
	log           zerolog.Logger
}

// NewBlackLittermanOptimizer creates a new Black-Litterman optimizer.
func NewBlackLittermanOptimizer(
	viewGenerator interface{},
	riskBuilder *RiskModelBuilder,
	log zerolog.Logger,
) *BlackLittermanOptimizer {
	if log.GetLevel() == zerolog.Disabled {
		log = zerolog.Nop()
	}
	return &BlackLittermanOptimizer{
		viewGenerator: viewGenerator,
		log:           log.With().Str("component", "black_litterman").Logger(),
	}
}

// CalculateMarketEquilibrium calculates implied equilibrium returns from market weights.
// Formula: Π = λ * Σ * w
// Where: λ = risk aversion, Σ = covariance matrix, w = market weights
func (bl *BlackLittermanOptimizer) CalculateMarketEquilibrium(
	weights map[string]float64,
	covMatrix [][]float64,
	symbols []string,
	riskAversion float64,
) (map[string]float64, error) {
	if len(weights) == 0 || len(covMatrix) == 0 {
		return nil, fmt.Errorf("weights and covariance matrix cannot be empty")
	}

	n := len(symbols)
	if len(covMatrix) != n {
		return nil, fmt.Errorf("covariance matrix size %d does not match symbols %d", len(covMatrix), n)
	}

	// Build weight vector
	w := mat.NewVecDense(n, nil)
	for i, symbol := range symbols {
		if weight, hasWeight := weights[symbol]; hasWeight {
			w.SetVec(i, weight)
		}
	}

	// Build covariance matrix
	sigma := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			sigma.Set(i, j, covMatrix[i][j])
		}
	}

	// Calculate Σ * w
	var sigmaW mat.VecDense
	sigmaW.MulVec(sigma, w)

	// Calculate Π = λ * Σ * w
	equilibriumReturns := make(map[string]float64, n)
	for i, symbol := range symbols {
		pi := riskAversion * sigmaW.AtVec(i)
		equilibriumReturns[symbol] = pi
	}

	return equilibriumReturns, nil
}

// BlendViewsWithEquilibrium blends investor views with market equilibrium using BL formula.
// Formula: E[R] = [(τΣ)^-1 + P'Ω^-1P]^-1 * [(τΣ)^-1Π + P'Ω^-1Q]
func (bl *BlackLittermanOptimizer) BlendViewsWithEquilibrium(
	equilibriumReturns map[string]float64,
	views []View,
	covMatrix [][]float64,
	symbols []string,
	tau float64, // Scaling factor (typically 0.05)
	viewConfidence float64, // Base confidence for views
) (map[string]float64, error) {
	if len(equilibriumReturns) == 0 {
		return nil, fmt.Errorf("equilibrium returns cannot be empty")
	}

	n := len(symbols)
	if len(covMatrix) != n {
		return nil, fmt.Errorf("covariance matrix size mismatch")
	}

	// If no views, return equilibrium returns
	if len(views) == 0 {
		return equilibriumReturns, nil
	}

	// Build matrices for BL formula
	// For simplicity, use diagonal uncertainty matrix Ω
	// In practice, would use more sophisticated uncertainty estimation

	// Build P matrix (view matrix) and Q vector (view returns)
	m := len(views) // Number of views
	P := mat.NewDense(m, n, nil)
	Q := mat.NewVecDense(m, nil)
	omega := mat.NewDense(m, m, nil) // Uncertainty matrix (diagonal)

	for i, view := range views {
		// Set view return
		Q.SetVec(i, view.Return)

		// Set uncertainty (inverse of confidence)
		uncertainty := (1.0 - view.Confidence) * viewConfidence
		if uncertainty < 1e-6 {
			uncertainty = 1e-6 // Prevent division by zero
		}
		omega.Set(i, i, uncertainty)

		// Set P matrix based on view type
		if view.Type == "absolute" {
			// Absolute view: single security
			for j, symbol := range symbols {
				if symbol == view.Symbol {
					P.Set(i, j, 1.0)
					break
				}
			}
		} else if view.Type == "relative" {
			// Relative view: Symbol1 outperforms Symbol2
			for j, symbol := range symbols {
				if symbol == view.Symbol1 {
					P.Set(i, j, 1.0)
				} else if symbol == view.Symbol2 {
					P.Set(i, j, -1.0)
				}
			}
		}
	}

	// Build covariance matrix
	sigma := mat.NewDense(n, n, nil)
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			sigma.Set(i, j, covMatrix[i][j])
		}
	}

	// Build equilibrium returns vector
	pi := mat.NewVecDense(n, nil)
	for i, symbol := range symbols {
		if ret, hasRet := equilibriumReturns[symbol]; hasRet {
			pi.SetVec(i, ret)
		}
	}

	// Calculate τΣ
	tauSigma := mat.NewDense(n, n, nil)
	tauSigma.Scale(tau, sigma)

	// Calculate (τΣ)^-1
	var tauSigmaInv mat.Dense
	if err := tauSigmaInv.Inverse(tauSigma); err != nil {
		return nil, fmt.Errorf("failed to invert τΣ: %w", err)
	}

	// Calculate Ω^-1
	var omegaInv mat.Dense
	if err := omegaInv.Inverse(omega); err != nil {
		return nil, fmt.Errorf("failed to invert Ω: %w", err)
	}

	// Calculate P'Ω^-1P
	var PTrans mat.Dense
	PTrans.CloneFrom(P.T())
	var PTransOmegaInv mat.Dense
	PTransOmegaInv.Mul(&PTrans, &omegaInv)
	var PTransOmegaInvP mat.Dense
	PTransOmegaInvP.Mul(&PTransOmegaInv, P)

	// Calculate [(τΣ)^-1 + P'Ω^-1P]
	var M mat.Dense
	M.Add(&tauSigmaInv, &PTransOmegaInvP)

	// Calculate M^-1
	var MInv mat.Dense
	if err := MInv.Inverse(&M); err != nil {
		return nil, fmt.Errorf("failed to invert M: %w", err)
	}

	// Calculate (τΣ)^-1Π
	var tauSigmaInvPi mat.VecDense
	tauSigmaInvPi.MulVec(&tauSigmaInv, pi)

	// Calculate P'Ω^-1Q
	var PTransOmegaInvQ mat.VecDense
	PTransOmegaInvQ.MulVec(&PTransOmegaInv, Q)

	// Calculate [(τΣ)^-1Π + P'Ω^-1Q]
	var rhs mat.VecDense
	rhs.AddVec(&tauSigmaInvPi, &PTransOmegaInvQ)

	// Calculate final returns: M^-1 * rhs
	var finalReturns mat.VecDense
	finalReturns.MulVec(&MInv, &rhs)

	// Convert to map
	result := make(map[string]float64, n)
	for i, symbol := range symbols {
		result[symbol] = finalReturns.AtVec(i)
	}

	return result, nil
}

// CalculateBLReturns is a convenience method that combines equilibrium calculation and view blending.
func (bl *BlackLittermanOptimizer) CalculateBLReturns(
	marketWeights map[string]float64,
	views []View,
	covMatrix [][]float64,
	symbols []string,
	tau float64,
	riskAversion float64,
) (map[string]float64, error) {
	// Calculate equilibrium returns
	equilibriumReturns, err := bl.CalculateMarketEquilibrium(marketWeights, covMatrix, symbols, riskAversion)
	if err != nil {
		return nil, fmt.Errorf("failed to calculate equilibrium: %w", err)
	}

	// Blend with views
	blReturns, err := bl.BlendViewsWithEquilibrium(equilibriumReturns, views, covMatrix, symbols, tau, 0.5)
	if err != nil {
		return nil, fmt.Errorf("failed to blend views: %w", err)
	}

	return blReturns, nil
}
