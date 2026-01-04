import { Container } from '@mantine/core';
import { Outlet } from 'react-router-dom';
import { AppHeader } from './AppHeader';
import { StatusBar } from './StatusBar';
import { TabNavigation } from './TabNavigation';
import { useEffect } from 'react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useSettingsStore } from '../../stores/settingsStore';

export function Layout() {
  const { fetchAll, startPlannerStatusStream, startRecommendationStream } = useAppStore();
  const { fetchAllocation, fetchCashBreakdown, fetchBuckets, fetchTargets } = usePortfolioStore();
  const { fetchSecurities, fetchSparklines } = useSecuritiesStore();
  const { fetchSettings } = useSettingsStore();

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
  }, []);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--mantine-color-dark-8)' }}>
      <Container size="xl" py="md">
        <AppHeader />
        <StatusBar />
        <TabNavigation />
        <div style={{ marginTop: '16px' }}>
          <Outlet />
        </div>
      </Container>
    </div>
  );
}
