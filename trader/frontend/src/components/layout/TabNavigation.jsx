import { Tabs, Badge, Group } from '@mantine/core';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../../stores/appStore';
import { useEffect } from 'react';

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

  const handleTabChange = (value) => {
    setActiveTab(value);
    const routes = {
      'next-actions': '/',
      'diversification': '/diversification',
      'security-universe': '/security-universe',
      'recent-trades': '/recent-trades',
      'logs': '/logs',
    };
    navigate(routes[value] || '/');
  };

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pendingCount = recommendations?.steps?.length || 0;

  return (
    <Tabs value={activeTab} onChange={handleTabChange}>
      <Tabs.List>
        <Tabs.Tab value="next-actions">
          <Group gap="xs">
            <span>Next Actions</span>
            {pendingCount > 0 && (
              <Badge size="xs" color="blue" variant="filled" className="pulse">
                {pendingCount}
              </Badge>
            )}
          </Group>
        </Tabs.Tab>
        <Tabs.Tab value="diversification">Diversification</Tabs.Tab>
        <Tabs.Tab value="security-universe">Security Universe</Tabs.Tab>
        <Tabs.Tab value="recent-trades">Recent Trades</Tabs.Tab>
        <Tabs.Tab value="logs">Logs</Tabs.Tab>
        <div style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--mantine-color-dark-2)' }}>
          Press <kbd style={{ padding: '2px 6px', backgroundColor: 'var(--mantine-color-dark-6)', borderRadius: '4px' }}>1-5</kbd>
        </div>
      </Tabs.List>
    </Tabs>
  );
}
