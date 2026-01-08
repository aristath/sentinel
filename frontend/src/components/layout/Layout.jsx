import { Container } from '@mantine/core';
import { Outlet } from 'react-router-dom';
import { AppHeader } from './AppHeader';
import { StatusBar } from './StatusBar';
import { TabNavigation } from './TabNavigation';
import { MarketStatus } from './MarketStatus';
import { JobFooter } from './JobFooter';
import { AddSecurityModal } from '../modals/AddSecurityModal';
import { EditSecurityModal } from '../modals/EditSecurityModal';
import { SecurityChartModal } from '../modals/SecurityChartModal';
import { SettingsModal } from '../modals/SettingsModal';
import { PlannerManagementModal } from '../modals/PlannerManagementModal';
import { useEffect, useRef } from 'react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { useTradesStore } from '../../stores/tradesStore';
import { useLogsStore } from '../../stores/logsStore';
import { useNotifications } from '../../hooks/useNotifications';
import { ColorSchemeToggle } from './ColorSchemeToggle';

export function Layout() {
  // Display notifications from app store
  useNotifications();
  const { fetchAll, startEventStream, stopEventStream } = useAppStore();
  const { fetchAllocation, fetchCashBreakdown, fetchTargets } = usePortfolioStore();
  const { fetchSecurities, fetchSparklines } = useSecuritiesStore();
  const { fetchSettings } = useSettingsStore();
  const { fetchTrades } = useTradesStore();
  const { fetchAvailableLogFiles, selectedLogFile } = useLogsStore();

  // Load initial data once on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        await Promise.all([
          fetchAll(),
          fetchAllocation(),
          fetchCashBreakdown(),
          fetchSecurities(),
          fetchTargets(),
          fetchSparklines(),
          fetchSettings(),
          fetchTrades(),
          fetchAvailableLogFiles(),
        ]);
      } catch (error) {
        console.error('Failed to load initial data:', error);
        // Individual store methods already handle their own errors
        // This catch prevents unhandled promise rejection
      }
    };

    loadData();
  }, [fetchAll, fetchAllocation, fetchCashBreakdown, fetchSecurities, fetchTargets, fetchSparklines, fetchSettings, fetchTrades, fetchAvailableLogFiles]);

  // Manage event stream lifecycle - restart when selectedLogFile changes
  useEffect(() => {
    startEventStream(selectedLogFile);

    return () => {
      stopEventStream();
    };
  }, [selectedLogFile, startEventStream, stopEventStream]);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--mantine-color-dark-9)' }}>
      <Container size="xl" py="md">
        <AppHeader />
        <MarketStatus />
        <StatusBar />
        <TabNavigation />
        <div style={{ marginTop: '16px' }}>
          <Outlet />
        </div>
        <JobFooter />
      </Container>

      {/* Modals */}
      <AddSecurityModal />
      <EditSecurityModal />
      <SecurityChartModal />
      <SettingsModal />
      <PlannerManagementModal />

      {/* Color Scheme Toggle */}
      <ColorSchemeToggle />
    </div>
  );
}
