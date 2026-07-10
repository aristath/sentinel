import { describe, expect, it } from 'vitest';
import { formatEur, formatPct } from './periodStats';

describe('period stat formatting', () => {
  it('preserves negative signs and zero values', () => {
    expect(formatEur(-1234)).toBe('-€1.2K');
    expect(formatEur(0)).toBe('+€0');
    expect(formatPct(0)).toBe('+0.0%');
    expect(formatPct(null)).toBe('—');
  });
});
