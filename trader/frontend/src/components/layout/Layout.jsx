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
import { UniverseManagementModal } from '../modals/UniverseManagementModal';
import { BucketHealthModal } from '../modals/BucketHealthModal';
import { PlannerManagementModal } from '../modals/PlannerManagementModal';
import { useEffect } from 'react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useSettingsStore } from '../../stores/settingsStore';
import { useTradesStore } from '../../stores/tradesStore';
import { useLogsStore } from '../../stores/logsStore';
import { useNotifications } from '../../hooks/useNotifications';

export function Layout() {
  // Display notifications from app store
  useNotifications();
  const { fetchAll, startPlannerStatusStream, startRecommendationStream } = useAppStore();
  const { fetchAllocation, fetchCashBreakdown, fetchBuckets, fetchTargets } = usePortfolioStore();
  const { fetchSecurities, fetchSparklines } = useSecuritiesStore();
  const { fetchSettings } = useSettingsStore();
  const { fetchTrades } = useTradesStore();
  const { fetchAvailableLogFiles } = useLogsStore();

  useEffect(() => {
    // Fetch all initial data
    const loadData = async () => {
      await Promise.all([
        fetchAll(),
        fetchAllocation(),
        fetchCashBreakdown(),
        fetchSecurities(),
        fetchBuckets(),
        fetchTargets(),
        fetchSparklines(),
        fetchSettings(),
        fetchTrades(),
        fetchAvailableLogFiles(),
      ]);
    };

    loadData();

    // Start SSE streams
    startPlannerStatusStream();
    startRecommendationStream();

    // Cleanup on unmount
    return () => {
      // SSE cleanup is handled in the store
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--mantine-color-dark-8)' }}>
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
      <UniverseManagementModal />
      <BucketHealthModal />
      <PlannerManagementModal />
    </div>
  );
}
