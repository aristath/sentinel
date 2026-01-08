import { Tabs, Badge, Group } from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../stores/appStore';
import { useEffect, useCallback } from 'react';

export function TabNavigation() {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, setActiveTab } = useAppStore();

  // Map route paths to tab values
  const getTabFromPath = (path) => {
    if (path === '/' || path === '/next-actions') return 'next-actions';
    if (path === '/diversification') return 'diversification';
    if (path === '/security-universe') return 'security-universe';
    if (path === '/recent-trades') return 'recent-trades';
    if (path === '/logs') return 'logs';
    return 'next-actions';
  };

  const activeTab = getTabFromPath(location.pathname);

  const handleTabChange = useCallback((value) => {
    setActiveTab(value);
    const routes = {
      'next-actions': '/',
      'diversification': '/diversification',
      'security-universe': '/security-universe',
      'recent-trades': '/recent-trades',
      'logs': '/logs',
    };
    navigate(routes[value] || '/');
  }, [navigate, setActiveTab]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeydown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;

      const shortcuts = {
        '1': 'next-actions',
        '2': 'diversification',
        '3': 'security-universe',
        '4': 'recent-trades',
        '5': 'logs',
      };

      if (shortcuts[e.key]) {
        e.preventDefault();
        handleTabChange(shortcuts[e.key]);
      }
    };

    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [handleTabChange]);

  const pendingCount = recommendations?.steps?.length || 0;

  return (
    <Tabs value={activeTab} onChange={handleTabChange}>
      <Tabs.List>
        <Tabs.Tab value="next-actions" style={{ fontFamily: 'var(--mantine-font-family)' }}>
          <Group gap="xs">
            <span>Next Actions</span>
            {pendingCount > 0 && (
              <Badge size="xs" color="blue" variant="filled" className="pulse" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                {pendingCount}
              </Badge>
            )}
          </Group>
        </Tabs.Tab>
        <Tabs.Tab value="diversification" style={{ fontFamily: 'var(--mantine-font-family)' }}>Diversification</Tabs.Tab>
        <Tabs.Tab value="security-universe" style={{ fontFamily: 'var(--mantine-font-family)' }}>Security Universe</Tabs.Tab>
        <Tabs.Tab value="recent-trades" style={{ fontFamily: 'var(--mantine-font-family)' }}>Recent Trades</Tabs.Tab>
        <Tabs.Tab value="logs" style={{ fontFamily: 'var(--mantine-font-family)' }}>Logs</Tabs.Tab>
        <div style={{
          marginLeft: 'auto',
          fontSize: '0.875rem',
          color: 'var(--mantine-color-dimmed)',
          fontFamily: 'var(--mantine-font-family)',
        }}>
          Press <kbd style={{
            padding: '2px 6px',
            backgroundColor: 'var(--mantine-color-dark-7)',
            border: '1px solid var(--mantine-color-dark-6)',
            borderRadius: '2px',
            fontFamily: 'var(--mantine-font-family)',
          }}>1-5</kbd>
        </div>
      </Tabs.List>
    </Tabs>
  );
}
