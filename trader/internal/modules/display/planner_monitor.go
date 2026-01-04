package display

import (
	"context"
	"time"

	"github.com/aristath/arduino-trader/internal/modules/planning"
	"github.com/rs/zerolog"
)

// PlannerMonitor monitors pending planner recommendations and updates LED4 accordingly
type PlannerMonitor struct {
	recommendationRepo *planning.RecommendationRepository
	stateManager       *StateManager
	log                zerolog.Logger
	interval           time.Duration
}

// NewPlannerMonitor creates a new planner monitor
func NewPlannerMonitor(recommendationRepo *planning.RecommendationRepository, stateManager *StateManager, log zerolog.Logger) *PlannerMonitor {
	return &PlannerMonitor{
		recommendationRepo: recommendationRepo,
		stateManager:       stateManager,
		log:                log.With().Str("component", "planner_monitor").Logger(),
		interval:           5 * time.Second,
	}
}

// CountPendingBySide queries database for pending BUY and SELL counts
func (pm *PlannerMonitor) CountPendingBySide() (buyCount int, sellCount int, err error) {
	return pm.recommendationRepo.CountPendingBySide()
}

// UpdateLED4ForActions maps pending action types to LED4 behavior
func (pm *PlannerMonitor) UpdateLED4ForActions(hasBuy bool, hasSell bool) {
	if !hasBuy && !hasSell {
		// No pending actions - turn off
		pm.stateManager.SetLED4Color(0, 0, 0)
		pm.log.Debug().Msg("LED4: Off (no pending actions)")
		return
	}

	if hasBuy && hasSell {
		// Both BUY and SELL - alternating blue/orange
		// Blue: RGB(0, 100, 255), Orange: RGB(255, 165, 0)
		pm.stateManager.SetLED4Alternating(0, 100, 255, 255, 165, 0, 1000)
		pm.log.Debug().Msg("LED4: Alternating blue/orange (both BUY and SELL)")
	} else if hasBuy {
		// BUY only - blue blink, coordinated with LED3
		// Get LED3 current state for coordination
		led3State := pm.stateManager.GetLED3BlinkState()
		pm.stateManager.SetLED4Coordinated(0, 100, 255, 1000, led3State)
		pm.log.Debug().Bool("led3_state", led3State).Msg("LED4: Blue blink coordinated with LED3 (BUY only)")
	} else if hasSell {
		// SELL only - orange blink, coordinated with LED3
		// Get LED3 current state for coordination
		led3State := pm.stateManager.GetLED3BlinkState()
		pm.stateManager.SetLED4Coordinated(255, 165, 0, 1000, led3State)
		pm.log.Debug().Bool("led3_state", led3State).Msg("LED4: Orange blink coordinated with LED3 (SELL only)")
	}
}

// MonitorPlannerActions runs the monitoring loop
func (pm *PlannerMonitor) MonitorPlannerActions(ctx context.Context) {
	pm.log.Info().
		Dur("interval", pm.interval).
		Msg("Starting planner action monitor")

	ticker := time.NewTicker(pm.interval)
	defer ticker.Stop()

	// Initial check
	buyCount, sellCount, err := pm.CountPendingBySide()
	if err != nil {
		pm.log.Error().Err(err).Msg("Failed to get initial pending recommendations")
		pm.UpdateLED4ForActions(false, false)
	} else {
		pm.UpdateLED4ForActions(buyCount > 0, sellCount > 0)
	}

	for {
		select {
		case <-ctx.Done():
			pm.log.Info().Msg("Planner monitor stopping")
			pm.stateManager.SetLED4Color(0, 0, 0)
			return
		case <-ticker.C:
			buyCount, sellCount, err := pm.CountPendingBySide()
			if err != nil {
				pm.log.Debug().Err(err).Msg("Failed to count pending recommendations")
				pm.UpdateLED4ForActions(false, false)
				continue
			}

			pm.UpdateLED4ForActions(buyCount > 0, sellCount > 0)
		}
	}
}
