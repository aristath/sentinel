/**
 * Security Allocation Card Component
 *
 * Displays portfolio allocation by security using a horizontal stacked bar table.
 * Gray shows the base, green shows buys, red shows sells.
 */
import { useMemo, useState } from 'react';
import { Card, Group, SegmentedControl, Stack, Switch, Text } from '@mantine/core';
import { formatEur } from '../utils/formatting';
import './SecurityAllocationCard.css';

const SORT_OPTIONS = [
  { value: 'allocation', label: 'By allocation' },
  { value: 'ideal', label: 'By ideal' },
];

function formatPct(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

export function SecurityAllocationCard({ securities, recommendations, longTermPlan, cashAfterPlan }) {
  const [sortBy, setSortBy] = useState('allocation');
  const [showIdeal, setShowIdeal] = useState(true);

  const { rows, maxValue } = useMemo(() => {
    if ((!securities || securities.length === 0) && !longTermPlan) {
      return { rows: [], maxValue: 0 };
    }

    const targetsBySymbol = new Map((longTermPlan?.targets || []).map((target) => [target.symbol, target]));

    // A row is shown if it's relevant to any of the three series:
    //   - currently held (`value_eur > 0`)
    //   - has a pending recommendation (buy or sell)
    //   - has a planner-derived ideal weight > 0 — only when the ideal layer is
    //     turned on (otherwise rows that exist purely because of an ideal would
    //     render as empty bars).
    const data = (securities || [])
      .filter((s) => {
        const hasPosition = s.has_position && s.value_eur > 0;
        const hasRecommendation = recommendations?.some((r) => r.symbol === s.symbol);
        const hasIdeal = showIdeal && targetsBySymbol.has(s.symbol);
        return hasPosition || hasRecommendation || hasIdeal;
      })
      .map((s) => {
        const rec = recommendations?.find((r) => r.symbol === s.symbol);
        const delta = rec ? rec.value_delta_eur : 0;
        const target = targetsBySymbol.get(s.symbol);
        const current = s.value_eur || 0;
        const final = current + delta;
        const ideal = Number(target?.target_value_eur ?? rec?.target_value_eur ?? current);
        const modelIdeal = Number(target?.model_target_value_eur ?? ideal);

        if (final <= 0 && current <= 0 && ideal <= 0) return null;

        const isBuy = delta > 0;
        const isSell = delta < 0;

        return {
          symbol: s.symbol,
          current,
          final: Math.max(0, final),
          delta,
          ideal,
          currentAllocation: s.current_allocation || 0,
          postPlanAllocation: s.post_plan_allocation ?? s.current_allocation ?? 0,
          idealAllocation: target?.target_allocation_pct ?? s.ideal_allocation ?? 0,
          targetGap: Number(target?.gap_eur || 0),
          modelIdeal,
          sellLocked: Boolean(target?.sell_locked),
          isBuy,
          isSell,
          // Bar must extend to whichever of current / final / ideal is largest
          // so the ideal marker always lands inside the bar's range. When the
          // ideal is hidden it doesn't influence the scale.
          maxBar: showIdeal
            ? Math.max(current, final, ideal)
            : Math.max(current, final),
        };
      })
      .filter(Boolean);

    const currentCash = Number(longTermPlan?.current_cash_eur || 0);
    const targetCash = Number(longTermPlan?.target_cash_value_eur || 0);
    if (currentCash > 0 || targetCash > 0) {
      const currentTotal = Number(longTermPlan?.current_total_value_eur || 0);
      const cashGap = Number(longTermPlan?.cash_gap_eur || 0);
      const plannedCash = Number.isFinite(Number(cashAfterPlan)) ? Math.max(0, Number(cashAfterPlan)) : currentCash;
      const cashDelta = plannedCash - currentCash;
      data.push({
        symbol: 'CASH',
        current: currentCash,
        final: plannedCash,
        delta: cashDelta,
        ideal: targetCash,
        currentAllocation: currentTotal > 0 ? (currentCash / currentTotal) * 100 : 0,
        postPlanAllocation: currentTotal > 0 ? (plannedCash / currentTotal) * 100 : 0,
        idealAllocation: Number(longTermPlan?.target_cash_allocation_pct || 0),
        targetGap: cashGap,
        isBuy: cashDelta > 0,
        isSell: cashDelta < 0,
        maxBar: showIdeal ? Math.max(currentCash, plannedCash, targetCash) : Math.max(currentCash, plannedCash),
      });
    }

    data.sort((a, b) => {
        if (sortBy === 'ideal') return b.ideal - a.ideal;
        // 'allocation' — largest current/post-plan holding first
        return Math.max(b.final, b.current) - Math.max(a.final, a.current);
      });

    const max = Math.max(...data.map((d) => d.maxBar), 0);

    return { rows: data, maxValue: max };
  }, [securities, recommendations, longTermPlan, cashAfterPlan, sortBy, showIdeal]);

  const hasData = rows.length > 0;

  return (
    <Card className="security-alloc-card" p="md" withBorder>
      <Stack gap="sm">
        <Group className="security-alloc-card__header" justify="space-between" wrap="wrap">
          <Text className="security-alloc-card__title" size="sm" tt="uppercase" c="dimmed" fw={600}>
            Security Allocation
          </Text>
          <Group gap="sm" wrap="nowrap">
            <SegmentedControl
              size="xs"
              value={sortBy}
              onChange={setSortBy}
              data={SORT_OPTIONS}
            />
            <Switch
              size="xs"
              label="Ideal"
              checked={showIdeal}
              onChange={(e) => setShowIdeal(e.currentTarget.checked)}
            />
          </Group>
        </Group>

        {hasData ? (
          <div className="allocation-table-wrapper">
            <table className="allocation-table">
              <tbody>
                {rows.map((row) => {
                  const grayWidth = maxValue > 0
                    ? (row.isBuy ? ((row.final - row.delta) / maxValue) * 100 : (row.final / maxValue) * 100)
                    : 0;
                  const deltaWidth = maxValue > 0 ? (Math.abs(row.delta) / maxValue) * 100 : 0;
                  const idealPct = maxValue > 0 ? (row.ideal / maxValue) * 100 : 0;
                  const targetGapText = `${row.targetGap >= 0 ? '+' : '-'}${formatEur(Math.abs(row.targetGap))}`;
                  const idealTitle = row.sellLocked
                    ? `No-sell floor: ${formatEur(row.ideal)}; model target: ${formatEur(row.modelIdeal)}`
                    : `12-month target: ${formatEur(row.ideal)}; gap: ${targetGapText}`;

                  return (
                    <tr key={row.symbol}>
                      <td className="allocation-table__symbol">{row.symbol}</td>
                      <td className="allocation-table__bar-cell">
                        <div className="allocation-bar">
                          {grayWidth > 0 && (
                            <div
                              className="allocation-bar__segment allocation-bar__segment--gray"
                              style={{ width: `${grayWidth}%` }}
                            />
                          )}
                          {row.isBuy && deltaWidth > 0 && (
                            <div
                              className="allocation-bar__segment allocation-bar__segment--green"
                              style={{ width: `${deltaWidth}%` }}
                            />
                          )}
                          {row.isSell && deltaWidth > 0 && (
                            <div
                              className="allocation-bar__segment allocation-bar__segment--red"
                              style={{ width: `${deltaWidth}%` }}
                            />
                          )}
                          {showIdeal && (
                            <div
                              className="allocation-bar__ideal"
                              style={{ left: `${idealPct}%` }}
                              title={idealTitle}
                            />
                          )}
                        </div>
                      </td>
                      <td className="allocation-table__numbers">
                        <div>
                          <span>{formatPct(row.currentAllocation)}</span>
                          <span className="allocation-table__arrow">→</span>
                          <span className={row.isBuy ? 'allocation-table__buy' : row.isSell ? 'allocation-table__sell' : ''}>
                            {formatPct(row.postPlanAllocation)}
                          </span>
                          <span className="allocation-table__target">/ {formatPct(row.idealAllocation)}</span>
                        </div>
                        <div className="allocation-table__target-value">
                          {formatEur(row.ideal)} · {row.sellLocked ? 'locked' : targetGapText}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Text size="sm" c="dimmed" ta="center" py="xl">
            No allocation data available
          </Text>
        )}

        <Group gap="md" wrap="wrap" className="allocation-legend">
          <LegendSwatch kind="gray" label="Current holding" />
          <LegendSwatch kind="green" label="Today's increase" />
          <LegendSwatch kind="red" label="Today's decrease" />
          {showIdeal && <LegendSwatch kind="ideal" label="12-month target" />}
        </Group>
      </Stack>
    </Card>
  );
}

function LegendSwatch({ kind, label }) {
  return (
    <Group gap={6} wrap="nowrap">
      <span className={`allocation-legend__swatch allocation-legend__swatch--${kind}`} />
      <Text size="xs" c="dimmed">
        {label}
      </Text>
    </Group>
  );
}
