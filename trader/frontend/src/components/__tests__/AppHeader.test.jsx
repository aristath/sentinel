import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { AppHeader } from '../layout/AppHeader';
import { useAppStore } from '../../stores/appStore';
import { useSettingsStore } from '../../stores/settingsStore';

// Mock stores
vi.mock('../../stores/appStore', () => ({
  useAppStore: vi.fn(),
}));

vi.mock('../../stores/settingsStore', () => ({
  useSettingsStore: vi.fn(),
}));

describe('AppHeader', () => {
  it('renders the application title', () => {
    useAppStore.mockReturnValue({
      tradernet: { connected: false },
      openSettingsModal: vi.fn(),
    });
    useSettingsStore.mockReturnValue({
      tradingMode: 'research',
      toggleTradingMode: vi.fn(),
    });

    render(
      <MantineProvider>
        <AppHeader />
      </MantineProvider>
    );

    expect(screen.getByText('Arduino Trader')).toBeInTheDocument();
  });
});

