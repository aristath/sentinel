import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PeriodStatsTable } from './PeriodStatsTable';

describe('PeriodStatsTable', () => {
  it('renders all requested periods in a semantic table', () => {
    render(
      <PeriodStatsTable
        stats={{
          '1D': { portfolio_eur: -1234, portfolio_pct: -2, benchmark_pct: 1, alpha_pct: -3 },
          '1W': { portfolio_eur: 0, portfolio_pct: 0, benchmark_pct: 0, alpha_pct: 0 },
          All: { portfolio_eur: 250, portfolio_pct: 25, benchmark_pct: null, alpha_pct: null },
        }}
      />,
    );

    const table = screen.getByRole('table', { name: 'Portfolio performance by period' });
    expect(within(table).getAllByRole('columnheader')).toHaveLength(5);
    expect(within(table).getAllByRole('rowheader')).toHaveLength(8);
    expect(screen.getByText('1D')).toBeInTheDocument();
    expect(screen.getByText('1W')).toBeInTheDocument();
    expect(screen.getByText('-€1.2K')).toBeInTheDocument();
    expect(screen.getByText('+€250')).toBeInTheDocument();
    expect(screen.getByText('+25.0%')).toBeInTheDocument();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});
