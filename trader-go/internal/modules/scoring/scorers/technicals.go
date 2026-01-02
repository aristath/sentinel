package scorers

import (
	"math"

	"github.com/aristath/arduino-trader/internal/modules/scoring"
	"github.com/aristath/arduino-trader/pkg/formulas"
)

// TechnicalsScorer calculates technical indicators score
// Faithful translation from Python: app/modules/scoring/domain/groups/technicals.py
type TechnicalsScorer struct{}

// TechnicalsScore represents the result of technical scoring
type TechnicalsScore struct {
	Components map[string]float64 `json:"components"`
	Score      float64            `json:"score"`
}

// NewTechnicalsScorer creates a new technicals scorer
func NewTechnicalsScorer() *TechnicalsScorer {
	return &TechnicalsScorer{}
}

// Calculate calculates the technicals score from daily prices
// Components:
// - RSI Position (35%): Oversold/overbought
// - Bollinger Position (35%): Position within bands
// - EMA Distance (30%): Distance from 200-day EMA
func (ts *TechnicalsScorer) Calculate(dailyPrices []float64) TechnicalsScore {
	if len(dailyPrices) < 20 {
		// Insufficient data - return neutral score
		return TechnicalsScore{
			Score: 0.5,
			Components: map[string]float64{
				"rsi":       0.5,
				"bollinger": 0.5,
				"ema":       0.5,
			},
		}
	}

	currentPrice := dailyPrices[len(dailyPrices)-1]

	// Calculate RSI score
	rsiValue := formulas.CalculateRSI(dailyPrices, scoring.RSILength)
	rsiScore := scoreRSI(rsiValue)

	// Calculate Bollinger Bands position
	bbPosition := formulas.CalculateBollingerPosition(dailyPrices, scoring.BollingerLength, scoring.BollingerStd)
	bbScore := scoreBollinger(bbPosition)

	// Calculate EMA distance score
	emaValue := formulas.CalculateEMA(dailyPrices, scoring.EMALength)
	emaScore := scoreEMADistance(currentPrice, emaValue)

	// Weighted combination: 35% RSI, 35% Bollinger, 30% EMA
	totalScore := rsiScore*0.35 + bbScore*0.35 + emaScore*0.30
	totalScore = math.Min(1.0, totalScore)

	return TechnicalsScore{
		Score: round3(totalScore),
		Components: map[string]float64{
			"rsi":       round3(rsiScore),
			"bollinger": round3(bbScore),
			"ema":       round3(emaScore),
		},
	}
}

// scoreRSI scores based on RSI value
// Oversold (< 30) = buying opportunity = 1.0
// Overbought (> 70) = poor time to buy = 0.0
func scoreRSI(rsiValue *float64) float64 {
	if rsiValue == nil {
		return 0.5
	}

	rsi := *rsiValue

	if rsi < scoring.RSIOversold { // < 30
		return 1.0
	} else if rsi > scoring.RSIOverbought { // > 70
		return 0.0
	} else {
		// Linear scale between 30-70
		return 1.0 - ((rsi - scoring.RSIOversold) / (scoring.RSIOverbought - scoring.RSIOversold))
	}
}

// scoreBollinger scores based on position within Bollinger Bands
// Near lower band = buying opportunity = higher score
func scoreBollinger(position *formulas.BollingerPosition) float64 {
	if position == nil {
		return 0.5
	}

	// Lower position = better score (inverted)
	return math.Max(0.0, math.Min(1.0, 1.0-position.Position))
}

// scoreEMADistance scores based on distance from 200-day EMA
// Below EMA = HIGHER score (buying opportunity)
func scoreEMADistance(currentPrice float64, emaValue *float64) float64 {
	if emaValue == nil || *emaValue <= 0 {
		return 0.5
	}

	pctFromEMA := (currentPrice - *emaValue) / *emaValue

	if pctFromEMA >= scoring.EMAVeryAbove { // 10%+ above
		return 0.2
	} else if pctFromEMA >= 0 { // 0-10% above
		return 0.5 - (pctFromEMA/scoring.EMAVeryAbove)*0.3
	} else if pctFromEMA >= scoring.EMABelow { // 0-5% below
		return 0.5 + (math.Abs(pctFromEMA)/0.05)*0.2
	} else if pctFromEMA >= scoring.EMAVeryBelow { // 5-10% below
		return 0.7 + ((math.Abs(pctFromEMA)-0.05)/0.05)*0.3
	} else { // 10%+ below
		return 1.0
	}
}

// round3 rounds a float to 3 decimal places
func round3(f float64) float64 {
	return math.Round(f*1000) / 1000
}
