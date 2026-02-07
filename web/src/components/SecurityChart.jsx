import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

export function SecurityChart({
  prices = [],
  avgCost = 0,
  hasPosition = false,
  height = 120,
}) {
  const [containerRef, width] = useResponsiveWidth(300);

  const renderChart = () => {
    if (!prices || prices.length < 2) {
      return (
        <div style={{ width: '100%', height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: catppuccin.overlay1, fontSize: '0.875rem' }}>
          No price data
        </div>
      );
    }

    const padding = { top: 10, right: 10, bottom: 10, left: 10 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    if (chartWidth <= 0 || chartHeight <= 0) return null;

    const values = prices.map((p) => p.close);
    const minValue = Math.min(...values, avgCost || Infinity);
    const maxValue = Math.max(...values, avgCost || -Infinity);
    const valueRange = maxValue - minValue || 1;

    const scaleX = (i, total) => padding.left + (i / Math.max(total - 1, 1)) * chartWidth;
    const scaleY = (v) => padding.top + chartHeight - ((v - minValue) / valueRange) * chartHeight;
    const totalPoints = values.length;

    const points = values.map((v, i) => ({ x: scaleX(i, totalPoints), y: scaleY(v), value: v }));

    let segments = [];
    if (hasPosition && avgCost > 0) {
      let currentSegment = [points[0]];
      let currentColor = points[0].value >= avgCost ? catppuccin.green : catppuccin.red;
      for (let i = 1; i < points.length; i += 1) {
        const color = points[i].value >= avgCost ? catppuccin.green : catppuccin.red;
        if (color !== currentColor) {
          segments.push({ points: [...currentSegment], color: currentColor });
          currentSegment = [points[i - 1], points[i]];
          currentColor = color;
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
      <svg width={width} height={height} style={{ display: 'block' }}>
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
          />
        )}

        {segments.map((seg, idx) => (
          <path key={idx} d={buildSmoothPath(seg.points)} fill="none" stroke={seg.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        ))}

        <circle cx={lastPoint.x} cy={lastPoint.y} r={3} fill={catppuccin.text} />
      </svg>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <div style={{ height }}>{renderChart()}</div>
    </div>
  );
}
