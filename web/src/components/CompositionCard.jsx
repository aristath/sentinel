/**
 * Composition Card
 *
 * Stacked horizontal-bar breakdowns sourced from the freedom24 PRAAMS
 * analysis (/api/portfolio/structure). Four panels:
 *
 *   - Asset class       (e.g. Equity 100%)
 *   - Sector / Industry (e.g. Industrials 56%, Technology 40%, Energy 4%)
 *   - Region / Country  (e.g. Asia & Oceania 61%, Europe 24%, North America 15%)
 *   - Currency          (e.g. HKD 56%, EUR 36%, USD 7%)
 *
 * Each bar is a single 100%-wide segmented strip with proportional slices
 * plus a small legend below. The card collapses to nothing if the
 * structure endpoint is unavailable.
 */
import { Card, Group, Stack, Text } from '@mantine/core';
import { catppuccin } from '../theme';
import { usePortfolioStructure } from '../hooks/usePortfolioStructure';

// Reusable palette — picks ordered for visual contrast on the dark theme.
const PALETTE = [
  catppuccin.blue,
  catppuccin.green,
  catppuccin.peach || catppuccin.yellow,
  catppuccin.mauve,
  catppuccin.teal,
  catppuccin.pink,
  catppuccin.red,
  catppuccin.lavender,
];

function StackedBar({ items }) {
  // `items` is an array of {label, value} with values that sum to ~100.
  // Filter zero-value slices to avoid invisible-but-counted segments.
  const visible = (items || []).filter((it) => (it.value || 0) > 0);
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
        {visible.map((it, i) => (
          <div
            key={it.label + i}
            title={`${it.label}: ${it.value}%`}
            style={{
              width: `${it.value}%`,
              background: PALETTE[i % PALETTE.length],
            }}
          />
        ))}
      </div>
      <Group gap="md" wrap="wrap">
        {visible.map((it, i) => (
          <Group key={it.label + i} gap={4} wrap="nowrap">
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
              {it.label} {it.value}%
            </Text>
          </Group>
        ))}
      </Group>
    </Stack>
  );
}

function Section({ title, items }) {
  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} tt="uppercase" c="dimmed">
        {title}
      </Text>
      <StackedBar items={items} />
    </Stack>
  );
}

export function CompositionCard() {
  const { data, isLoading, isError } = usePortfolioStructure();
  if (isLoading || isError || !data) return null;
  const initial = data.portfolioAnalysis?.initial || {};

  return (
    <Card p="sm" withBorder>
      <Stack gap="sm">
        <Text size="xs" c="dimmed" fw={600} tt="uppercase">
          Composition
        </Text>
        <Section title="Asset class" items={initial.assetClasses} />
        <Section
          title="Sector"
          items={(initial.sectorIndustry?.graph || []).map((s) => ({
            label: s.label,
            value: s.value,
          }))}
        />
        <Section
          title="Region"
          items={(initial.regionCountry?.graph || []).map((r) => ({
            label: r.label,
            value: r.value,
          }))}
        />
        <Section title="Currency" items={initial.currency} />
      </Stack>
    </Card>
  );
}
