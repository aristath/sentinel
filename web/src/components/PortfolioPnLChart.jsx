/**
 * Portfolio P&L Chart Component
 *
 * SVG-based area chart showing portfolio P&L percentage over time.
 * Green fill for positive P&L, red fill for negative P&L.
 * Includes a dashed zero line and summary badge.
 */
import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

/**
 * Renders a portfolio P&L area chart with gradient fill
 *
 * @param {Object} props
 * @param {Array} props.snapshots - Array of {date, pnl_eur, pnl_pct} objects
 * @param {Object} props.summary - {start_value, end_value, pnl_absolute, pnl_percent}
 * @param {number} props.height - Chart height (default 160)
 * @param {string} props.period - Current period selection
 */
export function PortfolioPnLChart({
  snapshots = [],
  summary = null,
  height = 160,
}) {
  const [containerRef, width] = useResponsiveWidth(300);

  // Format currency for display
  const formatEur = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toLocaleString('en-US', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })}`;
  };

  const formatPct = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  // Render chart
  const renderChart = () => {
    // Not enough data
    if (!snapshots || snapshots.length < 2) {
      return (
        <div
          className="portfolio-pnl-chart__empty"
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
          No P&L data available
        </div>
      );
    }

    const padding = { top: 20, right: 60, bottom: 20, left: 10 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    if (chartWidth <= 0 || chartHeight <= 0) return null;

    // Extract P&L percentages
    const values = snapshots.map((s) => s.pnl_pct);
    const minValue = Math.min(...values, 0);
    const maxValue = Math.max(...values, 0);

    // Add some padding to the range
    const range = maxValue - minValue || 1;
    const paddedMin = minValue - range * 0.1;
    const paddedMax = maxValue + range * 0.1;
    const valueRange = paddedMax - paddedMin;

    // Scale functions
    const scaleX = (i) => padding.left + (i / (values.length - 1)) * chartWidth;
    const scaleY = (v) => padding.top + chartHeight - ((v - paddedMin) / valueRange) * chartHeight;

    // Zero line Y position
    const zeroY = scaleY(0);

    // Build points for the line
    const points = values.map((v, i) => ({
      x: scaleX(i),
      y: scaleY(v),
      value: v,
    }));

    // Build area path (line + close to bottom + back to start)
    const buildAreaPath = (pts) => {
      const linePath = buildSmoothPath(pts);
      if (!linePath) return '';

      const firstX = pts[0].x;
      const lastX = pts[pts.length - 1].x;

      // Close the path: go down to zero line, across, and up
      return `${linePath} L ${lastX},${zeroY} L ${firstX},${zeroY} Z`;
    };

    // Split points into segments based on positive/negative
    const segments = [];
    let currentSegment = [points[0]];
    let currentIsPositive = points[0].value >= 0;

    for (let i = 1; i < points.length; i++) {
      const isPositive = points[i].value >= 0;

      if (isPositive !== currentIsPositive) {
        // Find zero crossing point (linear interpolation)
        const prev = points[i - 1];
        const curr = points[i];
        const t = (0 - prev.value) / (curr.value - prev.value);
        const crossX = prev.x + t * (curr.x - prev.x);
        const crossPoint = { x: crossX, y: zeroY, value: 0 };

        // End current segment at crossing
        currentSegment.push(crossPoint);
        segments.push({ points: currentSegment, isPositive: currentIsPositive });

        // Start new segment from crossing
        currentSegment = [crossPoint, points[i]];
        currentIsPositive = isPositive;
      } else {
        currentSegment.push(points[i]);
      }
    }
    segments.push({ points: currentSegment, isPositive: currentIsPositive });

    const lastPoint = points[points.length - 1];
    const lastIsPositive = lastPoint.value >= 0;

    return (
      <svg width={width} height={height} style={{ display: 'block' }} className="portfolio-pnl-chart__svg">
        {/* Gradient definitions */}
        <defs>
          <linearGradient id="pnl-gradient-pos" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={catppuccin.green} stopOpacity={0.3} />
            <stop offset="100%" stopColor={catppuccin.green} stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="pnl-gradient-neg" x1="0%" y1="100%" x2="0%" y2="0%">
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
          opacity={0.6}
          className="portfolio-pnl-chart__zero-line"
        />

        {/* Zero label */}
        <text
          x={width - padding.right + 5}
          y={zeroY + 4}
          fill={catppuccin.subtext0}
          fontSize="10"
          className="portfolio-pnl-chart__zero-label"
        >
          0%
        </text>

        {/* Area fills for each segment */}
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
              fill={`url(#pnl-gradient-${seg.isPositive ? 'pos' : 'neg'})`}
              className="portfolio-pnl-chart__area"
            />
          );
        })}

        {/* Lines for each segment */}
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
              className="portfolio-pnl-chart__line"
            />
          );
        })}

        {/* Current value dot */}
        <circle
          cx={lastPoint.x}
          cy={lastPoint.y}
          r={4}
          fill={lastIsPositive ? catppuccin.green : catppuccin.red}
          stroke={catppuccin.base}
          strokeWidth={2}
          className="portfolio-pnl-chart__current-dot"
        />

        {/* Summary badge */}
        {summary && (
          <g className="portfolio-pnl-chart__summary">
            <rect
              x={width - padding.right - 85}
              y={padding.top - 15}
              width={80}
              height={24}
              rx={4}
              fill={catppuccin.surface0}
              opacity={0.9}
            />
            <text
              x={width - padding.right - 45}
              y={padding.top + 2}
              fill={lastIsPositive ? catppuccin.green : catppuccin.red}
              fontSize="11"
              fontWeight="600"
              textAnchor="middle"
              className="portfolio-pnl-chart__summary-text"
            >
              {formatPct(summary.pnl_percent)}
            </text>
          </g>
        )}

        {/* Y-axis labels */}
        <text
          x={width - padding.right + 5}
          y={padding.top + 10}
          fill={catppuccin.subtext0}
          fontSize="10"
          className="portfolio-pnl-chart__max-label"
        >
          {formatPct(maxValue)}
        </text>
        <text
          x={width - padding.right + 5}
          y={height - padding.bottom}
          fill={catppuccin.subtext0}
          fontSize="10"
          className="portfolio-pnl-chart__min-label"
        >
          {formatPct(minValue)}
        </text>
      </svg>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%' }} className="portfolio-pnl-chart">
      <div style={{ height }}>
        {renderChart()}
      </div>
      {/* Bottom summary line */}
      {summary && snapshots && snapshots.length >= 2 && (
        <div
          className="portfolio-pnl-chart__footer"
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
            P&L: <span style={{ color: summary.pnl_absolute >= 0 ? catppuccin.green : catppuccin.red }}>
              {formatEur(summary.pnl_absolute)}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
