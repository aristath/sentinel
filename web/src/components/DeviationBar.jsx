/**
 * Deviation Bar — single metric on its own horizontal scale.
 *
 * Each row renders:
 *   - plain-language label (top-left) + technical subtitle (small, dimmed)
 *   - the formatted value (top-right)
 *   - a horizontal bar with: min/max range, a vertical reference marker,
 *     and a colored dot at the current value
 *   - small labels under each end + the reference
 *
 * The dot color reflects `goodDirection`:
 *   - "high" -> green when value > reference, red when value < reference
 *   - "low"  -> green when value < reference, red when value > reference
 *   - "neutral" -> no color signal (context-dependent metric)
 *
 * Out-of-range values get clamped to the bar's edge but the headline number
 * still shows the true value — so a 60% drawdown on a 0..50% bar shows the
 * dot at the right edge and the text "60%" next to it.
 */
import { Group, Stack, Text } from '@mantine/core';
import { catppuccin } from '../theme';

function clamp01(x) {
  if (Number.isNaN(x) || !Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function dotColor(value, reference, goodDirection) {
  if (goodDirection === 'neutral') return catppuccin.text || catppuccin.lavender;
  const good =
    goodDirection === 'high' ? value >= reference : value <= reference;
  return good ? catppuccin.green : catppuccin.red;
}

export function DeviationBar({
  label,
  subLabel,
  value,
  formatted,
  min,
  max,
  reference,
  minLabel,
  maxLabel,
  referenceLabel,
  goodDirection = 'high',
}) {
  const span = max - min;
  const valuePct = span > 0 ? clamp01((value - min) / span) : 0.5;
  const refPct = span > 0 ? clamp01((reference - min) / span) : 0.5;
  const color = dotColor(value, reference, goodDirection);

  return (
    <Stack gap={2}>
      <Group justify="space-between" gap="xs" wrap="nowrap" align="baseline">
        <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
          <Text size="sm" fw={500}>
            {label}
          </Text>
          {subLabel ? (
            <Text size="xs" c="dimmed">
              {subLabel}
            </Text>
          ) : null}
        </Stack>
        <Text size="sm" fw={600} style={{ color, flexShrink: 0 }}>
          {formatted}
        </Text>
      </Group>

      {/* The bar itself */}
      <div
        style={{
          position: 'relative',
          height: 10,
          margin: '4px 0 2px',
          borderRadius: 0,
          background: 'var(--mantine-color-dark-5)',
          overflow: 'hidden',
        }}
      >
        {/* Solid colored fill from the reference marker to the current value.
            The fill's edge IS the current value — magnitude and direction
            of the deviation read at a glance, no extra markers needed. */}
        <div
          style={{
            position: 'absolute',
            left: `${Math.min(refPct, valuePct) * 100}%`,
            width: `${Math.abs(valuePct - refPct) * 100}%`,
            top: 0,
            bottom: 0,
            background: color,
          }}
        />
        {/* Reference marker — drawn on top of the fill so its start edge
            is still visible even when the deviation is small. */}
        <div
          style={{
            position: 'absolute',
            left: `${refPct * 100}%`,
            top: -2,
            bottom: -2,
            width: 1,
            background: catppuccin.subtext0 || '#94a3b8',
            transform: 'translateX(-0.5px)',
          }}
        />
      </div>

      {/* Range labels — min/reference/max */}
      <div style={{ position: 'relative', height: 14 }}>
        {minLabel ? (
          <Text size="xs" c="dimmed" style={{ position: 'absolute', left: 0 }}>
            {minLabel}
          </Text>
        ) : null}
        {referenceLabel ? (
          <Text
            size="xs"
            c="dimmed"
            style={{
              position: 'absolute',
              left: `${refPct * 100}%`,
              transform: 'translateX(-50%)',
              whiteSpace: 'nowrap',
            }}
          >
            {referenceLabel}
          </Text>
        ) : null}
        {maxLabel ? (
          <Text size="xs" c="dimmed" style={{ position: 'absolute', right: 0 }}>
            {maxLabel}
          </Text>
        ) : null}
      </div>
    </Stack>
  );
}
