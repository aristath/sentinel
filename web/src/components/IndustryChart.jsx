/**
 * Industry Chart Component
 *
 * Provides weight editing interface for industry allocation targets.
 */
import { useEffect, useMemo, useState } from 'react';
import { Group, Text, Button, Slider, Badge, Stack, Divider, ActionIcon } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { useAvailableIndustries, useSaveIndustryTargets, useDeleteIndustryTarget } from '../hooks/useAllocation';
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

export function IndustryChart({ targets = {} }) {
  const { data: industriesData } = useAvailableIndustries();
  const saveMutation = useSaveIndustryTargets();
  const deleteMutation = useDeleteIndustryTarget();
  const queryClient = useQueryClient();

  const [mode, setMode] = useState(null); // null, 'weights', or 'list'
  const [localTargets, setLocalTargets] = useState(targets);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLocalTargets(targets);
  }, [targets]);

  const activeIndustries = industriesData?.industries || [];

  const sortedIndustries = useMemo(() => {
    return [...activeIndustries].sort();
  }, [activeIndustries]);

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
      console.error('Failed to save industry targets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (name) => {
    try {
      await deleteMutation.mutateAsync(name);
      // Hook handles optimistic update and cache invalidation
    } catch (error) {
      console.error('Failed to delete industry:', error);
    }
  };

  const handleCancel = () => {
    setLocalTargets(targets);
    setMode(null);
  };

  return (
    <div className="industry-chart">
      <Group className="industry-chart__header" justify="space-between" mb="md">
        <Text className="industry-chart__title" size="sm" fw={500}>
          Industry Weights
        </Text>
        {mode === null && (
          <Group gap="xs">
            <Button
              className="industry-chart__list-btn"
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => setMode('list')}
            >
              Edit List
            </Button>
            <Button
              className="industry-chart__edit-btn"
              size="sm"
              variant="subtle"
              color="violet"
              onClick={() => setMode('weights')}
            >
              Edit Weights
            </Button>
          </Group>
        )}
      </Group>

      {/* Edit List Mode */}
      {mode === 'list' && (
        <Stack className="industry-chart__list" gap="xs">
          <Text size="sm" c="dimmed" mb="xs">
            Remove unused industries:
          </Text>
          {sortedIndustries.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No industries available
            </Text>
          ) : (
            sortedIndustries.map((name) => (
              <Group key={name} justify="space-between" className="industry-chart__list-item">
                <Text size="sm" truncate style={{ maxWidth: '200px' }}>
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
        <Stack className="industry-chart__edit" gap="md">
          <Group className="industry-chart__legend" justify="space-between">
            <Text className="industry-chart__legend-avoid" size="sm" c="red">
              0 Avoid
            </Text>
            <Text className="industry-chart__legend-neutral" size="sm" c="dimmed">
              0.5 Neutral
            </Text>
            <Text className="industry-chart__legend-prioritize" size="sm" c="green">
              1 Prioritize
            </Text>
          </Group>

          <Divider className="industry-chart__divider" />

          {sortedIndustries.length === 0 ? (
            <Text className="industry-chart__empty" size="sm" c="dimmed" ta="center" p="md">
              No active industries available
            </Text>
          ) : (
            sortedIndustries.map((name) => {
              const weight = localTargets[name] || 0;
              const badgeClass = getWeightBadgeClass(weight);

              return (
                <div className="industry-chart__slider-item" key={name}>
                  <Group className="industry-chart__slider-header" justify="space-between" mb="xs">
                    <Text className="industry-chart__slider-name" size="sm" truncate style={{ maxWidth: '200px' }}>
                      {name}
                    </Text>
                    <Badge className="industry-chart__slider-badge" size="sm" {...badgeClass}>
                      {formatWeight(weight)}
                    </Badge>
                  </Group>
                  <Slider
                    className="industry-chart__slider"
                    value={weight}
                    onChange={(val) => handleSliderChange(name, val)}
                    min={0}
                    max={1}
                    step={0.01}
                    color="violet"
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

          <Divider className="industry-chart__divider" />

          <Group className="industry-chart__actions" grow>
            <Button className="industry-chart__cancel-btn" variant="subtle" onClick={handleCancel}>
              Cancel
            </Button>
            <Button
              className="industry-chart__save-btn"
              color="violet"
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
