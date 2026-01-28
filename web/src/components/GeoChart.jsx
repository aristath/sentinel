/**
 * Geo Chart Component
 *
 * Provides weight editing interface for geographic allocation targets.
 */
import { useEffect, useMemo, useState } from 'react';
import { Group, Text, Button, Slider, Badge, Stack, Divider, ActionIcon } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { useAvailableGeographies, useSaveGeographyTargets, useDeleteGeographyTarget } from '../hooks/useAllocation';
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

export function GeoChart({ targets = {} }) {
  const { data: geographiesData } = useAvailableGeographies();
  const saveMutation = useSaveGeographyTargets();
  const deleteMutation = useDeleteGeographyTarget();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState(null); // null, 'weights', or 'list'
  const [localTargets, setLocalTargets] = useState(targets);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLocalTargets(targets);
  }, [targets]);

  const activeGeographies = geographiesData?.geographies || [];

  const sortedGeographies = useMemo(() => {
    return [...activeGeographies].sort();
  }, [activeGeographies]);

  const handleSliderChange = (name, value) => {
    const newTargets = { ...localTargets, [name]: value };
    setLocalTargets(newTargets);
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
      console.error('Failed to save geography targets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name) => {
    try {
      await deleteMutation.mutateAsync(name);
      // Hook handles optimistic update and cache invalidation
    } catch (error) {
      console.error('Failed to delete geography:', error);
    }
  };

  const handleCancel = () => {
    setLocalTargets(targets);
    setMode(null);
  };

  return (
    <div className="geo-chart">
      <Group className="geo-chart__header" justify="space-between" mb="md">
        <Text className="geo-chart__title" size="sm" fw={500}>
          Geography Weights
        </Text>
        {mode === null && (
          <Group gap="xs">
            <Button
              className="geo-chart__list-btn"
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => setMode('list')}
            >
              Edit List
            </Button>
            <Button
              className="geo-chart__edit-btn"
              size="sm"
              variant="subtle"
              onClick={() => setMode('weights')}
            >
              Edit Weights
            </Button>
          </Group>
        )}
      </Group>

      {/* Edit List Mode */}
      {mode === 'list' && (
        <Stack className="geo-chart__list" gap="xs">
          <Text size="sm" c="dimmed" mb="xs">
            Remove unused geographies:
          </Text>
          {sortedGeographies.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No geographies available
            </Text>
          ) : (
            sortedGeographies.map((name) => (
              <Group key={name} justify="space-between" className="geo-chart__list-item">
                <Text size="sm">{name}</Text>
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
        <Stack className="geo-chart__edit" gap="md">
          <Group className="geo-chart__legend" justify="space-between">
            <Text className="geo-chart__legend-avoid" size="sm" c="red">
              0 Avoid
            </Text>
            <Text className="geo-chart__legend-neutral" size="sm" c="dimmed">
              0.5 Neutral
            </Text>
            <Text className="geo-chart__legend-prioritize" size="sm" c="green">
              1 Prioritize
            </Text>
          </Group>

          <Divider className="geo-chart__divider" />

          {sortedGeographies.length === 0 ? (
            <Text className="geo-chart__empty" size="sm" c="dimmed" ta="center" p="md">
              No active geographies available
            </Text>
          ) : (
            sortedGeographies.map((name) => {
              const weight = localTargets[name] || 0;
              const badgeClass = getWeightBadgeClass(weight);

              return (
                <div className="geo-chart__slider-item" key={name}>
                  <Group className="geo-chart__slider-header" justify="space-between" mb="xs">
                    <Text className="geo-chart__slider-name" size="sm">
                      {name}
                    </Text>
                    <Badge className="geo-chart__slider-badge" size="sm" {...badgeClass}>
                      {formatWeight(weight)}
                    </Badge>
                  </Group>
                  <Slider
                    className="geo-chart__slider"
                    value={weight}
                    onChange={(val) => handleSliderChange(name, val)}
                    min={0}
                    max={1}
                    step={0.01}
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

          <Divider className="geo-chart__divider" />

          <Group className="geo-chart__actions" grow>
            <Button className="geo-chart__cancel-btn" variant="subtle" onClick={handleCancel}>
              Cancel
            </Button>
            <Button className="geo-chart__save-btn" onClick={handleSave} disabled={loading} loading={loading}>
              Save
            </Button>
          </Group>
        </Stack>
      )}
    </div>
  );
}
