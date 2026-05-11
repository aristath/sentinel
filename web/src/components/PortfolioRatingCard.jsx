/**
 * Portfolio Rating Card
 *
 * Top sidebar card sourced from the freedom24 PRAAMS analysis
 * (/api/portfolio/structure). Shows:
 *
 *   - Portfolio rating (1-7 stars + the "Favourable / Limited" prose labels)
 *   - 12-axis Risk/Return radar (investWatch.{countryRisk, performance, …})
 *     split visually into a risk half and a return half.
 *   - Key return factors (bullet list with check/warn icons)
 *   - Key risk factors  (bullet list with check/warn icons)
 *
 * Renders nothing while the structure endpoint is unavailable (no creds, or
 * upstream down) — the card just disappears rather than spamming an error.
 */
import { useMemo } from 'react';
import { Card, Group, Stack, Text, Tooltip } from '@mantine/core';
import { IconStar, IconStarFilled, IconCheck, IconAlertTriangle } from '@tabler/icons-react';
import { catppuccin } from '../theme';
import { usePortfolioStructure } from '../hooks/usePortfolioStructure';

const MAX_STARS = 7;
const MAX_AXIS = 7;

// The 12 investWatch axes, split into return-side (good if high) and
// risk-side (also good if high — they're "resilience" scores upstream).
// Order mirrors the visual layout on the freedom24 page: return axes top
// half, risk axes bottom half.
const RETURN_AXES = [
  { key: 'analystMarketViewView', label: 'Analyst' },
  { key: 'valuation', label: 'Valuation' },
  { key: 'performance', label: 'Performance' },
  { key: 'profitability', label: 'Profitability' },
  { key: 'growthMom', label: 'Growth' },
  { key: 'dividendsCoupons', label: 'Dividends' },
];
const RISK_AXES = [
  { key: 'solvency', label: 'Solvency' },
  { key: 'volatility', label: 'Volatility' },
  { key: 'stressTest', label: 'Stress' },
  { key: 'liquidity', label: 'Liquidity' },
  { key: 'countryRisk', label: 'Country' },
  { key: 'other', label: 'Other' },
];

function Stars({ value }) {
  const filled = Math.max(0, Math.min(MAX_STARS, Math.round(value || 0)));
  return (
    <Group gap={2}>
      {Array.from({ length: MAX_STARS }, (_, i) =>
        i < filled ? (
          <IconStarFilled key={i} size={14} color={catppuccin.yellow} />
        ) : (
          <IconStar key={i} size={14} color="var(--mantine-color-gray-6)" />
        )
      )}
    </Group>
  );
}

/**
 * Render the 12-axis radar as inline SVG. Two overlaid polygons: green for
 * the return-side axes, red for the risk-side axes. Axis labels are placed
 * just outside the polygon ring.
 */
function RiskReturnRadar({ investWatch }) {
  const layout = useMemo(() => {
    const axes = [...RETURN_AXES, ...RISK_AXES];
    const size = 220;
    const cx = size / 2;
    const cy = size / 2;
    const rMax = size / 2 - 26;
    const step = (Math.PI * 2) / axes.length;

    const points = axes.map((axis, i) => {
      const angle = -Math.PI / 2 + i * step;
      const v = Math.max(0, Math.min(MAX_AXIS, investWatch?.[axis.key] ?? 0));
      const r = (v / MAX_AXIS) * rMax;
      return {
        axis,
        angle,
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        labelX: cx + Math.cos(angle) * (rMax + 14),
        labelY: cy + Math.sin(angle) * (rMax + 14),
        v,
      };
    });

    // Split polygon into return half and risk half so the two colors blend.
    const returnPoly = points.slice(0, RETURN_AXES.length);
    const riskPoly = points.slice(RETURN_AXES.length);

    const gridRings = [0.25, 0.5, 0.75, 1.0].map((ratio) => {
      const r = rMax * ratio;
      const ringPts = axes.map((_, i) => {
        const angle = -Math.PI / 2 + i * step;
        return `${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`;
      });
      return ringPts.join(' ');
    });

    return { size, cx, cy, rMax, points, returnPoly, riskPoly, gridRings };
  }, [investWatch]);

  if (!investWatch) return null;
  const { size, cx, cy, points, returnPoly, riskPoly, gridRings } = layout;

  const toPath = (pts) => pts.map((p) => `${p.x},${p.y}`).join(' ');

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ display: 'block', margin: '0 auto' }}
      role="img"
      aria-label="Risk and Return profile (12 axes)"
    >
      {gridRings.map((pts, i) => (
        <polygon
          key={i}
          points={pts}
          fill="none"
          stroke="var(--mantine-color-dark-4)"
          strokeWidth={0.5}
        />
      ))}
      {points.map((p, i) => (
        <line
          key={`spoke-${i}`}
          x1={cx}
          y1={cy}
          x2={cx + Math.cos(p.angle) * layout.rMax}
          y2={cy + Math.sin(p.angle) * layout.rMax}
          stroke="var(--mantine-color-dark-4)"
          strokeWidth={0.5}
        />
      ))}
      <polygon
        points={toPath(returnPoly)}
        fill={catppuccin.green}
        fillOpacity={0.35}
        stroke={catppuccin.green}
        strokeWidth={1.5}
      />
      <polygon
        points={toPath(riskPoly)}
        fill={catppuccin.red}
        fillOpacity={0.30}
        stroke={catppuccin.red}
        strokeWidth={1.5}
      />
      {points.map((p, i) => (
        <Tooltip key={`tip-${i}`} label={`${p.axis.label}: ${p.v}/${MAX_AXIS}`}>
          <circle cx={p.x} cy={p.y} r={3} fill="var(--mantine-color-gray-3)" />
        </Tooltip>
      ))}
      {points.map((p, i) => (
        <text
          key={`lbl-${i}`}
          x={p.labelX}
          y={p.labelY}
          fontSize={10}
          fill="var(--mantine-color-gray-5)"
          textAnchor="middle"
          dominantBaseline="middle"
        >
          {p.axis.label}
        </text>
      ))}
    </svg>
  );
}

