/**
 * Forward Return Card
 *
 * Visualises `initial.return[]` from the freedom24 PRAAMS analysis: indexed
 * portfolio value (Today = 100) projected 1-5 years ahead, with the
 * confidence band drawn behind the central total-return line.
 *
 * Renders nothing if structure data isn't available (no creds / upstream
 * down).
 */
import { useMemo } from 'react';
import { Card, Group, Stack, Text } from '@mantine/core';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { catppuccin } from '../theme';
import { usePortfolioStructure } from '../hooks/usePortfolioStructure';

function fmt(v) {
  return typeof v === 'number' ? v.toFixed(1) : v;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  // Recharts gives us each visible series — pull what we need out by key.
  const row = payload[0]?.payload || {};
  return (
    <div
      style={{
        background: 'var(--mantine-color-dark-7)',
        border: '1px solid var(--mantine-color-dark-4)',
        padding: '6px 8px',
        borderRadius: 4,
        fontSize: 11,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div style={{ color: catppuccin.blue }}>
        Total return: {fmt(row.totalReturn)}
      </div>
      <div style={{ color: 'var(--mantine-color-gray-5)' }}>
        Range: {fmt(row.confidenceLow)} – {fmt(row.confidenceHigh)}
      </div>
    </div>
  );
}

export function ForwardReturnCard() {
  const { data, isLoading, isError } = usePortfolioStructure();
  const series = useMemo(() => {
    const items = data?.portfolioAnalysis?.initial?.return || [];
    return items
      .slice()
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .map((p) => ({
        label: p.label,
        totalReturn: p.totalReturn,
        confidenceLow: p.confidenceLow,
        confidenceHigh: p.confidenceHigh,
        // Recharts area requires a single value; we synthesize a "spread"
        // by stacking confidenceLow + (high - low) so the Area sits between
        // the two confidence bounds.
        bandLow: p.confidenceLow,
        bandSpread: Math.max(0, (p.confidenceHigh ?? 0) - (p.confidenceLow ?? 0)),
      }));
  }, [data]);

  if (isLoading || isError || !data || series.length === 0) return null;

  const last = series[series.length - 1];
  const lastPct = last ? last.totalReturn - 100 : 0;
  const lastColor = lastPct >= 0 ? catppuccin.green : catppuccin.red;

  return (
    <Card p="sm" withBorder>
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Forward return projection
          </Text>
          <Text size="xs" c="dimmed">
            Today = 100; central line = expected total return; band = 90% range
          </Text>
        </Group>

        <Group gap="xl">
          <Stack gap={0}>
            <Text size="xs" c="dimmed">5Y central</Text>
            <Text size="md" fw={600} c={lastColor}>
              {lastPct >= 0 ? '+' : ''}{fmt(lastPct)}%
            </Text>
          </Stack>
          <Stack gap={0}>
            <Text size="xs" c="dimmed">5Y range</Text>
            <Text size="md" fw={500}>
              {fmt(last?.confidenceLow - 100)}% to {fmt(last?.confidenceHigh - 100)}%
            </Text>
          </Stack>
        </Group>

        <div style={{ width: '100%', height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: 'var(--mantine-color-gray-5)' }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--mantine-color-gray-5)' }}
                domain={['dataMin - 5', 'dataMax + 5']}
                tickFormatter={(v) => `${Math.round(v)}`}
              />
              <Tooltip content={<ChartTooltip />} />
              {/* Confidence band: stack the low + spread so the visible area
                  occupies [low, high]. The low layer is transparent. */}
              <Area
                type="monotone"
                dataKey="bandLow"
                stackId="band"
                stroke="none"
                fill="transparent"
              />
              <Area
                type="monotone"
                dataKey="bandSpread"
                stackId="band"
                stroke="none"
                fill={catppuccin.blue}
                fillOpacity={0.18}
              />
              <Line
                type="monotone"
                dataKey="totalReturn"
                stroke={catppuccin.blue}
                strokeWidth={2}
                dot={{ r: 3, fill: catppuccin.blue }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Stack>
    </Card>
  );
}
