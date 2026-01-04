import { useEffect, useRef } from 'react';
import { useSecuritiesStore } from '../../stores/securitiesStore';

/**
 * Security Sparkline Component
 * Custom SVG-based sparkline chart for security table
 */
export function SecuritySparkline({ symbol, hasPosition = false }) {
  const containerRef = useRef(null);
  const { sparklines } = useSecuritiesStore();

  useEffect(() => {
    if (!containerRef.current || !symbol) return;

    const data = sparklines[symbol];
    if (!data || data.length < 2) {
      containerRef.current.innerHTML = '<span style="color: var(--mantine-color-dark-4); font-size: 12px;">-</span>';
      return;
    }

    const width = 80;
    const height = 32;
    const padding = 1;

    // Extract values and find min/max
    const values = data.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    // Calculate scaling factors
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Build SVG path
    const points = values.map((value, index) => {
      const x = padding + (index / (values.length - 1)) * chartWidth;
      const y = padding + chartHeight - ((value - minValue) / valueRange) * chartHeight;
      return `${x},${y}`;
    });

    const pathData = `M ${points.join(' L ')}`;

    // Determine color based on trend and position
    const firstValue = values[0];
    const lastValue = values[values.length - 1];
    const isPositive = lastValue > firstValue;
    const color = hasPosition
      ? (isPositive ? 'rgba(34, 197, 94, 0.8)' : 'rgba(239, 68, 68, 0.8)')
      : (isPositive ? 'rgba(59, 130, 246, 0.6)' : 'rgba(107, 114, 128, 0.6)');

    containerRef.current.innerHTML = `
      <svg width="${width}" height="${height}" style="display: block;">
        <path
          d="${pathData}"
          fill="none"
          stroke="${color}"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    `;
  }, [symbol, hasPosition, sparklines]);

  if (!symbol) {
    return <span style={{ color: 'var(--mantine-color-dark-4)', fontSize: '12px' }}>-</span>;
  }

  return <div ref={containerRef} style={{ display: 'inline-block' }} />;
}

