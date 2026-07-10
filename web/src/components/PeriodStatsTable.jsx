import { catppuccin } from '../theme';
import { formatEur, formatPct } from '../utils/periodStats';
import './PeriodStatsTable.css';

const PERIODS = ['1D', '1W', '1M', '3M', '6M', '1Y', 'YTD', 'All'];

function valueColor(value) {
  if (value == null) return catppuccin.overlay1;
  if (value > 0) return catppuccin.green;
  if (value < 0) return catppuccin.red;
  return catppuccin.text;
}

export function PeriodStatsTable({ stats }) {
  if (!stats) return null;

  return (
    <div className="period-stats-scroll">
      <table className="period-stats-table">
        <caption>Portfolio performance by period</caption>
        <thead>
          <tr>
            <th scope="col">Period</th>
            <th scope="col">P/L</th>
            <th scope="col">Return</th>
            <th scope="col">Benchmark</th>
            <th scope="col">Alpha</th>
          </tr>
        </thead>
        <tbody>
          {PERIODS.map((period) => {
            const row = stats[period] || {};
            return (
              <tr key={period}>
                <th scope="row">{period}</th>
                <td style={{ color: valueColor(row.portfolio_eur) }}>{formatEur(row.portfolio_eur)}</td>
                <td style={{ color: valueColor(row.portfolio_pct) }}>{formatPct(row.portfolio_pct)}</td>
                <td style={{ color: row.benchmark_pct == null ? catppuccin.overlay1 : catppuccin.blue }}>
                  {formatPct(row.benchmark_pct)}
                </td>
                <td style={{ color: valueColor(row.alpha_pct) }}>{formatPct(row.alpha_pct)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default PeriodStatsTable;
