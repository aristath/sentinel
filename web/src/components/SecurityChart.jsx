/**
 * Security Chart Component
 *
 * Responsive SVG-based price chart with cost-basis coloring and future projection.
 * Data is expected to be pre-validated by the backend (invalid peaks removed).
 */
import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

/**
 * Renders a responsive price chart with optional cost-basis coloring and future projections
 *
 * @param {Object} props
 * @param {Array} props.prices - Array of {date, close} objects (pre-validated)
 * @param {number} props.avgCost - Average purchase price (for cost-basis coloring)
 * @param {number} props.expectedReturn - Blended expected return (0-1) for projection
 * @param {number} props.waveletScore - Wavelet-only score (0-1) for projection
 * @param {number} props.mlScore - ML-only score (0-1) for projection
 * @param {boolean} props.hasPosition - Whether user has a position
 * @param {number} props.height - Chart height (default 120)
 */
export function SecurityChart({
  prices = [],
  avgCost = 0,
  expectedReturn = 0,
  waveletScore = null,
  mlScore = null,
  hasPosition = false,
  height = 120,
}) {
  const [containerRef, width] = useResponsiveWidth(300);

  // Render chart
  const renderChart = () => {
    // Not enough data
    if (!prices || prices.length < 2) {
      return (
        <div
          className="security-chart__empty"
          style={{
            width: '100%',
            height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            // Style guide: subtle/muted text uses Overlay 1
            color: catppuccin.overlay1,
            fontSize: '0.875rem',
          }}
        >
          No price data
        </div>
      );
    }

    const padding = { top: 10, right: 10, bottom: 10, left: 10 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    if (chartWidth <= 0 || chartHeight <= 0) return null;

    // Extract values (already validated by backend)
    const values = prices.map((p) => p.close);
    const lastPrice = values[values.length - 1];

    // Calculate projection points (extend 15% into future)
    const projectionDays = Math.ceil(values.length * 0.15);

    // Helper to calculate projected values for a given score
    const calcProjection = (score) => {
      if (score === null || score === undefined) return [];
      const dailyReturn = score / 252;
      const projected = [];
      for (let i = 1; i <= projectionDays; i++) {
        projected.push(lastPrice * (1 + dailyReturn * i));
      }
      return projected;
    };

    // Calculate projections for all three scores
    const blendedProjection = calcProjection(expectedReturn);
    const waveletProjection = calcProjection(waveletScore);
    const mlProjection = calcProjection(mlScore);

    // Combine all values for min/max calculation
    const allProjectedValues = [...blendedProjection, ...waveletProjection, ...mlProjection];
    const allValues = [...values, ...allProjectedValues];
    const minValue = Math.min(...allValues, avgCost || Infinity);
    const maxValue = Math.max(...allValues, avgCost || -Infinity);
    const valueRange = maxValue - minValue || 1;

    // Scale functions
    const scaleX = (i, total) => padding.left + (i / (total - 1)) * chartWidth;
    const scaleY = (v) => padding.top + chartHeight - ((v - minValue) / valueRange) * chartHeight;

    // Determine total points for X scaling (use blended or any non-empty projection)
    const maxProjectionLen = Math.max(blendedProjection.length, waveletProjection.length, mlProjection.length);
    const totalPoints = values.length + maxProjectionLen;

    // Build main price path points
    const points = values.map((v, i) => ({
      x: scaleX(i, totalPoints),
      y: scaleY(v),
      value: v,
    }));

    // Helper to build projection points array
    const buildProjectionPoints = (projectedValues) => {
      return projectedValues.map((v, i) => ({
        x: scaleX(values.length + i, totalPoints),
        y: scaleY(v),
        value: v,
      }));
    };

    const blendedPoints = buildProjectionPoints(blendedProjection);
    const waveletPoints = buildProjectionPoints(waveletProjection);
    const mlPoints = buildProjectionPoints(mlProjection);

    // Generate SVG paths
    let segments = [];

    if (hasPosition && avgCost > 0) {
      let currentSegment = [points[0]];
      let currentColor = points[0].value >= avgCost ? catppuccin.green : catppuccin.red;

      for (let i = 1; i < points.length; i++) {
        const isAbove = points[i].value >= avgCost;
        const segmentColor = isAbove ? catppuccin.green : catppuccin.red;

        if (segmentColor !== currentColor) {
          segments.push({ points: [...currentSegment], color: currentColor });
          currentSegment = [points[i - 1], points[i]];
          currentColor = segmentColor;
        } else {
          currentSegment.push(points[i]);
        }
      }
      segments.push({ points: currentSegment, color: currentColor });
    } else {
      const isPositive = values[values.length - 1] > values[0];
      segments = [{ points, color: isPositive ? catppuccin.blue : catppuccin.overlay1 }];
    }

    const lastPoint = points[points.length - 1];

    return (
      <svg width={width} height={height} style={{ display: 'block' }} className="security-chart__svg">
        {/* Average cost line */}
        {hasPosition && avgCost > 0 && (
          <line
            x1={padding.left}
            y1={scaleY(avgCost)}
            x2={width - padding.right}
            y2={scaleY(avgCost)}
            stroke={catppuccin.overlay0}
            strokeWidth={1}
            strokeDasharray="2,2"
            opacity={0.5}
            className="security-chart__cost-line"
          />
        )}

        {/* Price segments */}
        {segments.map((seg, idx) => (
          <path
            key={idx}
            d={buildSmoothPath(seg.points)}
            fill="none"
            stroke={seg.color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`security-chart__price-segment security-chart__price-segment--${idx}`}
          />
        ))}

        {/* Wavelet projection (cyan dashed) */}
        {waveletPoints.length > 0 && (
          <path
            d={buildSmoothPath([points[points.length - 1], ...waveletPoints])}
            fill="none"
            stroke={catppuccin.sapphire}
            strokeWidth={1.5}
            strokeDasharray="4,4"
            opacity={0.6}
            className="security-chart__projection security-chart__projection--wavelet"
          />
        )}

        {/* ML projection (amber dashed) */}
        {mlPoints.length > 0 && (
          <path
            d={buildSmoothPath([points[points.length - 1], ...mlPoints])}
            fill="none"
            stroke={catppuccin.peach}
            strokeWidth={1.5}
            strokeDasharray="4,4"
            opacity={0.6}
            className="security-chart__projection security-chart__projection--ml"
          />
        )}

        {/* Blended projection (green/red dashed - main prediction) */}
        {blendedPoints.length > 0 && (
          <path
            d={buildSmoothPath([points[points.length - 1], ...blendedPoints])}
            fill="none"
            stroke={expectedReturn >= 0 ? catppuccin.green : catppuccin.red}
            strokeWidth={1.5}
            strokeDasharray="4,4"
            className={`security-chart__projection security-chart__projection--blended ${expectedReturn >= 0 ? 'security-chart__projection--positive' : 'security-chart__projection--negative'}`}
          />
        )}

        {/* Current price dot */}
        <circle cx={lastPoint.x} cy={lastPoint.y} r={3} fill={catppuccin.text} className="security-chart__current-price-dot" />
      </svg>
    );
  };

  // Check if any projections are shown
  const hasProjections = prices && prices.length >= 2;

  return (
    <div ref={containerRef} style={{ width: '100%' }} className="security-chart">
      <div style={{ height }}>
        {renderChart()}
      </div>
      {hasProjections && (
        <div
          className="security-chart__legend"
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '12px',
            marginTop: '4px',
            fontSize: '10px',
            color: catppuccin.subtext0,
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <svg width="16" height="2">
              <line x1="0" y1="1" x2="16" y2="1" stroke={catppuccin.sapphire} strokeWidth="1.5" strokeDasharray="3,2" />
            </svg>
            Wavelet
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <svg width="16" height="2">
              <line x1="0" y1="1" x2="16" y2="1" stroke={catppuccin.peach} strokeWidth="1.5" strokeDasharray="3,2" />
            </svg>
            ML
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <svg width="16" height="2">
              <line x1="0" y1="1" x2="16" y2="1" stroke={catppuccin.green} strokeWidth="1.5" strokeDasharray="3,2" />
            </svg>
            Blended
          </span>
        </div>
      )}
    </div>
  );
}
