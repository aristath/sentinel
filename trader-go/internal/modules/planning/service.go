package planning

import (
	"github.com/aristath/arduino-trader/internal/modules/opportunities"
	"github.com/aristath/arduino-trader/internal/modules/planning/domain"
	"github.com/aristath/arduino-trader/internal/modules/planning/planner"
	"github.com/aristath/arduino-trader/internal/modules/sequences"
	"github.com/rs/zerolog"
)

type Service struct {
	planner *planner.Planner
	log     zerolog.Logger
}

func NewService(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, log zerolog.Logger) *Service {
	return &Service{
		planner: planner.NewPlanner(opportunitiesService, sequencesService, log),
		log:     log.With().Str("module", "planning").Logger(),
	}
}

func (s *Service) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	return s.planner.CreatePlan(ctx, config)
}
