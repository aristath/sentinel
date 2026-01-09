import { Paper, Group, Text, NumberInput } from '@mantine/core';
import { useState } from 'react';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { formatCurrency, formatNumber, formatTimestamp } from '../../utils/formatters';

export function StatusBar() {
  const { status, showMessage } = useAppStore();
  const { allocation, cashBreakdown, updateTestCash } = usePortfolioStore();
  const [editingTestCash, setEditingTestCash] = useState(false);
  const [testCashValue, setTestCashValue] = useState(null);

  return (
    <Paper
      p="md"
      style={{
        backgroundColor: 'var(--mantine-color-dark-7)',
        border: '1px solid var(--mantine-color-dark-6)',
      }}
    >
      {/* System Status Row */}
      <Group justify="space-between" mb="xs">
        <Group gap="md">
          <Group gap="xs">
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: status.status === 'healthy' ? 'var(--mantine-color-green-0)' : 'var(--mantine-color-red-0)',
              }}
            />
            <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
              {status.status === 'healthy' ? 'System Online' : 'System Offline'}
            </Text>
          </Group>
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">|</Text>
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
            Last sync: <span>{status.last_sync ? formatTimestamp(status.last_sync) : 'Never'}</span>
          </Text>
        </Group>
      </Group>

      {/* Portfolio Summary Row */}
      <Group justify="space-between">
        <Group gap="md" wrap="wrap">
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
            Total Value: <span style={{ color: 'var(--mantine-color-green-0)' }}>
              {formatCurrency(allocation.total_value)}
            </span>
          </Text>
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">|</Text>
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
            Cash: <span>
              {formatCurrency(allocation.cash_balance)}
            </span>
          </Text>
          {cashBreakdown && cashBreakdown.length > 0 && (
            <>
              <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
                ({cashBreakdown.map((cb, index) => {
                  if (cb.currency === 'TEST') {
                    const displayAmount = cb.amount ?? 0;
                    const isEditing = editingTestCash;
                    const currentValue = testCashValue !== null ? testCashValue : displayAmount;

                    return (
                      <span key={cb.currency}>
                        <span style={{ backgroundColor: 'rgba(166, 227, 161, 0.15)', padding: '2px 4px', borderRadius: '2px', border: '1px solid rgba(166, 227, 161, 0.3)' }}>
                          <span style={{ color: 'var(--mantine-color-green-0)' }}>{cb.currency}</span>:
                          {isEditing ? (
                            <NumberInput
                              value={currentValue}
                              onChange={(val) => setTestCashValue(val ?? 0)}
                              onBlur={async () => {
                                try {
                                  await updateTestCash(currentValue);
                                  setEditingTestCash(false);
                                  setTestCashValue(null);
                                  showMessage('TEST cash updated', 'success');
                                } catch (error) {
                                  showMessage(`Failed to update TEST cash: ${error.message}`, 'error');
                                  setEditingTestCash(false);
                                  setTestCashValue(null);
                                }
                              }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  e.currentTarget.blur();
                                } else if (e.key === 'Escape') {
                                  setEditingTestCash(false);
                                  setTestCashValue(null);
                                }
                              }}
                              size="xs"
                              min={0}
                              step={0.01}
                              precision={2}
                              style={{
                                display: 'inline-block',
                                width: '80px',
                                marginLeft: '4px',
                              }}
                              styles={{
                                input: {
                                  color: 'var(--mantine-color-green-0)',
                                  backgroundColor: 'rgba(166, 227, 161, 0.2)',
                                  border: '1px solid rgba(166, 227, 161, 0.5)',
                                  fontSize: 'var(--mantine-font-size-xs)',
                                  padding: '2px 4px',
                                  height: 'auto',
                                  minHeight: 'unset',
                                },
                              }}
                              autoFocus
                            />
                          ) : (
                            <span
                              style={{
                                color: 'var(--mantine-color-green-0)',
                                cursor: 'pointer',
                                textDecoration: 'underline',
                                textDecorationStyle: 'dotted',
                              }}
                              onClick={() => {
                                setEditingTestCash(true);
                                setTestCashValue(displayAmount);
                              }}
                              title="Click to edit"
                            >
                              {formatNumber(displayAmount, 2)}
                            </span>
                          )}
                        </span>
                      </span>
                    );
                  }
                  return (
                    <span key={cb.currency}>
                      <span>
                        {cb.currency}: <span>{formatNumber(cb.amount ?? 0, 2)}</span>
                      </span>
                      {index < cashBreakdown.length - 1 && ', '}
                    </span>
                  );
                })})
              </Text>
            </>
          )}
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">|</Text>
          <Text size="xs" c="dimmed" ff="var(--mantine-font-family)">
            Positions: <span>
              {status.active_positions || 0}
            </span>
          </Text>
        </Group>
      </Group>
    </Paper>
  );
}
