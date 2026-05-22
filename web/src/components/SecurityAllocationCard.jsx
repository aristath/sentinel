/**
 * Security Allocation Card Component
 *
 * Displays portfolio allocation by security using a horizontal stacked bar table.
 * Gray shows the base, green shows buys, red shows sells.
 */
import { useMemo, useState } from 'react';
import { Card, Group, SegmentedControl, Stack, Switch, Text } from '@mantine/core';
import './SecurityAllocationCard.css';

const SORT_OPTIONS = [
  { value: 'allocation', label: 'By allocation' },
  { value: 'ideal', label: 'By ideal' },
];

export function SecurityAllocationCard({ securities, recommendations, totalValueEur = 0 }) {
  const [sortBy, setSortBy] = useState('allocation');
  const [showIdeal, setShowIdeal] = useState(true);

  const { rows, maxValue } = useMemo(() => {
    if (!securities || securities.length === 0) {
      return { rows: [], maxValue: 0 };
    }

    // A row is shown if it's relevant to any of the three series:
    //   - currently held (`value_eur > 0`)
    //   - has a pending recommendation (buy or sell)
    //   - has a planner-derived ideal weight > 0 — only when the ideal layer is
    //     turned on (otherwise rows that exist purely because of an ideal would
    //     render as empty bars).
    const data = securities
      .filter((s) => {
        const hasPosition = s.has_position && s.value_eur > 0;
        const hasRecommendation = recommendations?.some((r) => r.symbol === s.symbol);
        const hasIdeal = showIdeal && (s.ideal_allocation || 0) > 0;
        return hasPosition || hasRecommendation || hasIdeal;
      })
      .map((s) => {
        const rec = recommendations?.find((r) => r.symbol === s.symbol);
        const delta = rec ? rec.value_delta_eur : 0;
        const current = s.value_eur || 0;
        const final = current + delta;
        // Ideal EUR target. Recommendations carry it directly; for securities
        // without a recommendation we derive it from ideal_allocation (%) ×
        // total portfolio value. Fallback to `current` when neither is known
        // — that just hides the marker under the bar's right edge.
        let ideal;
        if (rec) {
          ideal = rec.target_value_eur;
        } else if ((s.ideal_allocation || 0) > 0 && totalValueEur > 0) {
          ideal = (s.ideal_allocation / 100) * totalValueEur;
        } else {
          ideal = current;
        }

        // Skip rows that contribute nothing to any of the three series.
        if (final <= 0 && current <= 0 && ideal <= 0) return null;

        const isBuy = delta > 0;
        const isSell = delta < 0;

        return {
          symbol: s.symbol,
          current,
          final: Math.max(0, final),
          delta,
          ideal,
          isBuy,
          isSell,
          // Bar must extend to whichever of current / final / ideal is largest
          // so the ideal marker always lands inside the bar's range. When the
          // ideal is hidden it doesn't influence the scale.
          maxBar: showIdeal ? Math.max(current, final, ideal) : Math.max(current, final),
        };
      })
      .filter(Boolean)
      .sort((a, b) => {
        if (sortBy === 'ideal') return b.ideal - a.ideal;
        // 'allocation' — largest current/post-plan holding first
        return Math.max(b.final, b.current) - Math.max(a.final, a.current);
      });

    const max = Math.max(...data.map((d) => d.maxBar), 0);

    return { rows: data, maxValue: max };
  }, [securities, recommendations, totalValueEur, sortBy, showIdeal]);

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
                  const grayWidth = row.isBuy
                    ? ((row.final - row.delta) / maxValue) * 100
                    : (row.final / maxValue) * 100;
                  const deltaWidth = (Math.abs(row.delta) / maxValue) * 100;
                  const idealPct = maxValue > 0 ? (row.ideal / maxValue) * 100 : 0;

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
                              title={`Ideal: €${row.ideal.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                            />
                          )}
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
          <LegendSwatch kind="green" label="Will buy" />
          <LegendSwatch kind="red" label="Will sell" />
          {showIdeal && <LegendSwatch kind="ideal" label="Planner's ideal" />}
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
