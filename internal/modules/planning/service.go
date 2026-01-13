package planning

import (
	maindomain "github.com/aristath/sentinel/internal/domain"
	"github.com/aristath/sentinel/internal/modules/opportunities"
	"github.com/aristath/sentinel/internal/modules/planning/domain"
	"github.com/aristath/sentinel/internal/modules/planning/evaluation"
	"github.com/aristath/sentinel/internal/modules/planning/planner"
	"github.com/aristath/sentinel/internal/modules/planning/progress"
	"github.com/aristath/sentinel/internal/modules/sequences"
	"github.com/aristath/sentinel/internal/modules/universe"
	"github.com/aristath/sentinel/internal/services"
	"github.com/rs/zerolog"
)

type Service struct {
	planner *planner.Planner
	log     zerolog.Logger
}

func NewService(opportunitiesService *opportunities.Service, sequencesService *sequences.Service, evaluationService *evaluation.Service, securityRepo *universe.SecurityRepository, currencyExchangeService *services.CurrencyExchangeService, brokerClient maindomain.BrokerClient, log zerolog.Logger) *Service {
	return &Service{
		planner: planner.NewPlanner(opportunitiesService, sequencesService, evaluationService, securityRepo, currencyExchangeService, brokerClient, log),
		log:     log.With().Str("module", "planning").Logger(),
	}
}

func (s *Service) CreatePlan(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration) (*domain.HolisticPlan, error) {
	return s.planner.CreatePlan(ctx, config)
}

// CreatePlanWithRejections creates a plan with rejection tracking and optional progress callback.
func (s *Service) CreatePlanWithRejections(ctx *domain.OpportunityContext, config *domain.PlannerConfiguration, progressCallback progress.Callback) (*planner.PlanResult, error) {
	return s.planner.CreatePlanWithRejections(ctx, config, progressCallback)
}
