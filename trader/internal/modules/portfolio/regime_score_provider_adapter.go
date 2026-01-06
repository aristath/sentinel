package portfolio

// RegimeScoreProviderAdapter adapts RegimePersistence to consumers that expect a float64 regime score.
type RegimeScoreProviderAdapter struct {
	persistence *RegimePersistence
}

func NewRegimeScoreProviderAdapter(persistence *RegimePersistence) *RegimeScoreProviderAdapter {
	return &RegimeScoreProviderAdapter{persistence: persistence}
}

func (a *RegimeScoreProviderAdapter) GetCurrentRegimeScore() (float64, error) {
	score, err := a.persistence.GetCurrentRegimeScore()
	return float64(score), err
}
