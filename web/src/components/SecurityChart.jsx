import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

export function SecurityChart({
  prices = [],
  avgCost = 0,
  hasPosition = false,
  forecastPoints = [],
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

    const values = prices.map((p) => Number(p.close)).filter((value) => Number.isFinite(value) && value > 0);
    if (values.length < 2) {
      return (
        <div style={{ width: '100%', height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: catppuccin.overlay1, fontSize: '0.875rem' }}>
          No price data
        </div>
      );
    }

    const anchorPrice = values[values.length - 1];
    const projection = buildForecastProjection(forecastPoints, anchorPrice);
    const projectedValues = projection.flatMap((point) => [point.low, point.median, point.high]);
    const scaleValues = [...values, ...projectedValues];
    if (avgCost > 0) {
      scaleValues.push(avgCost);
    }
    const minValue = Math.min(...scaleValues);
    const maxValue = Math.max(...scaleValues);
    const valueRange = maxValue - minValue || 1;
    const forecastSteps = Math.max(0, projection.length - 1);
    const totalSlots = values.length + forecastSteps;

    const scaleX = (i) => padding.left + (i / Math.max(totalSlots - 1, 1)) * chartWidth;
    const scaleY = (v) => padding.top + chartHeight - ((v - minValue) / valueRange) * chartHeight;

    const points = values.map((v, i) => ({ x: scaleX(i), y: scaleY(v), value: v }));
    const projectionPoints = projection.map((point, index) => ({
      x: scaleX(values.length - 1 + index),
      lowY: scaleY(point.low),
      medianY: scaleY(point.median),
      highY: scaleY(point.high),
    }));
    const forecastBandPath = buildBandPath(projectionPoints);
    const forecastMedianPath = buildSmoothPath(
      projectionPoints.map((point) => ({ x: point.x, y: point.medianY }))
    );

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
        <title>Price history with forecast projection</title>
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

        {forecastBandPath && (
          <path
            d={forecastBandPath}
            fill={catppuccin.lavender}
            opacity={0.16}
          />
        )}

        {segments.map((seg, idx) => (
          <path key={idx} d={buildSmoothPath(seg.points)} fill="none" stroke={seg.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        ))}

        {forecastMedianPath && (
          <path
            d={forecastMedianPath}
            fill="none"
            stroke={catppuccin.lavender}
            strokeWidth={2}
            strokeDasharray="4,3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        <circle cx={lastPoint.x} cy={lastPoint.y} r={3} fill={catppuccin.text} />
        {projectionPoints.length > 1 && (
          <circle
            cx={projectionPoints[projectionPoints.length - 1].x}
            cy={projectionPoints[projectionPoints.length - 1].medianY}
            r={2.5}
            fill={catppuccin.lavender}
          />
        )}
      </svg>
    );
  };

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <div style={{ height }}>{renderChart()}</div>
    </div>
  );
}

function buildForecastProjection(forecastPoints, anchorPrice) {
  if (!Array.isArray(forecastPoints) || forecastPoints.length === 0 || !Number.isFinite(anchorPrice) || anchorPrice <= 0) {
    return [];
  }

  const projection = forecastPoints
    .map((point) => {
      const lowReturn = Number(point.cumulative_q10);
      const medianReturn = Number(point.cumulative_q50);
      const highReturn = Number(point.cumulative_q90);
      if (!Number.isFinite(lowReturn) || !Number.isFinite(medianReturn) || !Number.isFinite(highReturn)) {
        return null;
      }
      const low = anchorPrice * (1 + Math.min(lowReturn, highReturn));
      const high = anchorPrice * (1 + Math.max(lowReturn, highReturn));
      return {
        low,
        median: anchorPrice * (1 + medianReturn),
        high,
      };
    })
    .filter(Boolean);

  if (projection.length === 0) {
    return [];
  }

  return [
    { low: anchorPrice, median: anchorPrice, high: anchorPrice },
    ...projection,
  ];
}

function buildBandPath(points) {
  if (!Array.isArray(points) || points.length < 2) {
    return null;
  }
  const upper = points.map((point) => `${point.x},${point.highY}`).join(' L ');
  const lower = [...points].reverse().map((point) => `${point.x},${point.lowY}`).join(' L ');
  return `M ${upper} L ${lower} Z`;
}
