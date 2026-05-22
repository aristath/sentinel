/**
 * Composition Card — portfolio breakdowns as horizontal stacked bars.
 *
 * Five panels, each a 100%-wide segmented bar plus a small legend:
 *   - Country (ISO-2)
 *   - Continent (rolled up from country)
 *   - Industry (TRBC)
 *   - Currency (instrument trading currency)
 *   - Asset class (stock / ETF / depositary receipt)
 *
 * Data: /api/portfolio/composition. Computed server-side from current
 * positions + the new broker-sourced geography/industry fields. The card
 * collapses to nothing while the endpoint is unavailable.
 */
import { Card, Group, Stack, Text } from '@mantine/core';
import { catppuccin } from '../theme';
import { usePortfolioComposition } from '../hooks/usePortfolioComposition';
import { CompositionRadar } from './CompositionRadar';

const PALETTE = [
  catppuccin.blue,
  catppuccin.green,
  catppuccin.peach || catppuccin.yellow,
  catppuccin.mauve,
  catppuccin.teal,
  catppuccin.pink,
  catppuccin.red,
  catppuccin.lavender,
  catppuccin.sapphire || catppuccin.blue,
  catppuccin.flamingo || catppuccin.pink,
];

function formatPct(pct) {
  const v = pct * 100;
  return v >= 10 ? v.toFixed(0) : v.toFixed(1);
}

function StackedBar({ buckets }) {
  const visible = (buckets || []).filter((b) => (b.pct || 0) > 0);
  if (visible.length === 0) {
    return (
      <Text size="xs" c="dimmed" fs="italic">
        no data
      </Text>
    );
  }
  return (
    <Stack gap={6}>
      <div
        style={{
          display: 'flex',
          width: '100%',
          height: 10,
          borderRadius: 4,
          overflow: 'hidden',
          background: 'var(--mantine-color-dark-5)',
        }}
      >
        {visible.map((b, i) => (
          <div
            key={b.name + i}
            title={`${b.name}: ${formatPct(b.pct)}%`}
            style={{
              width: `${b.pct * 100}%`,
              background: PALETTE[i % PALETTE.length],
            }}
          />
        ))}
      </div>
      <Group gap="md" wrap="wrap">
        {visible.map((b, i) => (
          <Group key={b.name + i} gap={4} wrap="nowrap">
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: PALETTE[i % PALETTE.length],
                flexShrink: 0,
              }}
            />
            <Text size="xs" c="dimmed">
              {b.name} {formatPct(b.pct)}%
            </Text>
          </Group>
        ))}
      </Group>
    </Stack>
  );
}

function Section({ title, buckets }) {
  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} tt="uppercase" c="dimmed">
        {title}
      </Text>
      <StackedBar buckets={buckets} />
    </Stack>
  );
}

function RadarSection({ title, current, ideal, postPlan }) {
  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} tt="uppercase" c="dimmed">
        {title}
      </Text>
      <CompositionRadar current={current} ideal={ideal} postPlan={postPlan} />
    </Stack>
  );
}

export function CompositionCard() {
  const { data, isLoading, isError } = usePortfolioComposition();
  if (isLoading || isError || !data?.composition) return null;
  const c = data.composition;
  const ideal = data.composition_ideal || {};
  const postPlan = data.composition_post_plan || {};

  return (
    <Card p="sm" withBorder>
      <Stack gap="md">
        <Text size="xs" c="dimmed" fw={600} tt="uppercase">
          Composition
        </Text>
        <RadarSection
          title="Country of risk"
          current={c.by_country}
          ideal={ideal.by_country}
          postPlan={postPlan.by_country}
        />
        <RadarSection
          title="Industry"
          current={c.by_industry}
          ideal={ideal.by_industry}
          postPlan={postPlan.by_industry}
        />
        <Section title="Continent" buckets={c.by_continent} />
        <Section title="Currency" buckets={c.by_currency} />
        <Section title="Asset class" buckets={c.by_asset_class} />
      </Stack>
    </Card>
  );
}
