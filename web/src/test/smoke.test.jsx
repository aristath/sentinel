import { render } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { DatesProvider } from '@mantine/dates';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { theme, colorScheme } from '../theme';
import App from '../App';
import { BacktestModal } from '../components/BacktestModal';
import { TradesModal } from '../components/TradesModal';
import { SchedulerModal } from '../components/SchedulerModal';
import { SecurityExpandedRow } from '../components/SecurityExpandedRow';
import { SettingsModal } from '../components/SettingsModal';

const wrap = (ui) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MantineProvider theme={theme} defaultColorScheme={colorScheme} forceColorScheme={colorScheme}>
      <Notifications />
      <DatesProvider settings={{ firstDayOfWeek: 1 }}>
        <MemoryRouter>{ui}</MemoryRouter>
      </DatesProvider>
    </MantineProvider>
  </QueryClientProvider>
);

describe('upgrade smoke test', () => {
  it('mounts App without crashing', () => {
    render(wrap(<App />));
  });

  it('renders BacktestModal (DatePickerInput with string values)', () => {
    render(wrap(<BacktestModal opened onClose={() => {}} />));
  });

  it('renders TradesModal (Pagination + DatePickerInput)', () => {
    render(wrap(<TradesModal opened onClose={() => {}} />));
  });

  it('renders SchedulerModal (Table.* subcomponents)', () => {
    render(wrap(<SchedulerModal opened onClose={() => {}} />));
  });

  it('renders SettingsModal (Divider + freedom24 fields)', () => {
    render(wrap(<SettingsModal opened onClose={() => {}} />));
  });

  it('renders SecurityExpandedRow (Grid gap, Grid.Col responsive span)', () => {
    const security = {
      symbol: 'AAPL.US',
      name: 'Apple Inc.',
      category: 'tech',
      country: 'US',
      enabled: true,
      target_pct: 5,
      current_pct: 4.5,
      score: 0.5,
      last_price: 200,
      lots: [],
    };
    render(wrap(<SecurityExpandedRow security={security} />));
  });
});
