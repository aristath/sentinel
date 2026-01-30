/**
 * Security Expanded Row Component
 *
 * Inline expandable content for a security row showing:
 * - Price chart with projection
 * - Position data
 * - Controls (buy/sell toggles, multiplier, geography/industry)
 * - ML Prediction settings
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
  Button,
  Progress,
  Collapse,
} from '@mantine/core';
import { IconTrash, IconAlertTriangle, IconBrain, IconPlayerPlay, IconRefresh } from '@tabler/icons-react';
import { SecurityChart } from './SecurityChart';
import { catppuccin } from '../theme';
import { formatCurrencySymbol as formatCurrency, formatPercent } from '../utils/formatting';
import { useCategories, parseCommaSeparated } from '../hooks/useCategories';
import { useMLTraining } from '../hooks/useMLTraining';

export function SecurityExpandedRow({ security, onUpdate, onDelete }) {
  const [isUpdating, setIsUpdating] = useState(false);
  const [localMultiplier, setLocalMultiplier] = useState(null);
  const [localBlendRatio, setLocalBlendRatio] = useState(null);
  const { data: categories } = useCategories();

  const {
    status: mlStatus,
    train: handleTrainMl,
    isTraining: mlTraining,
    progress: mlProgress,
    message: mlMessage,
    error: mlError,
    setError: setMlError,
    deleteTraining,
  } = useMLTraining(security?.symbol, { enabled: security?.ml_enabled === 1 });

  // Reset local state when security changes
  useEffect(() => {
    setLocalMultiplier(null);
    setLocalBlendRatio(null);
    setMlError(null);
  }, [security?.symbol, setMlError]);

  if (!security) return null;

  const handleDeleteMlData = () => {
    if (!confirm(`Delete all ML training data for ${security.symbol}?`)) return;
    deleteTraining();
  };

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
                expectedReturn={optimisticExpectedReturn}
                waveletScore={wavelet_score}
                mlScore={ml_score}
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
                <Text size="xs" fw={500}>{effectiveMultiplier.toFixed(1)}x</Text>
              </Group>
              <Slider
                value={effectiveMultiplier}
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
                size="xs"
              />
            </Box>
          </Stack>
        </Grid.Col>

        {/* Right Column: ML & Recommendation */}
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

            {/* ML Prediction */}
            <Box>
              <Group justify="space-between" mb="xs">
                <Group gap="xs">
                  <IconBrain size={14} style={{ opacity: 0.7 }} />
                  <Text size="xs" fw={500}>ML Prediction</Text>
                </Group>
                <Switch
                  size="xs"
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
                        {(effectiveBlendRatio * 100).toFixed(0)}% ML
                      </Text>
                    </Group>
                    <Slider
                      value={effectiveBlendRatio}
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
                    <Text size="xs" c="dimmed">
                      {mlStatus.model_exists
                        ? `Model trained (${mlStatus.sample_count || mlStatus.model_info?.training_samples || 0} samples)`
                        : `${mlStatus.sample_count || 0} samples available`}
                    </Text>
                  )}

                  {mlTraining && (
                    <Box>
                      <Progress value={mlProgress} size="xs" animated />
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
                      leftSection={mlStatus?.model_exists ? <IconRefresh size={12} /> : <IconPlayerPlay size={12} />}
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
                        Delete
                      </Button>
                    )}
                  </Group>
                </Stack>
              </Collapse>
            </Box>
          </Stack>
        </Grid.Col>
      </Grid>
    </Box>
  );
}
