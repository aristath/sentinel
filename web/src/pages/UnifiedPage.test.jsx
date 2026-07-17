import { describe, expect, it } from 'vitest';
import { hasDisabledTradePermission, shouldShowSecurityForFilter } from './UnifiedPage';

const quietSecurity = {
  symbol: 'AAPL.US',
  allow_buy: 1,
  allow_sell: 1,
  current_allocation: 0,
  ideal_allocation: 0,
  has_position: false,
  recommendation: null,
  price_warning: null,
};

describe('UnifiedPage filters', () => {
  it('keeps disabled trade permissions visible in the Review filter', () => {
    expect(shouldShowSecurityForFilter(quietSecurity, 'review')).toBe(false);
    expect(shouldShowSecurityForFilter({ ...quietSecurity, allow_buy: 0 }, 'review')).toBe(true);
    expect(shouldShowSecurityForFilter({ ...quietSecurity, allow_buy: false }, 'review')).toBe(true);
    expect(shouldShowSecurityForFilter({ ...quietSecurity, allow_sell: 0 }, 'review')).toBe(true);
  });

  it('detects missing permission fields as enabled defaults', () => {
    expect(hasDisabledTradePermission({})).toBe(false);
    expect(hasDisabledTradePermission({ allow_buy: '0' })).toBe(true);
    expect(hasDisabledTradePermission({ allow_sell: false })).toBe(true);
  });
});
