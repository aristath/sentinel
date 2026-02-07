/**
 * Security Expanded Row Component
 *
 * Inline expandable content for a security row showing:
 * - Price chart (historical)
 * - Position data
 * - Controls (buy/sell toggles, multiplier, geography/industry)
 */
import { useState, useEffect } from 'react';
import {
  Group,
  Stack,
  Text,
  Badge,
  Switch,
  Slider,
  TagsInput,
  Grid,
  Box,
  Tooltip,
  ActionIcon,
} from '@mantine/core';
import { IconTrash, IconAlertTriangle } from '@tabler/icons-react';
import { SecurityChart } from './SecurityChart';
import { catppuccin } from '../theme';
import { formatCurrencySymbol as formatCurrency, formatPercent } from '../utils/formatting';
import { useCategories, parseCommaSeparated } from '../hooks/useCategories';

export function SecurityExpandedRow({ security, onUpdate, onDelete }) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [localMultiplier, setLocalMultiplier] = useState(null);
  const { data: categories } = useCategories();

  // Reset local state when security changes
  useEffect(() => {
    setLocalMultiplier(null);
  }, [security?.symbol]);

  if (!security) return null;

  const geographyOptions = categories?.geographies || [];
  const industryOptions = categories?.industries || [];

  const handleUpdate = async (field, value) => {
    setIsUpdating(true);
    try {
      await onUpdate(security.symbol, { [field]: value });
    } finally {
      setIsUpdating(false);
    }
  };

  const {
    symbol,
    currency,
    geography,
    industry,
    min_lot,
    aliases,
    allow_buy,
    allow_sell,
    user_multiplier,
    has_position,
    quantity,
    avg_cost,
    current_price,
    value_eur,
    profit_pct,
    profit_value_eur,
    current_allocation,
    ideal_allocation,
    opp_score,
    dip_score,
    capitulation_score,
    cycle_turn,
    freefall_block,
    prices,
    recommendation,
    price_warning,
  } = security;

  const allocationDelta = ideal_allocation - current_allocation;
  const isUnderweight = allocationDelta > 0.5;
  const isOverweight = allocationDelta < -0.5;

  const effectiveMultiplier = Math.max(0, Math.min(1, localMultiplier ?? user_multiplier ?? 0.5));

  return (
    <Box
      p="md"
      style={{
        background: catppuccin.mantle,
        borderTop: `1px solid ${catppuccin.surface0}`,
      }}
    >
      <Grid gutter="md">
        {/* Left Column: Chart & Stats */}
        <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
          <Stack gap="md">
            {/* Price Anomaly Warning */}
            {price_warning && (
              <Box
                p="xs"
                style={{
                  background: catppuccin.yellow + '33',
                  borderRadius: 'var(--mantine-radius-sm)',
                  border: `1px solid ${catppuccin.yellow}`,
                }}
              >
                <Group gap="xs">
                  <IconAlertTriangle size={16} color={catppuccin.yellow} />
                  <Text size="sm" fw={500}>{price_warning}</Text>
                </Group>
              </Box>
            )}

            {/* Chart */}
            <Box
              style={{
                background: catppuccin.base,
                borderRadius: 'var(--mantine-radius-sm)',
                padding: '8px',
              }}
            >
              <SecurityChart
                prices={prices}
                avgCost={avg_cost}
                hasPosition={has_position}
                width={300}
                height={150}
              />
            </Box>

            {/* Position Stats */}
            <Stack gap="xs">
              {has_position ? (
                <>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Quantity</Text>
                    <Text size="xs" fw={500}>{quantity}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Avg Cost</Text>
                    <Text size="xs">{formatCurrency(avg_cost, currency)}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Current Price</Text>
                    <Text size="xs">{formatCurrency(current_price, currency)}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Lot Size</Text>
                    <Text size="xs">{min_lot}</Text>
                  </Group>
                </>
              ) : (
                <>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Current Price</Text>
                    <Text size="xs">{formatCurrency(current_price, currency)}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="xs" c="dimmed">Lot Size</Text>
                    <Text size="xs">{min_lot}</Text>
                  </Group>
                </>
              )}
            </Stack>
          </Stack>
        </Grid.Col>

        {/* Middle Column: Settings */}
        <Grid.Col span={{ base: 12, md: 6, lg: 4 }}>
          <Stack gap="md">
            {/* Controls Row */}
            <Group justify="space-between">
              <Group gap="md">
                <Switch
                  label="Buy"
                  size="xs"
                  checked={allow_buy === 1}
                  onChange={(e) => handleUpdate('allow_buy', e.currentTarget.checked ? 1 : 0)}
                  disabled={isUpdating}
                />
                <Switch
                  label="Sell"
                  size="xs"
                  checked={allow_sell === 1}
                  onChange={(e) => handleUpdate('allow_sell', e.currentTarget.checked ? 1 : 0)}
                  disabled={isUpdating}
                />
              </Group>
              <Tooltip label="Delete security">
                <ActionIcon
                  variant="subtle"
                  color="red"
                  size="sm"
                  onClick={() => onDelete(security)}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>

            {/* Geography & Industry */}
            <TagsInput
              label="Geography"
              size="xs"
              data={geographyOptions}
              value={parseCommaSeparated(geography)}
              onChange={(v) => handleUpdate('geography', v)}
              placeholder="Select or type"
              clearable
              disabled={isUpdating}
            />
            <TagsInput
              label="Industry"
              size="xs"
              data={industryOptions}
              value={parseCommaSeparated(industry)}
              onChange={(v) => handleUpdate('industry', v)}
              placeholder="Select or type"
              clearable
              disabled={isUpdating}
            />

            <TagsInput
              label="Aliases"
              size="xs"
              value={parseCommaSeparated(aliases)}
              onChange={(v) => handleUpdate('aliases', v)}
              placeholder="News search names"
              clearable
              disabled={isUpdating}
            />

            {/* Conviction Multiplier */}
            <Box>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Conviction</Text>
                <Text size="xs" fw={500}>{effectiveMultiplier.toFixed(2)}</Text>
              </Group>
              <Slider
                value={effectiveMultiplier}
                onChange={setLocalMultiplier}
                onChangeEnd={(v) => {
                  setLocalMultiplier(null);
                  handleUpdate('user_multiplier', v);
                }}
                min={0}
                max={1}
                step={0.01}
                marks={[
                  { value: 0, label: '0.00' },
                  { value: 0.5, label: '0.50' },
                  { value: 1, label: '1.00' },
                ]}
                disabled={isUpdating}
                size="xs"
              />
            </Box>
          </Stack>
        </Grid.Col>

        {/* Right Column: Recommendation */}
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack gap="md">
            {/* Recommendation */}
            {recommendation && (
              <Box
                p="sm"
                style={{
                  background: catppuccin.base,
                  borderRadius: 'var(--mantine-radius-sm)',
                  borderLeft: `3px solid ${recommendation.action === 'buy' ? catppuccin.green : catppuccin.red}`,
                }}
              >
                <Group gap="sm">
                  <Badge
                    color={recommendation.action === 'buy' ? 'green' : 'red'}
                    variant="filled"
                    size="sm"
                  >
                    {recommendation.action.toUpperCase()}
                  </Badge>
                  <Text size="xs">
                    {formatCurrency(Math.abs(recommendation.value_delta_eur))}
                    {recommendation.action === 'sell' && quantity > 0 && (
                      <Text span c="dimmed"> ({Math.round((recommendation.quantity / quantity) * 100)}%)</Text>
                    )}
                  </Text>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>{recommendation.reason}</Text>
              </Box>
            )}

            {/* Deterministic Signals */}
            <Box>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Opportunity score</Text>
                <Text size="xs" fw={500}>{formatPercent((opp_score || 0) * 100, 1)}</Text>
              </Group>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Dip</Text>
                <Text size="xs" fw={500}>{formatPercent((dip_score || 0) * 100, 1)}</Text>
              </Group>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Capitulation</Text>
                <Text size="xs" fw={500}>{formatPercent((capitulation_score || 0) * 100, 1)}</Text>
              </Group>
              <Group justify="space-between" mb={4}>
                <Text size="xs" c="dimmed">Cycle turn</Text>
                <Text size="xs" fw={500}>{cycle_turn ? 'Yes' : 'No'}</Text>
              </Group>
              <Group justify="space-between">
                <Text size="xs" c="dimmed">Freefall blocked</Text>
                <Text size="xs" fw={500}>{freefall_block ? 'Yes' : 'No'}</Text>
              </Group>
            </Box>
          </Stack>
        </Grid.Col>
      </Grid>
    </Box>
  );
}
