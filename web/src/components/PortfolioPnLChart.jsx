import { useState } from 'react';
import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

const SMOOTH_WINDOWS = { '1D': 1, '1W': 7, '2W': 14 };
const SMOOTH_OPTIONS = ['1D', '1W', '2W'];

function smoothSeries(values, windowSize) {
  if (windowSize <= 1) return values;
  return values.map((_, i) => {
    const start = Math.max(0, i - windowSize + 1);
    let sum = 0;
    let count = 0;
    for (let j = start; j <= i; j += 1) {
      const value = values[j];
      if (value == null || Number.isNaN(value)) continue;
      sum += value;
      count += 1;
    }
    return count > 0 ? sum / count : null;
  });
}

export function PortfolioPnLChart({ snapshots = [], summary = null, height = 300 }) {
  const [containerRef, width] = useResponsiveWidth(300);
  const [showActual, setShowActual] = useState(true);
  const [showTarget, setShowTarget] = useState(false);
  const [smoothWindow, setSmoothWindow] = useState('1D');

  const formatPct = (value) => {
    if (value == null) return '';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  const Legend = () => (
    <div style={{ display: 'flex', gap: '12px', fontSize: '10px', color: catppuccin.subtext0, padding: '0 4px', marginBottom: '2px', flexWrap: 'wrap' }}>
      <span
        onClick={() => setShowActual((prev) => !prev)}
        style={{ display: 'flex', alignItems: 'center', gap: '3px', cursor: 'pointer', opacity: showActual ? 1 : 0.35, userSelect: 'none' }}
      >
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: catppuccin.green, display: 'inline-block' }} />
        Actual
      </span>

      <span
        onClick={() => setShowTarget((prev) => !prev)}
        style={{ display: 'flex', alignItems: 'center', gap: '3px', cursor: 'pointer', opacity: showTarget ? 1 : 0.35, userSelect: 'none' }}
      >
        <svg width="10" height="10">
          <line x1="0" y1="5" x2="10" y2="5" stroke={catppuccin.overlay0} strokeWidth="1.5" strokeDasharray="2,2" />
        </svg>
        Target
      </span>

      <span style={{ opacity: 0.8 }}>Smooth:</span>
      {SMOOTH_OPTIONS.map((option) => (
        <span
          key={option}
          onClick={() => setSmoothWindow(option)}
          style={{ cursor: 'pointer', opacity: smoothWindow === option ? 1 : 0.5, userSelect: 'none' }}
        >
          {option}
        </span>
      ))}
    </div>
  );

  if (!snapshots || snapshots.length < 2) {
    return (
      <div ref={containerRef} style={{ width: '100%', height }}>
        <Legend />
        <div style={{ color: catppuccin.overlay1, fontSize: '12px', textAlign: 'center', paddingTop: '40px' }}>
          Not enough data yet
        </div>
      </div>
    );
  }

  const padding = { top: 24, right: 46, bottom: 22, left: 10 };
  const chartWidth = Math.max(0, width - padding.left - padding.right);
  const chartHeight = Math.max(0, height - padding.top - padding.bottom);

  const actualSeriesRaw = snapshots.map((s) => (s.actual_ann_return != null ? Number(s.actual_ann_return) : null));
  const actualSeries = smoothSeries(actualSeriesRaw, SMOOTH_WINDOWS[smoothWindow]);

  const values = actualSeries.filter((v) => v != null);
  const minVal = values.length ? Math.min(...values, 0) : -10;
  const maxVal = values.length ? Math.max(...values, 10) : 10;
  const range = Math.max(1, maxVal - minVal);
  const pad = range * 0.2;
  const yMin = minVal - pad;
  const yMax = maxVal + pad;

  const scaleX = (idx) => padding.left + (idx / (snapshots.length - 1)) * chartWidth;
  const scaleY = (v) => padding.top + chartHeight - ((v - yMin) / (yMax - yMin)) * chartHeight;

  const actualPoints = [];
  for (let i = 0; i < snapshots.length; i += 1) {
    const value = actualSeries[i];
    if (value != null) actualPoints.push({ x: scaleX(i), y: scaleY(value) });
  }
  const actualPath = showActual ? buildSmoothPath(actualPoints) : null;

  const target = summary?.target_ann_return;
  const targetY = target != null ? scaleY(Number(target)) : null;

  const last = [...actualSeries].reverse().find((v) => v != null);

  return (
    <div ref={containerRef} style={{ width: '100%', height }}>
      <Legend />
      <svg width={width} height={height}>
        {[0.25, 0.5, 0.75].map((ratio) => {
          const y = padding.top + ratio * chartHeight;
          return <line key={ratio} x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke={catppuccin.surface2} strokeWidth="1" opacity="0.5" />;
        })}

        {targetY != null && showTarget && (
          <line x1={padding.left} y1={targetY} x2={width - padding.right} y2={targetY} stroke={catppuccin.overlay0} strokeWidth="1.5" strokeDasharray="4,3" opacity="0.8" />
        )}

        {actualPath && <path d={actualPath} fill="none" stroke={catppuccin.green} strokeWidth="2" opacity="0.95" />}

        {last != null && (
          <text x={width - padding.right + 4} y={scaleY(last)} fontSize="10" fill={catppuccin.green} dominantBaseline="middle">
            {formatPct(last)}
          </text>
        )}
      </svg>
    </div>
  );
}

export default PortfolioPnLChart;
