import { catppuccin } from '../theme';
import { buildSmoothPath } from '../utils/chartUtils';
import { normalizeWeights } from '../utils/mlWeights';
import { useResponsiveWidth } from '../hooks/useResponsiveWidth';

function computeCombined(row, normalizedWeights) {
  if (!normalizedWeights) return null;
  const components = {
    wavelet: row?.wavelet_ann_return,
    xgboost: row?.ml_xgboost,
    ridge: row?.ml_ridge,
    rf: row?.ml_rf,
    svr: row?.ml_svr,
  };

  let weighted = 0;
  let availableWeight = 0;
  Object.entries(components).forEach(([key, value]) => {
    if (value == null) return;
    const weight = Number(normalizedWeights[key] ?? 0);
    if (!Number.isFinite(weight) || weight <= 0) return;
    weighted += Number(value) * weight;
    availableWeight += weight;
  });
  if (availableWeight <= 0) return null;
  return weighted / availableWeight;
}

export function SecurityMLHistoryChart({ snapshots = [], weightsDraft = null, height = 190 }) {
  const [containerRef, width] = useResponsiveWidth(320);
  const normalized = normalizeWeights(weightsDraft);

  if (!snapshots || snapshots.length < 2) {
    return (
      <div ref={containerRef} style={{ width: '100%', height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: catppuccin.overlay1, fontSize: '0.8rem' }}>
        No historical ML data
      </div>
    );
  }

  const padding = { top: 14, right: 42, bottom: 26, left: 12 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  if (chartWidth <= 0 || chartHeight <= 0) {
    return <div ref={containerRef} style={{ width: '100%', height }} />;
  }

  const actual = snapshots.map((row) => (row.actual_ann_return != null ? Number(row.actual_ann_return) : null));
  const combined = snapshots.map((row) => computeCombined(row, normalized));

  const values = [0];
  actual.forEach((v) => v != null && values.push(v));
  combined.forEach((v) => v != null && values.push(v));
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const range = rawMax - rawMin || 1;
  const minY = rawMin - range * 0.1;
  const maxY = rawMax + range * 0.1;
  const yRange = maxY - minY || 1;

  const scaleX = (i) => padding.left + (i / (snapshots.length - 1)) * chartWidth;
  const scaleY = (v) => padding.top + chartHeight - ((v - minY) / yRange) * chartHeight;

  const actualPts = [];
  const combinedPts = [];
  snapshots.forEach((_, i) => {
    if (actual[i] != null) actualPts.push({ x: scaleX(i), y: scaleY(actual[i]) });
    if (combined[i] != null) combinedPts.push({ x: scaleX(i), y: scaleY(combined[i]) });
  });

  const actualPath = buildSmoothPath(actualPts);
  const combinedPath = buildSmoothPath(combinedPts);
  const zeroY = scaleY(0);

  return (
    <div ref={containerRef} style={{ width: '100%' }}>
      <div style={{ display: 'flex', gap: 10, fontSize: 10, color: catppuccin.subtext0, marginBottom: 3 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <svg width="12" height="2"><line x1="0" y1="1" x2="12" y2="1" stroke={catppuccin.green} strokeWidth="1.5" /></svg>
          Actual
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <svg width="12" height="2"><line x1="0" y1="1" x2="12" y2="1" stroke={catppuccin.lavender} strokeWidth="1.5" /></svg>
          Combined
        </span>
      </div>
      <svg width={width} height={height} style={{ display: 'block' }}>
        <line x1={padding.left} y1={zeroY} x2={width - padding.right} y2={zeroY} stroke={catppuccin.overlay0} strokeDasharray="3,3" opacity={0.45} />
        {actualPath && <path d={actualPath} fill="none" stroke={catppuccin.green} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" opacity={0.9} />}
        {combinedPath && <path d={combinedPath} fill="none" stroke={catppuccin.lavender} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" opacity={0.95} />}
      </svg>
    </div>
  );
}

