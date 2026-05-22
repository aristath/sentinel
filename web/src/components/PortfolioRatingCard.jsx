/**
 * Portfolio Rating Card — stack of deviation bars, one per metric.
 *
 * Each metric has its own scale and reference point because they're not
 * comparable on a single axis. The dot is colored green/red based on whether
 * we're on the "good" side of the reference — no need to remember which
 * direction means good for a given metric.
 *
 * Source: `/api/portfolio/composition`. Card collapses to nothing while the
 * endpoint is unavailable.
 */
import { Card, Stack, Text } from '@mantine/core';
import { usePortfolioComposition } from '../hooks/usePortfolioComposition';
import { DeviationBar } from './DeviationBar';

function pct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(digits)}%`;
}

function num(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toFixed(digits);
}

export function PortfolioRatingCard() {
  const { data, isLoading, isError } = usePortfolioComposition();
  if (isLoading || isError || !data?.metrics) return null;
  const m = data.metrics;
  const benchmarks = data.benchmarks || [];
  const primary = benchmarks.find((b) => b.symbol === m.primary_benchmark_symbol) || benchmarks[0];

  // Each row is one metric. Ranges and reference points are intentionally
  // hard-coded — they're stable financial-literacy anchors, not user knobs.
  const rows = [
    {
      label: 'Last year',
      subLabel: '1Y return — money made (or lost) after subtracting deposits',
      value: m.return_1y,
      formatted: pct(m.return_1y),
      min: -0.3,
      max: 0.3,
      reference: 0,
      minLabel: '-30%',
      maxLabel: '+30%',
      referenceLabel: 'break-even',
      goodDirection: 'high',
    },
    {
      label: 'Since the beginning',
      subLabel: `CAGR — annualized growth since first deposit (${num(m.inception_years || 0, 1)} years)`,
      value: m.return_since_inception_cagr,
      formatted: pct(m.return_since_inception_cagr),
      min: -0.3,
      max: 0.3,
      reference: 0,
      minLabel: '-30%',
      maxLabel: '+30%',
      referenceLabel: 'break-even',
      goodDirection: 'high',
    },
    {
      label: 'Bumpiness',
      subLabel: 'Annual volatility — how wild the daily price swings are',
      value: m.volatility,
      formatted: pct(m.volatility),
      min: 0,
      max: 0.4,
      reference: 0.18,
      minLabel: 'calm',
      maxLabel: 'wild',
      referenceLabel: 'typical',
      goodDirection: 'low',
    },
    {
      label: 'Worst drop',
      subLabel: 'Max drawdown — biggest dip from peak to bottom',
      value: m.max_drawdown,
      formatted: pct(m.max_drawdown),
      min: 0,
      max: 0.5,
      reference: 0.2,
      minLabel: 'no dips',
      maxLabel: 'crash',
      referenceLabel: 'tolerable',
      goodDirection: 'low',
    },
    {
      label: 'Reward for the bumps',
      subLabel: 'Sharpe ratio — return per unit of risk, vs cash',
      value: m.sharpe,
      formatted: num(m.sharpe),
      min: -1,
      max: 3,
      reference: 1.0,
      minLabel: '-1',
      maxLabel: '3',
      referenceLabel: 'good',
      goodDirection: 'high',
    },
    {
      label: 'All in one basket?',
      subLabel: 'Concentration (HHI) — 0 spread evenly, 1 single position',
      value: m.hhi,
      formatted: num(m.hhi, 3),
      min: 0,
      max: 1,
      reference: 0.1,
      minLabel: 'spread',
      maxLabel: 'all-in',
      referenceLabel: 'diversified',
      goodDirection: 'low',
    },
  ];

  if (primary) {
    rows.push(
      {
        label: 'Tracks the market?',
        subLabel: `Beta vs ${primary.symbol} — 1.0 mirrors the market`,
        value: primary.beta,
        formatted: num(primary.beta),
        min: -1,
        max: 2,
        reference: 1.0,
        minLabel: '-1',
        maxLabel: '+2',
        referenceLabel: 'market',
        goodDirection: 'neutral',
      },
      {
        label: 'Beating the market?',
        subLabel: `Alpha vs ${primary.symbol} — outperformance over last year`,
        value: m.alpha_1y,
        formatted: pct(m.alpha_1y),
        min: -0.2,
        max: 0.2,
        reference: 0,
        minLabel: '-20%',
        maxLabel: '+20%',
        referenceLabel: 'matches',
        goodDirection: 'high',
      },
    );
  }

  return (
    <Card p="sm" withBorder>
      <Stack gap="md">
        <Text size="xs" c="dimmed" fw={600} tt="uppercase">
          Risk / Return
        </Text>

        <Stack gap="md">
          {rows.map((row) => (
            <DeviationBar key={row.label} {...row} />
          ))}
        </Stack>

        {!primary ? (
          <Text size="xs" c="dimmed" fs="italic">
            Benchmarks not yet synced — market-comparison rows will populate on next sync cycle.
          </Text>
        ) : null}
      </Stack>
    </Card>
  );
}
