import { Alert, Badge, Box, Button, Card, Collapse, Group, Slider, Stack, Text } from '@mantine/core';
import { IconChevronDown, IconChevronRight, IconDeviceFloppy, IconRotate } from '@tabler/icons-react';

import { normalizeWeights } from '../utils/mlWeights';

const WEIGHT_FIELDS = [
  { key: 'wavelet', label: 'Wavelet' },
  { key: 'xgboost', label: 'XGBoost' },
  { key: 'ridge', label: 'Ridge' },
  { key: 'rf', label: 'RF' },
  { key: 'svr', label: 'SVR' },
];

function isEqualWeights(a, b) {
  if (!a || !b) return false;
  return WEIGHT_FIELDS.every(({ key }) => Number(a[key] ?? 0) === Number(b[key] ?? 0));
}

export function PortfolioWeightControls({
  opened,
  onToggle,
  draftWeights,
  baselineWeights,
  onWeightChange,
  onSave,
  onReset,
  isSaving = false,
  error = '',
  showToggle = true,
}) {
  const normalized = normalizeWeights(draftWeights);
  const isValid = normalized != null;
  const isDirty = !isEqualWeights(draftWeights, baselineWeights);

  return (
    <Card shadow="sm" padding="sm" withBorder>
      <Group justify="space-between">
        <Text size="sm" fw={500}>Prediction Weights</Text>
        {showToggle && (
          <Button
            variant="subtle"
            size="xs"
            leftSection={opened ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
            onClick={onToggle}
          >
            {opened ? 'Collapse' : 'Expand'}
          </Button>
        )}
      </Group>

      <Collapse in={showToggle ? opened : true}>
        <Stack gap="sm" mt="sm">
          {WEIGHT_FIELDS.map(({ key, label }) => {
            const rawValue = Number(draftWeights?.[key] ?? 0);
            const pct = normalized ? normalized[key] * 100 : 0;
            return (
              <Box key={key}>
                <Group justify="space-between" mb={4}>
                  <Text size="xs" fw={500}>{label}</Text>
                  <Group gap="xs">
                    <Badge size="xs" variant="light">{rawValue.toFixed(2)}</Badge>
                    <Badge size="xs" variant="dot">{pct.toFixed(1)}%</Badge>
                  </Group>
                </Group>
                <Slider
                  value={rawValue}
                  onChange={(value) => onWeightChange(key, value)}
                  min={0}
                  max={1}
                  step={0.01}
                  label={(value) => value.toFixed(2)}
                  disabled={isSaving}
                />
              </Box>
            );
          })}

          {!isValid && (
            <Alert color="red" variant="light">
              Total weight must be greater than zero.
            </Alert>
          )}

          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}

          <Group justify="flex-end">
            <Button
              size="xs"
              variant="subtle"
              leftSection={<IconRotate size={14} />}
              disabled={!isDirty || isSaving}
              onClick={onReset}
            >
              Reset
            </Button>
            <Button
              size="xs"
              leftSection={<IconDeviceFloppy size={14} />}
              disabled={!isValid || !isDirty}
              loading={isSaving}
              onClick={onSave}
            >
              Save
            </Button>
          </Group>
        </Stack>
      </Collapse>
    </Card>
  );
}