function FactorList({ factors, isRisk }) {
  if (!factors || factors.length === 0) return null;
  return (
    <Stack gap={4}>
      {factors.map((f) => {
        // `icon: true` upstream means "positive marker" (check). false →
        // "warning" marker.
        const Icon = f.icon ? IconCheck : IconAlertTriangle;
        const color = f.icon
          ? (isRisk ? catppuccin.green : catppuccin.green)
          : catppuccin.yellow;
        return (
          <Group key={f.priority} gap={6} wrap="nowrap" align="flex-start">
            <Icon size={14} color={color} style={{ flexShrink: 0, marginTop: 2 }} />
            <Text size="xs" c="dimmed" style={{ lineHeight: 1.3 }}>
              {f.text}
            </Text>
          </Group>
        );
      })}
    </Stack>
  );
}

export function PortfolioRatingCard() {
  const { data, isLoading, isError } = usePortfolioStructure();
  // The endpoint returns 503 when credentials aren't configured. React Query
  // surfaces that as `isError`; hide the card entirely rather than nag.
  if (isLoading || isError || !data) return null;

  const pa = data.portfolioAnalysis || {};
  const initial = pa.initial || {};
  const stars = pa.portfolioStars;
  const praams = initial.praams;
  const returnLabel = initial.keyFactors?.return?.characteristic;
  const riskLabel = initial.keyFactors?.risk?.characteristic;

  return (
    <Card p="sm" withBorder>
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Text size="xs" c="dimmed" fw={600} tt="uppercase">
            Portfolio Rating
          </Text>
          {praams !== undefined && (
            <Text size="xs" c="dimmed">
              {praams}/{MAX_STARS}
            </Text>
          )}
        </Group>

        {stars !== undefined && (
          <Group justify="center">
            <Stars value={stars} />
          </Group>
        )}

        <Group justify="space-around" gap="xs" wrap="nowrap">
          <Stack gap={0} align="center">
            <Text size="xs" c="dimmed">Return</Text>
            <Text size="sm" fw={500} c={catppuccin.green}>
              {returnLabel || '—'}
            </Text>
          </Stack>
          <Stack gap={0} align="center">
            <Text size="xs" c="dimmed">Risk</Text>
            <Text size="sm" fw={500} c={catppuccin.red}>
              {riskLabel || '—'}
            </Text>
          </Stack>
        </Group>

        <RiskReturnRadar investWatch={initial.investWatch} />

        <Stack gap="xs" mt={4}>
          {initial.keyFactors?.return?.factors?.length > 0 && (
            <Stack gap={4}>
              <Text size="xs" fw={600} c={catppuccin.green}>
                Return factors
              </Text>
              <FactorList factors={initial.keyFactors.return.factors} isRisk={false} />
            </Stack>
          )}
          {initial.keyFactors?.risk?.factors?.length > 0 && (
            <Stack gap={4}>
              <Text size="xs" fw={600} c={catppuccin.red}>
                Risk factors
              </Text>
              <FactorList factors={initial.keyFactors.risk.factors} isRisk={true} />
            </Stack>
          )}
        </Stack>
      </Stack>
    </Card>
  );
}
