import { describe, expect, it } from 'vitest';
import { buildSmoothPath, buildUsefulYAxisDomain } from './chartUtils';

describe('buildSmoothPath', () => {
  it('returns an empty path for fewer than two points', () => {
    expect(buildSmoothPath([])).toBe('');
  });
});

describe('buildUsefulYAxisDomain', () => {
  it('keeps the domain close to the visible values', () => {
    const [min, max] = buildUsefulYAxisDomain([60, 75, 90], {
      paddingRatio: 0.04,
      minPadding: 1,
    });

    expect(min).toBeCloseTo(58.8);
    expect(max).toBeCloseTo(91.2);
  });

  it('uses a readable range for flat data', () => {
    const [min, max] = buildUsefulYAxisDomain([100, 100, 100], {
      paddingRatio: 0.04,
      minPadding: 1,
    });

    expect(min).toBeLessThan(100);
    expect(max).toBeGreaterThan(100);
  });
});
