import { Card, Group, Text, Badge, Stack, Paper, ActionIcon } from '@mantine/core';
import { IconRefresh, IconRotateClockwise, IconX, IconPlus } from '@tabler/icons-react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { formatCurrency } from '../../utils/formatters';
import { api } from '../../api/client';
import { PlannerProgressPanel, RejectedSequencesList } from '../planning';

export function NextActionsCard() {
  const {
    recommendations,
    runningJobs,
    lastPlannerRun,
    loading,
    fetchRecommendations,
    triggerPlannerBatch,
  } = useAppStore();
  const { allocation } = usePortfolioStore();
  const { settings } = useSettingsStore();

  // Find planner_batch job in running jobs
  const plannerJob = Object.values(runningJobs).find(j => j.jobType === 'planner_batch');
  const isPlanning = !!plannerJob;

  const handleTriggerPlanner = async () => {
    if (confirm('This will trigger a new planning job to regenerate recommendations. Continue?')) {
      await triggerPlannerBatch();
    }
  };

  const steps = recommendations?.steps || [];
  const hasRecommendations = steps.length > 0;

  return (
    <Card
      className="next-actions"
      p="lg"
      style={{
        border: '1px solid var(--mantine-color-dark-6)',
        backgroundColor: 'var(--mantine-color-dark-7)',
      }}
    >
      <Group className="next-actions__header" justify="space-between" mb="md">
        <div className="next-actions__title-section" style={{ flex: 1 }}>
          <Text className="next-actions__title" size="lg" fw={700} c="blue" tt="uppercase" mb="xs" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Next Actions
          </Text>
          <Text className="next-actions__subtitle" size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Automated portfolio management recommendations
          </Text>
        </div>
        <Group className="next-actions__stats" gap="md" visibleFrom="md">
          <div className="next-actions__stat next-actions__stat--total" style={{ textAlign: 'right' }}>
            <Text className="next-actions__stat-label" size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>Total Value</Text>
            <Text className="next-actions__stat-value" size="sm" fw={600} c="green" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              {formatCurrency(allocation.total_value)}
            </Text>
          </div>
          <div className="next-actions__divider" style={{ width: '1px', height: '32px', backgroundColor: 'var(--mantine-color-dark-6)' }} />
          <div className="next-actions__stat next-actions__stat--cash" style={{ textAlign: 'right' }}>
            <Text className="next-actions__stat-label" size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>Cash</Text>
            <Text className="next-actions__stat-value" size="sm" fw={600} c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              {formatCurrency(allocation.cash_balance)}
            </Text>
          </div>
        </Group>
        <Group className="next-actions__actions" gap="xs">
          <ActionIcon
            className="next-actions__refresh-btn"
            variant="subtle"
            onClick={fetchRecommendations}
            loading={loading.recommendations}
            title="Refresh recommendations"
          >
            <IconRefresh size={18} />
          </ActionIcon>
          <ActionIcon
            className="next-actions__planner-btn"
            variant="subtle"
            onClick={handleTriggerPlanner}
            disabled={isPlanning}
            title="Trigger planning job"
          >
            <IconRotateClockwise size={18} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Planner Progress Panel - shows when running or has last run data */}
      {(isPlanning || lastPlannerRun) && (
        <PlannerProgressPanel
          job={plannerJob}
          lastRun={isPlanning ? null : lastPlannerRun}
        />
      )}

      {/* Empty State */}
      {!loading.recommendations && !hasRecommendations && (
        <Stack className="next-actions__empty" align="center" py="xl">
          <Text className="next-actions__empty-title" size="lg" fw={600} c="dimmed">
            No recommendations pending
          </Text>
          <Text className="next-actions__empty-subtitle" size="sm" c="dimmed">
            {recommendations?.rejected_opportunities && recommendations.rejected_opportunities.length > 0
              ? 'All opportunities were filtered out'
              : recommendations?.pre_filtered_securities && recommendations.pre_filtered_securities.length > 0
              ? 'All securities were pre-filtered - expand details below'
              : 'Portfolio is optimally balanced'}
          </Text>
        </Stack>
      )}

      {/* Recommendations Sequence */}
      {hasRecommendations && (
        <Stack className="next-actions__sequence" gap="md">
          {recommendations.evaluated_count !== undefined && (
            <Text className="next-actions__evaluated-count" size="sm" c="dimmed">
              Scenarios evaluated: {(recommendations.evaluated_count || 0).toLocaleString()}
            </Text>
          )}
          <Group className="next-actions__sequence-header" justify="space-between">
            <Group className="next-actions__sequence-info" gap="md">
              <Text className="next-actions__sequence-title" size="sm" fw={600}>
                Optimal Sequence ({steps.length} step{steps.length > 1 ? 's' : ''})
              </Text>
              {recommendations.total_score_improvement > 0 && (
                <Badge className="next-actions__score-badge next-actions__score-badge--positive" color="green" variant="light">
                  +{recommendations.total_score_improvement.toFixed(1)} score
                </Badge>
              )}
              {recommendations.total_score_improvement < 0 && (
                <Badge className="next-actions__score-badge next-actions__score-badge--negative" color="red" variant="light">
                  {recommendations.total_score_improvement.toFixed(1)} score
                </Badge>
              )}
            </Group>
            <Text className="next-actions__auto-note" size="xs" c="dimmed" fs="italic">
              Trades execute automatically every {Math.round(settings.job_sync_cycle_minutes || 15)} minutes
            </Text>
          </Group>

          <Stack className="next-actions__steps" gap="md">
            {steps.map((step) => (
              <Paper
                className={`next-actions__step next-actions__step--${step.side.toLowerCase()} ${step.is_emergency ? 'next-actions__step--emergency' : ''}`}
                key={`step-${step.step}`}
                p="md"
                style={{
                  border: '1px solid',
                  borderColor: step.is_emergency
                    ? 'var(--mantine-color-yellow-0)'
                    : step.side === 'SELL'
                    ? 'var(--mantine-color-red-0)'
                    : 'var(--mantine-color-green-0)',
                  backgroundColor: 'var(--mantine-color-dark-8)',
                }}
              >
                <Group className="next-actions__step-content" justify="space-between" align="flex-start">
                  <div className="next-actions__step-main" style={{ flex: 1, minWidth: 0 }}>
                    <Group className="next-actions__step-badges" gap="xs" mb="xs" wrap="wrap">
                      <Badge className="next-actions__step-number" size="sm" variant="filled" color="dark" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        Step {step.step}
                      </Badge>
                      {step.is_emergency && (
                        <Badge className="next-actions__emergency-badge" size="sm" color="orange" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          🚨 EMERGENCY
                        </Badge>
                      )}
                      <Badge
                        className="next-actions__side-badge"
                        size="sm"
                        color={step.side === 'SELL' ? 'red' : 'green'}
                        variant="light"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {step.side}
                      </Badge>
                      <Text className="next-actions__step-symbol" size="lg" fw={700} style={{ fontFamily: 'var(--mantine-font-family)' }} c={step.side === 'SELL' ? 'red' : 'green'}>
                        {step.symbol}
                      </Text>
                    </Group>
                    <Text className="next-actions__step-name" size="md" fw={500} mb="xs" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      {step.name}
                    </Text>
                    <Text
                      className="next-actions__step-reason"
                      size="sm"
                      mb="xs"
                      c={step.is_emergency ? 'orange' : 'dimmed'}
                      fw={step.is_emergency ? 600 : 400}
                      style={{ fontFamily: 'var(--mantine-font-family)' }}
                    >
                      {step.reason}
                    </Text>
                    <Group className="next-actions__step-scores" gap="md" wrap="wrap">
                      <Text className="next-actions__score-change" size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        Score: {step.portfolio_score_before.toFixed(1)} → {step.portfolio_score_after.toFixed(1)}
                      </Text>
                      {step.score_change > 0 && (
                        <Badge className="next-actions__score-delta next-actions__score-delta--positive" size="sm" color="green" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          +{step.score_change.toFixed(1)}
                        </Badge>
                      )}
                      {step.score_change < 0 && (
                        <Badge className="next-actions__score-delta next-actions__score-delta--negative" size="sm" color="red" variant="light" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          {step.score_change.toFixed(1)}
                        </Badge>
                      )}
                    </Group>
                  </div>
                  <div className="next-actions__step-values" style={{ textAlign: 'right', flexShrink: 0 }}>
                    <Text
                      className="next-actions__step-amount"
                      size="lg"
                      fw={700}
                      style={{ fontFamily: 'var(--mantine-font-family)' }}
                      c={step.side === 'SELL' ? 'red' : 'green'}
                    >
                      {(step.side === 'SELL' ? '-' : '+')}{formatCurrency(step.estimated_value)}
                    </Text>
                    <Text className="next-actions__step-quantity" size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      {step.quantity} @ {formatCurrency(step.estimated_price)}
                    </Text>
                    <Text className="next-actions__step-cash" size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      Cash: {formatCurrency(step.available_cash_before)} → {formatCurrency(step.available_cash_after)}
                    </Text>
                  </div>
                </Group>
              </Paper>
            ))}
          </Stack>

          {recommendations.final_available_cash && (
            <Text className="next-actions__final-cash" size="sm" c="dimmed" ta="center" mt="md" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              Final cash: <Text span fw={600} c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                {formatCurrency(recommendations.final_available_cash)}
              </Text>
            </Text>
          )}
        </Stack>
      )}

      {/* Rejected Opportunities - Always visible when present */}
      {recommendations?.rejected_opportunities && recommendations.rejected_opportunities.length > 0 && (
        <div className="next-actions__rejected" style={{
          marginTop: hasRecommendations ? '1rem' : '0',
          borderTop: hasRecommendations ? '1px solid var(--mantine-color-dark-6)' : 'none',
          paddingTop: hasRecommendations ? '1rem' : '0'
        }}>
          <Text className="next-actions__rejected-title" size="sm" c="dimmed" fw={500} mb="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
            Rejected Opportunities ({recommendations.rejected_opportunities.length})
          </Text>
          <Stack className="next-actions__rejected-list" gap="xs">
            {recommendations.rejected_opportunities.map((rejected, index) => (
              <Paper
                className="next-actions__rejected-item"
                key={`rejected-${rejected.symbol}-${rejected.side}-${index}`}
                p="sm"
                style={{
                  border: '1px solid var(--mantine-color-dark-6)',
                  backgroundColor: 'var(--mantine-color-dark-8)',
                }}
              >
                <Group className="next-actions__rejected-header" gap="xs" mb="xs" wrap="wrap">
                  <Badge
                    className="next-actions__rejected-side"
                    size="sm"
                    color={rejected.side === 'SELL' ? 'red' : 'green'}
                    variant="light"
                    style={{ fontFamily: 'var(--mantine-font-family)' }}
                  >
                    {rejected.side}
                  </Badge>
                  <Text className="next-actions__rejected-symbol" size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                    {rejected.symbol}
                  </Text>
                  {rejected.name && (
                    <Text className="next-actions__rejected-name" size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                      - {rejected.name}
                    </Text>
                  )}
                </Group>
                {rejected.reasons && rejected.reasons.length > 0 && (
                  <Text className="next-actions__rejected-reasons" size="xs" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)', lineHeight: 1.5 }}>
                    {rejected.reasons.join('; ')}
                  </Text>
                )}
              </Paper>
            ))}
          </Stack>
        </div>
      )}

      {/* Pre-Filtered Securities - Securities excluded before reaching opportunity stage */}
      {recommendations?.pre_filtered_securities && recommendations.pre_filtered_securities.length > 0 && (() => {
        // Group pre-filtered securities by symbol/ISIN
        const groupedBySymbol = recommendations.pre_filtered_securities.reduce((acc, filtered) => {
          const key = filtered.symbol || filtered.isin;
          if (!acc[key]) {
            acc[key] = {
              symbol: filtered.symbol,
              isin: filtered.isin,
              name: filtered.name,
              reasons: [] // Array of { calculator, reasons }
            };
          }
          // Add calculator and its reasons
          acc[key].reasons.push({
            calculator: filtered.calculator,
            reasons: filtered.reasons || []
          });
          return acc;
        }, {});

        const groupedSecurities = Object.values(groupedBySymbol);

        return (
          <div className="next-actions__filtered" style={{
            marginTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1rem' : '0',
            borderTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1px solid var(--mantine-color-dark-6)' : 'none',
            paddingTop: (hasRecommendations || recommendations?.rejected_opportunities?.length > 0) ? '1rem' : '0'
          }}>
            <Text className="next-actions__filtered-title" size="sm" c="dimmed" fw={500} mb="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
              Pre-Filtered Securities ({groupedSecurities.length} securities)
            </Text>
            <Text className="next-actions__filtered-subtitle" size="xs" c="dimmed" mb="sm" style={{ fontFamily: 'var(--mantine-font-family)', fontStyle: 'italic' }}>
              Securities excluded before reaching the opportunity identification stage
            </Text>
            <Stack className="next-actions__filtered-list" gap="xs">
              {groupedSecurities.map((security) => (
                <Paper
                  className="next-actions__filtered-item"
                  key={`filtered-${security.isin}`}
                  p="sm"
                  style={{
                    border: '1px solid var(--mantine-color-dark-5)',
                    backgroundColor: 'var(--mantine-color-dark-8)',
                  }}
                >
                  <Group className="next-actions__filtered-header" gap="xs" mb="xs" wrap="wrap">
                    <Text className="next-actions__filtered-symbol" size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                      {security.symbol || security.isin}
                    </Text>
                    {security.name && (
                      <Text className="next-actions__filtered-name" size="sm" c="dimmed" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        - {security.name}
                      </Text>
                    )}
                  </Group>
                  <Stack className="next-actions__filtered-reasons" gap={4}>
                    {security.reasons.map((entry, entryIndex) => (
                      entry.reasons.map((reasonObj, reasonIndex) => {
                        // Handle both old format (string) and new format (object with reason & dismissed)
                        const reasonText = typeof reasonObj === 'string' ? reasonObj : reasonObj.reason;
                        const isDismissed = typeof reasonObj === 'object' && reasonObj.dismissed;

                        const handleToggleDismiss = async () => {
                          try {
                            if (isDismissed) {
                              await api.undismissFilter(security.isin, entry.calculator, reasonText);
                            } else {
                              await api.dismissFilter(security.isin, entry.calculator, reasonText);
                            }
                            // Refresh recommendations to update the UI
                            fetchRecommendations();
                          } catch (error) {
                            console.error('Failed to toggle dismiss:', error);
                          }
                        };

                        return (
                          <Group className="next-actions__filter-reason" key={`${entryIndex}-${reasonIndex}`} gap="xs" wrap="nowrap">
                            <Text
                              className={`next-actions__reason-text ${isDismissed ? 'next-actions__reason-text--dismissed' : ''}`}
                              size="xs"
                              c="dimmed"
                              td={isDismissed ? 'line-through' : undefined}
                              style={{ fontFamily: 'var(--mantine-font-family)', lineHeight: 1.4, flex: 1 }}
                            >
                              • <Text span size="xs" c="gray.5" style={{ fontFamily: 'var(--mantine-font-family)' }}>{entry.calculator}</Text> {reasonText}
                            </Text>
                            <ActionIcon
                              className={`next-actions__dismiss-btn ${isDismissed ? 'next-actions__dismiss-btn--dismissed' : ''}`}
                              size="xs"
                              variant="subtle"
                              color={isDismissed ? 'green' : 'red'}
                              onClick={handleToggleDismiss}
                              title={isDismissed ? 'Re-enable this filter' : 'Dismiss this filter'}
                            >
                              {isDismissed ? <IconPlus size={12} /> : <IconX size={12} />}
                            </ActionIcon>
                          </Group>
                        );
                      })
                    ))}
                  </Stack>
                </Paper>
              ))}
            </Stack>
          </div>
        );
      })()}

      {/* Rejected Sequences - All evaluated sequences that weren't selected */}
      {recommendations?.rejected_sequences && recommendations.rejected_sequences.length > 0 && (
        <RejectedSequencesList
          sequences={recommendations.rejected_sequences}
          selectedScore={recommendations.end_state_score}
        />
      )}
    </Card>
  );
}
