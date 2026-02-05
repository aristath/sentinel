/**
 * Portfolio P&L Chart Component
 *
 * SVG-based chart showing annualized return % with:
 * - Actual (green/red area fill): 14-day rolling TWR, annualized
 * - Wavelet (blue line): portfolio-weighted wavelet score as annualized return
 * - ML (peach line): portfolio-weighted ML score as annualized return
 * - Target (dashed line): horizontal at 11%
 */
import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

/**
 * Renders the portfolio annualized return chart
 *
 * @param {Object} props
 * @param {Array} props.snapshots - Array of snapshot objects with annualized return fields
 * @param {Object} props.summary - Summary with target_ann_return
 * @param {number} props.height - Chart height (default 160)
 */
export function PortfolioPnLChart({
  snapshots = [],
  summary = null,
  height = 160,
}) {
  const [containerRef, width] = useResponsiveWidth(300);

  const formatPct = (value) => {
    if (value == null) return '';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  const formatEur = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;
  };

  // Legend component
  const Legend = () => (
    <div
      style={{
        display: 'flex',
        gap: '12px',
        fontSize: '10px',
        color: catppuccin.subtext0,
        padding: '0 4px',
        marginBottom: '2px',
        flexWrap: 'wrap',
      }}
    >
      {[
        { color: catppuccin.green, label: 'Actual' },
        { color: catppuccin.blue, label: 'Wavelet' },
        { color: catppuccin.yellow, label: 'ML' },
        { color: catppuccin.overlay0, label: 'Target', dashed: true },
      ].map(({ color, label, dashed }) => (
        <span key={label} style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
          {dashed ? (
            <svg width="10" height="10">
              <line x1="0" y1="5" x2="10" y2="5" stroke={color} strokeWidth="1.5" strokeDasharray="2,2" />
            </svg>
          ) : (
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: color,
                display: 'inline-block',
              }}
            />
          )}
          {label}
        </span>
      ))}
    </div>
  );

  const renderChart = () => {
    if (!snapshots || snapshots.length < 2) {
      return (
        <div
          style={{
            width: '100%',
            height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: catppuccin.overlay1,
            fontSize: '0.875rem',
          }}
        >
          No data available
        </div>
      );
    }

    const padding = { top: 20, right: 60, bottom: 20, left: 10 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    if (chartWidth <= 0 || chartHeight <= 0) return null;

    const targetReturn = summary?.target_ann_return ?? 11.0;

    // Collect all non-null values across series for Y-axis scaling
    const allValues = [0, targetReturn];
    snapshots.forEach((s) => {
      if (s.actual_ann_return != null) allValues.push(s.actual_ann_return);
      if (s.wavelet_ann_return != null) allValues.push(s.wavelet_ann_return);
      if (s.ml_ann_return != null) allValues.push(s.ml_ann_return);
    });

    const rawMin = Math.min(...allValues);
    const rawMax = Math.max(...allValues);
    const range = rawMax - rawMin || 1;
    const paddedMin = rawMin - range * 0.1;
    const paddedMax = rawMax + range * 0.1;
    const valueRange = paddedMax - paddedMin;

    const scaleX = (i) => padding.left + (i / (snapshots.length - 1)) * chartWidth;
    const scaleY = (v) => padding.top + chartHeight - ((v - paddedMin) / valueRange) * chartHeight;

    const zeroY = scaleY(0);
    const targetY = scaleY(targetReturn);

    // Build actual return points with area fill (green/red split at zero)
    const actualPoints = [];
    snapshots.forEach((s, i) => {
      if (s.actual_ann_return != null) {
        actualPoints.push({ x: scaleX(i), y: scaleY(s.actual_ann_return), value: s.actual_ann_return });
      }
    });

    // Split actual points into positive/negative segments at zero crossings
    const segments = [];
    if (actualPoints.length >= 2) {
      let currentSegment = [actualPoints[0]];
      let currentIsPositive = actualPoints[0].value >= 0;

      for (let i = 1; i < actualPoints.length; i++) {
        const isPositive = actualPoints[i].value >= 0;
        if (isPositive !== currentIsPositive) {
          const prev = actualPoints[i - 1];
          const curr = actualPoints[i];
          const t = (0 - prev.value) / (curr.value - prev.value);
          const crossX = prev.x + t * (curr.x - prev.x);
          const crossPoint = { x: crossX, y: zeroY, value: 0 };

          currentSegment.push(crossPoint);
          segments.push({ points: currentSegment, isPositive: currentIsPositive });
          currentSegment = [crossPoint, actualPoints[i]];
          currentIsPositive = isPositive;
        } else {
          currentSegment.push(actualPoints[i]);
        }
      }
      segments.push({ points: currentSegment, isPositive: currentIsPositive });
    }

    // Build overlay line points (wavelet, ML) - skip nulls
    const waveletPoints = [];
    const mlPoints = [];
    snapshots.forEach((s, i) => {
      if (s.wavelet_ann_return != null) {
        waveletPoints.push({ x: scaleX(i), y: scaleY(s.wavelet_ann_return) });
      }
      if (s.ml_ann_return != null) {
        mlPoints.push({ x: scaleX(i), y: scaleY(s.ml_ann_return) });
      }
    });

    const waveletPath = buildSmoothPath(waveletPoints);
    const mlPath = buildSmoothPath(mlPoints);

    // Current actual value for the dot
    const lastActual = actualPoints.length > 0 ? actualPoints[actualPoints.length - 1] : null;

    return (
      <svg width={width} height={height} style={{ display: 'block' }}>
        <defs>
          <linearGradient id="ann-gradient-pos" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={catppuccin.green} stopOpacity={0.3} />
            <stop offset="100%" stopColor={catppuccin.green} stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="ann-gradient-neg" x1="0%" y1="100%" x2="0%" y2="0%">
            <stop offset="0%" stopColor={catppuccin.red} stopOpacity={0.3} />
            <stop offset="100%" stopColor={catppuccin.red} stopOpacity={0.05} />
          </linearGradient>
        </defs>

        {/* Zero line */}
        <line
          x1={padding.left}
          y1={zeroY}
          x2={width - padding.right}
          y2={zeroY}
          stroke={catppuccin.overlay0}
          strokeWidth={1}
          strokeDasharray="4,4"
          opacity={0.4}
        />
        <text x={width - padding.right + 5} y={zeroY + 4} fill={catppuccin.subtext0} fontSize="10">
          0%
        </text>

        {/* Target line */}
        <line
          x1={padding.left}
          y1={targetY}
          x2={width - padding.right}
          y2={targetY}
          stroke={catppuccin.overlay0}
          strokeWidth={1}
          strokeDasharray="4,4"
          opacity={0.6}
        />
        <text x={width - padding.right + 5} y={targetY + 4} fill={catppuccin.subtext0} fontSize="10">
          {formatPct(targetReturn)}
        </text>

        {/* Actual: area fills */}
        {segments.map((seg, idx) => {
          const segPath = buildSmoothPath(seg.points);
          if (!segPath || seg.points.length < 2) return null;
          const firstX = seg.points[0].x;
          const lastX = seg.points[seg.points.length - 1].x;
          const areaPath = `${segPath} L ${lastX},${zeroY} L ${firstX},${zeroY} Z`;
          return (
            <path
              key={`area-${idx}`}
              d={areaPath}
              fill={`url(#ann-gradient-${seg.isPositive ? 'pos' : 'neg'})`}
            />
          );
        })}

        {/* Actual: stroke lines */}
        {segments.map((seg, idx) => {
          const segPath = buildSmoothPath(seg.points);
          if (!segPath) return null;
          return (
            <path
              key={`line-${idx}`}
              d={segPath}
              fill="none"
              stroke={seg.isPositive ? catppuccin.green : catppuccin.red}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          );
        })}

        {/* Wavelet line */}
        {waveletPath && (
          <path
            d={waveletPath}
            fill="none"
            stroke={catppuccin.blue}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.8}
          />
        )}

        {/* ML line */}
        {mlPath && (
          <path
            d={mlPath}
            fill="none"
            stroke={catppuccin.yellow}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.8}
          />
        )}

        {/* Current value dot */}
        {lastActual && (
          <circle
            cx={lastActual.x}
            cy={lastActual.y}
            r={4}
            fill={lastActual.value >= 0 ? catppuccin.green : catppuccin.red}
            stroke={catppuccin.base}
            strokeWidth={2}
          />
        )}

        {/* Y-axis min/max labels */}
        <text x={width - padding.right + 5} y={padding.top + 10} fill={catppuccin.subtext0} fontSize="10">
          {formatPct(rawMax)}
        </text>
        <text x={width - padding.right + 5} y={height - padding.bottom} fill={catppuccin.subtext0} fontSize="10">
          {formatPct(rawMin)}
        </text>
      </svg>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%' }} className="portfolio-pnl-chart">
      <Legend />
      <div style={{ height }}>
        {renderChart()}
      </div>
      {summary && snapshots && snapshots.length >= 2 && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '4px',
            padding: '0 4px',
            fontSize: '11px',
            color: catppuccin.subtext0,
          }}
        >
          <span>
            Value: <span style={{ color: catppuccin.text }}>{formatEur(summary.end_value).replace('+', '')}</span>
          </span>
          <span>
            P&L:{' '}
            <span style={{ color: summary.pnl_absolute >= 0 ? catppuccin.green : catppuccin.red }}>
              {formatEur(summary.pnl_absolute)}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
