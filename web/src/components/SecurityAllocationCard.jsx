/**
 * Security Allocation Card Component
 *
 * Displays portfolio allocation by security using a horizontal stacked bar table.
 * Gray shows the base, green shows buys, red shows sells.
 */
import { useMemo } from 'react';
import { Card, Group, Text } from '@mantine/core';
import './SecurityAllocationCard.css';

export function SecurityAllocationCard({ securities, recommendations }) {
  const { rows, maxValue } = useMemo(() => {
    if (!securities || securities.length === 0) {
      return { rows: [], maxValue: 0 };
    }

    // Build rows for securities with positions or recommendations
    const data = securities
      .filter((s) => {
        const hasPosition = s.has_position && s.value_eur > 0;
        const hasRecommendation = recommendations?.some((r) => r.symbol === s.symbol);
        return hasPosition || hasRecommendation;
      })
      .map((s) => {
        const rec = recommendations?.find((r) => r.symbol === s.symbol);
        const delta = rec ? rec.value_delta_eur : 0;
        const current = s.value_eur || 0;
        const final = current + delta;

        // Skip if final is 0 or negative (fully sold)
        if (final <= 0 && current <= 0) return null;

        const isBuy = delta > 0;
        const isSell = delta < 0;

        return {
          symbol: s.symbol,
          current,
          final: Math.max(0, final),
          delta,
          isBuy,
          isSell,
          // For scaling: max of current or final
          maxBar: Math.max(current, final),
        };
      })
      .filter(Boolean)
      .sort((a, b) => b.final - a.final);

    const max = Math.max(...data.map((d) => d.maxBar), 0);

    return { rows: data, maxValue: max };
  }, [securities, recommendations]);

  const hasData = rows.length > 0;

  return (
    <Card className="security-alloc-card" p="md" withBorder>
      <Group className="security-alloc-card__header" justify="space-between" mb="md">
        <Text className="security-alloc-card__title" size="sm" tt="uppercase" c="dimmed" fw={600}>
          Security Allocation
        </Text>
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
    </Card>
  );
}
