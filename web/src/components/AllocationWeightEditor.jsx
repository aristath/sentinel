/**
 * Allocation Weight Editor Component
 *
 * Provides weight editing interface for geographic or industry allocation targets.
 * Parameterized by `type` prop ("geography" or "industry").
 */
import { useEffect, useMemo, useState } from 'react';
import { Group, Text, Button, Slider, Badge, Stack, Divider, ActionIcon } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import {
  useAvailableGeographies,
  useAvailableIndustries,
  useSaveGeographyTargets,
  useSaveIndustryTargets,
  useDeleteGeographyTarget,
  useDeleteIndustryTarget,
} from '../hooks/useAllocation';
import { useQueryClient } from '@tanstack/react-query';

function formatWeight(weight) {
  if (weight === 0 || weight === undefined) return '0';
  return weight.toFixed(2);
}

function getWeightBadgeClass(weight) {
  if (weight > 0.7) return { color: 'green', variant: 'light' };
  if (weight < 0.3) return { color: 'red', variant: 'light' };
  return { color: 'gray', variant: 'light' };
}

const CONFIG = {
  geography: {
    label: 'Geography',
    dataKey: 'geographies',
    useAvailable: useAvailableGeographies,
    useSave: useSaveGeographyTargets,
    useDelete: useDeleteGeographyTarget,
    accentColor: undefined, // uses Mantine default
    cssPrefix: 'geo-chart',
    truncate: false,
  },
  industry: {
    label: 'Industry',
    dataKey: 'industries',
    useAvailable: useAvailableIndustries,
    useSave: useSaveIndustryTargets,
    useDelete: useDeleteIndustryTarget,
    accentColor: 'violet',
    cssPrefix: 'industry-chart',
    truncate: true,
  },
};

export function AllocationWeightEditor({ type, targets = {} }) {
  const config = CONFIG[type];
  const { data: availableData } = config.useAvailable();
  const saveMutation = config.useSave();
  const deleteMutation = config.useDelete();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState(null);
  const [localTargets, setLocalTargets] = useState(targets);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLocalTargets(targets);
  }, [targets]);

  const activeItems = availableData?.[config.dataKey] || [];

  const sortedItems = useMemo(() => {
    return [...activeItems].sort();
  }, [activeItems]);

  const handleSliderChange = (name, value) => {
    setLocalTargets((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await saveMutation.mutateAsync(localTargets);
      setMode(null);
      queryClient.invalidateQueries({ queryKey: ['allocation'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    } catch (error) {
      console.error(`Failed to save ${config.label.toLowerCase()} targets:`, error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name) => {
    try {
      await deleteMutation.mutateAsync(name);
    } catch (error) {
      console.error(`Failed to delete ${config.label.toLowerCase()}:`, error);
    }
  };

  const handleCancel = () => {
    setLocalTargets(targets);
    setMode(null);
  };

  const prefix = config.cssPrefix;
  const accent = config.accentColor;
  const truncateStyle = config.truncate ? { maxWidth: '200px' } : undefined;

  return (
    <div className={prefix}>
      <Group className={`${prefix}__header`} justify="space-between" mb="md">
        <Text className={`${prefix}__title`} size="sm" fw={500}>
          {config.label} Weights
        </Text>
        {mode === null && (
          <Group gap="xs">
            <Button
              className={`${prefix}__list-btn`}
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => setMode('list')}
            >
              Edit List
            </Button>
            <Button
              className={`${prefix}__edit-btn`}
              size="sm"
              variant="subtle"
              color={accent}
              onClick={() => setMode('weights')}
            >
              Edit Weights
            </Button>
          </Group>
        )}
      </Group>

      {/* Edit List Mode */}
      {mode === 'list' && (
        <Stack className={`${prefix}__list`} gap="xs">
          <Text size="sm" c="dimmed" mb="xs">
            Remove unused {config.label.toLowerCase() === 'geography' ? 'geographies' : 'industries'}:
          </Text>
          {sortedItems.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No {config.label.toLowerCase() === 'geography' ? 'geographies' : 'industries'} available
            </Text>
          ) : (
            sortedItems.map((name) => (
              <Group key={name} justify="space-between" className={`${prefix}__list-item`}>
                <Text size="sm" truncate={config.truncate} style={truncateStyle}>
                  {name}
                </Text>
                <ActionIcon
                  variant="subtle"
                  color="red"
                  size="sm"
                  onClick={() => handleDelete(name)}
                  loading={deleteMutation.isPending}
                >
                  <IconTrash size={14} />
                </ActionIcon>
              </Group>
            ))
          )}
          <Divider my="xs" />
          <Button variant="subtle" size="sm" onClick={() => setMode(null)}>
            Done
          </Button>
        </Stack>
      )}

      {/* Edit Weights Mode */}
      {mode === 'weights' && (
        <Stack className={`${prefix}__edit`} gap="md">
          <Group className={`${prefix}__legend`} justify="space-between">
            <Text className={`${prefix}__legend-avoid`} size="sm" c="red">
              0 Avoid
            </Text>
            <Text className={`${prefix}__legend-neutral`} size="sm" c="dimmed">
              0.5 Neutral
            </Text>
            <Text className={`${prefix}__legend-prioritize`} size="sm" c="green">
              1 Prioritize
            </Text>
          </Group>

          <Divider className={`${prefix}__divider`} />

          {sortedItems.length === 0 ? (
            <Text className={`${prefix}__empty`} size="sm" c="dimmed" ta="center" p="md">
              No active {config.label.toLowerCase() === 'geography' ? 'geographies' : 'industries'} available
            </Text>
          ) : (
            sortedItems.map((name) => {
              const weight = localTargets[name] || 0;
              const badgeClass = getWeightBadgeClass(weight);

              return (
                <div className={`${prefix}__slider-item`} key={name}>
                  <Group className={`${prefix}__slider-header`} justify="space-between" mb="xs">
                    <Text
                      className={`${prefix}__slider-name`}
                      size="sm"
                      truncate={config.truncate}
                      style={truncateStyle}
                    >
                      {name}
                    </Text>
                    <Badge className={`${prefix}__slider-badge`} size="sm" {...badgeClass}>
                      {formatWeight(weight)}
                    </Badge>
                  </Group>
                  <Slider
                    className={`${prefix}__slider`}
                    value={weight}
                    onChange={(val) => handleSliderChange(name, val)}
                    min={0}
                    max={1}
                    step={0.01}
                    color={accent}
                    marks={[
                      { value: 0, label: '0' },
                      { value: 0.5, label: '0.5' },
                      { value: 1, label: '1' },
                    ]}
                  />
                </div>
              );
            })
          )}

          <Divider className={`${prefix}__divider`} />

          <Group className={`${prefix}__actions`} grow>
            <Button className={`${prefix}__cancel-btn`} variant="subtle" onClick={handleCancel}>
              Cancel
            </Button>
            <Button
              className={`${prefix}__save-btn`}
              color={accent}
              onClick={handleSave}
              disabled={loading}
              loading={loading}
            >
              Save
            </Button>
          </Group>
        </Stack>
      )}
    </div>
  );
}
