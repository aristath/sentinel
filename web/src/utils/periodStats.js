export function formatPct(value) {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
}

export function formatEur(value) {
  if (value == null || Number.isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '-';
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000) return `${sign}€${(absolute / 1_000_000).toFixed(1)}M`;
  if (absolute >= 1_000) return `${sign}€${(absolute / 1_000).toFixed(1)}K`;
  return `${sign}€${absolute.toFixed(0)}`;
}
