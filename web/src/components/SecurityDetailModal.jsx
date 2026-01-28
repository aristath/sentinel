/**
 * Security Detail Modal
 *
 * Full-featured modal showing all information about a security:
 * - Price chart with projection
 * - Position data (quantity, avg cost, P/L)
 * - Allocation (current vs target)
 * - Controls (buy/sell toggles, multiplier, geography/industry)
 * - ML Prediction settings
 */
import { useState, useEffect, useRef } from 'react';
import {
  Modal,
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
  Button,
  Progress,
  Collapse,
} from '@mantine/core';
import { IconTrash, IconAlertTriangle, IconBrain, IconPlayerPlay, IconRefresh } from '@tabler/icons-react';
import { SecurityChart } from './SecurityChart';
import { catppuccin } from '../theme';
import { formatCurrencySymbol as formatCurrency, formatPercent } from '../utils/formatting';
import { useCategories, getGeographyOptions, getIndustryOptions, parseCommaSeparated } from '../hooks/useCategories';

export function SecurityDetailModal({ opened, onClose, security, onUpdate, onDelete }) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [localMultiplier, setLocalMultiplier] = useState(null);
  const [localBlendRatio, setLocalBlendRatio] = useState(null);
  const [mlTraining, setMlTraining] = useState(false);
  const [mlProgress, setMlProgress] = useState(0);
  const [mlMessage, setMlMessage] = useState('');
  const [mlError, setMlError] = useState(null);
  const [mlStatus, setMlStatus] = useState(null);
  const eventSourceRef = useRef(null);
  const { data: categories } = useCategories();

  // Reset local state when security changes
  useEffect(() => {
    setLocalMultiplier(null);
    setLocalBlendRatio(null);
    setMlError(null);
  }, [security?.symbol]);

  // Fetch ML training status on mount and when ml_enabled changes
  useEffect(() => {
    if (security?.ml_enabled) {
      fetch(`/api/ml/training-status/${security.symbol}`)
        .then(res => res.json())
        .then(setMlStatus)
        .catch(() => {});
    }
  }, [security?.symbol, security?.ml_enabled]);

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  if (!security) return null;

  const handleTrainMl = async () => {
    setMlTraining(true);
    setMlProgress(0);
    setMlMessage('Starting...');
    setMlError(null);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(`/api/ml/train/${security.symbol}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.error) {
        setMlError(data.error);
        setMlTraining(false);
        eventSource.close();
        return;
      }

      setMlProgress(data.progress || 0);
      setMlMessage(data.message || '');

      if (data.complete) {
        setMlTraining(false);
        setMlStatus({ model_exists: true, model_info: data.metrics });
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      setMlError('Connection lost');
      setMlTraining(false);
      eventSource.close();
    };
  };

  const handleDeleteMlData = async () => {
    if (!confirm(`Delete all ML training data for ${security.symbol}?`)) return;

    try {
      await fetch(`/api/ml/training-data/${security.symbol}`, { method: 'DELETE' });
      setMlStatus({ model_exists: false, sample_count: 0 });
    } catch (e) {
      setMlError('Failed to delete training data');
    }
  };

  const geographyOptions = getGeographyOptions(categories?.geographies || []);
  const industryOptions = getIndustryOptions(categories?.industries || []);

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
    name,
    currency,
    geography,
    industry,
    min_lot,
    allow_buy,
    allow_sell,
    user_multiplier,
    has_position,
    quantity,
    avg_cost,
    current_price,
    value_eur,
    profit_pct,
    profit_value,
    current_allocation,
    target_allocation,
    expected_return,
    wavelet_score,
    ml_score,
    prices,
    recommendation,
    price_warning,
    ml_enabled,
    ml_blend_ratio,
  } = security;

  const allocationDelta = target_allocation - current_allocation;
  const isUnderweight = allocationDelta > 0.5;
  const isOverweight = allocationDelta < -0.5;

  const effectiveMultiplier = localMultiplier ?? user_multiplier ?? 1;
  const effectiveBlendRatio = localBlendRatio ?? ml_blend_ratio ?? 0.5;

  const baseBlended = ml_enabled === 1 && wavelet_score != null && ml_score != null
    ? wavelet_score * (1 - effectiveBlendRatio) + ml_score * effectiveBlendRatio
    : (wavelet_score ?? expected_return ?? 0);

  const convictionBoost = (effectiveMultiplier - 1.0) * 0.3;
  const optimisticExpectedReturn = baseBlended + convictionBoost;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <Text fw={700} size="lg">{symbol}</Text>
          <Text c="dimmed" size="sm">{name}</Text>
          {!security.active && <Badge color="gray" size="sm">Inactive</Badge>}
        </Group>
      }
      size="xl"
    >
      <Stack gap="md">
        {/* Price Anomaly Warning */}
        {price_warning && (
          <Box
            p="xs"
            style={{
              // Style guide: warnings use Yellow
              background: catppuccin.yellow + '33',
              borderRadius: 'var(--mantine-radius-sm)',
              border: `1px solid ${catppuccin.yellow}`,
            }}
          >
            <Group gap="xs">
              <IconAlertTriangle size={16} color={catppuccin.yellow} />
              <Text size="sm" c="red" fw={500}>{price_warning}</Text>
            </Group>
          </Box>
        )}

        {/* Controls Row */}
        <Group justify="space-between">
          <Group gap="md">
            <Tooltip label="Allow buying this security">
              <Switch
                label="Buy"
                size="sm"
                checked={allow_buy === 1}
                onChange={(e) => handleUpdate('allow_buy', e.currentTarget.checked ? 1 : 0)}
                disabled={isUpdating}
              />
            </Tooltip>
            <Tooltip label="Allow selling this security">
              <Switch
                label="Sell"
                size="sm"
                checked={allow_sell === 1}
                onChange={(e) => handleUpdate('allow_sell', e.currentTarget.checked ? 1 : 0)}
                disabled={isUpdating}
              />
            </Tooltip>
          </Group>
          <Tooltip label="Delete security">
            <ActionIcon
              variant="subtle"
              color="red"
              size="sm"
              onClick={() => {
                onClose();
                onDelete(security);
              }}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>

        <Grid gutter="md">
          {/* Chart Column */}
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Box
              style={{
                background: catppuccin.mantle,
                borderRadius: 'var(--mantine-radius-sm)',
                padding: '8px',
              }}
            >
              <SecurityChart
                prices={prices}
                avgCost={avg_cost}
                expectedReturn={optimisticExpectedReturn}
                waveletScore={wavelet_score}
                mlScore={ml_score}
                hasPosition={has_position}
                width={350}
                height={180}
              />
            </Box>
          </Grid.Col>

          {/* Stats Column */}
          <Grid.Col span={{ base: 12, md: 6 }}>
            <Stack gap="xs">
              {has_position ? (
                <>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">Quantity</Text>
                    <Text size="sm" fw={500}>{quantity}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">Avg Cost</Text>
                    <Text size="sm">{formatCurrency(avg_cost, currency)}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">Current Price</Text>
                    <Text size="sm">{formatCurrency(current_price, currency)}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">Value</Text>
                    <Text size="sm">{formatCurrency(value_eur, 'EUR')}</Text>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">P/L</Text>
                    <Group gap="xs">
                      <Text size="sm" c={profit_pct >= 0 ? 'green' : 'red'} fw={500}>
                        {formatPercent(profit_pct)}
                      </Text>
                      <Text size="sm" c={profit_value >= 0 ? 'green' : 'red'}>
                        ({formatCurrency(profit_value, currency)})
                      </Text>
                    </Group>
                  </Group>
                </>
              ) : (
                <>
                  <Group justify="space-between">
                    <Text size="sm" c="dimmed">Current Price</Text>
                    <Text size="sm">{formatCurrency(current_price, currency)}</Text>
                  </Group>
                  <Text size="sm" c="dimmed" fs="italic">No position</Text>
                </>
              )}

              <Group justify="space-between" mt="xs">
                <Text size="sm" c="dimmed">Allocation</Text>
                <Group gap="xs">
                  <Text size="sm">{formatPercent(current_allocation, false)}</Text>
                  <Text size="sm" c="dimmed">{'\u2192'}</Text>
                  <Text
                    size="sm"
                    fw={500}
                    c={isUnderweight ? 'green' : isOverweight ? 'red' : undefined}
                  >
                    {formatPercent(target_allocation, false)}
                  </Text>
                </Group>
              </Group>

              <Group justify="space-between">
                <Text size="sm" c="dimmed">Lot Size</Text>
                <Text size="sm">{min_lot}</Text>
              </Group>
            </Stack>
          </Grid.Col>
        </Grid>

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
                size="lg"
              >
                {recommendation.action.toUpperCase()}
              </Badge>
              <Text size="sm">
                {formatCurrency(Math.abs(recommendation.value_delta_eur))}
                {recommendation.action === 'sell' && quantity > 0 && (
                  <Text span c="dimmed"> ({Math.round((recommendation.quantity / quantity) * 100)}%)</Text>
                )}
              </Text>
              <Text size="sm" c="dimmed">|</Text>
              <Text size="sm" c="dimmed">{recommendation.reason}</Text>
            </Group>
          </Box>
        )}

        {/* Geography & Industry */}
        <Grid gutter="md">
          <Grid.Col span={6}>
            <TagsInput
              label="Geography"
              size="sm"
              data={geographyOptions}
              value={parseCommaSeparated(geography)}
              onChange={(v) => handleUpdate('geography', v)}
              placeholder="Select or type"
              clearable
              disabled={isUpdating}
            />
          </Grid.Col>
          <Grid.Col span={6}>
            <TagsInput
              label="Industry"
              size="sm"
              data={industryOptions}
              value={parseCommaSeparated(industry)}
              onChange={(v) => handleUpdate('industry', v)}
              placeholder="Select or type"
              clearable
              disabled={isUpdating}
            />
          </Grid.Col>
        </Grid>

        {/* Conviction Multiplier */}
        <Box>
          <Group justify="space-between" mb={4}>
            <Text size="sm" c="dimmed">Conviction Multiplier</Text>
            <Text size="sm" fw={500}>{(localMultiplier ?? user_multiplier ?? 1).toFixed(1)}x</Text>
          </Group>
          <Slider
            value={localMultiplier ?? user_multiplier ?? 1}
            onChange={setLocalMultiplier}
            onChangeEnd={(v) => {
              setLocalMultiplier(null);
              handleUpdate('user_multiplier', v);
            }}
            min={0.25}
            max={2}
            step={0.1}
            marks={[
              { value: 0.5, label: '0.5x' },
              { value: 1, label: '1x' },
              { value: 1.5, label: '1.5x' },
              { value: 2, label: '2x' },
            ]}
            disabled={isUpdating}
            size="sm"
          />
        </Box>

        {/* ML Prediction */}
        <Box mt="md">
          <Group justify="space-between" mb="xs">
            <Group gap="xs">
              <IconBrain size={16} style={{ opacity: 0.7 }} />
              <Text size="sm" fw={500}>ML Prediction</Text>
            </Group>
            <Switch
              size="sm"
              checked={ml_enabled === 1}
              onChange={(e) => handleUpdate('ml_enabled', e.currentTarget.checked ? 1 : 0)}
              disabled={isUpdating}
            />
          </Group>

          <Collapse in={ml_enabled === 1}>
            <Stack gap="xs">
              <Box>
                <Group justify="space-between" mb={4}>
                  <Text size="xs" c="dimmed">Blend Ratio</Text>
                  <Text size="xs" fw={500}>
                    {((localBlendRatio ?? ml_blend_ratio ?? 0.5) * 100).toFixed(0)}% ML
                  </Text>
                </Group>
                <Slider
                  value={localBlendRatio ?? ml_blend_ratio ?? 0.5}
                  onChange={setLocalBlendRatio}
                  onChangeEnd={(v) => {
                    setLocalBlendRatio(null);
                    handleUpdate('ml_blend_ratio', v);
                  }}
                  min={0}
                  max={1}
                  step={0.01}
                  marks={[
                    { value: 0, label: 'Wavelet' },
                    { value: 0.5, label: '50/50' },
                    { value: 1, label: 'ML' },
                  ]}
                  disabled={isUpdating}
                  size="xs"
                />
              </Box>

              {mlStatus && (
                <Group gap="xs">
                  <Text size="xs" c="dimmed">
                    {mlStatus.model_exists
                      ? `Model trained (${mlStatus.sample_count || mlStatus.model_info?.training_samples || 0} samples)`
                      : `${mlStatus.sample_count || 0} samples available`}
                  </Text>
                </Group>
              )}

              {mlTraining && (
                <Box>
                  <Progress value={mlProgress} size="sm" animated />
                  <Text size="xs" c="dimmed" mt={4}>{mlMessage}</Text>
                </Box>
              )}

              {mlError && (
                <Text size="xs" c="red">{mlError}</Text>
              )}

              <Group gap="xs">
                <Button
                  size="xs"
                  variant="light"
                  leftSection={mlStatus?.model_exists ? <IconRefresh size={14} /> : <IconPlayerPlay size={14} />}
                  onClick={handleTrainMl}
                  loading={mlTraining}
                  disabled={isUpdating}
                >
                  {mlStatus?.model_exists ? 'Retrain' : 'Train'}
                </Button>
                {mlStatus?.model_exists && (
                  <Button
                    size="xs"
                    variant="subtle"
                    color="red"
                    onClick={handleDeleteMlData}
                    disabled={mlTraining || isUpdating}
                  >
                    Delete Data
                  </Button>
                )}
              </Group>
            </Stack>
          </Collapse>
        </Box>
      </Stack>
    </Modal>
  );
}
