import { useMemo } from 'react';
import { Group, Text, Button, Slider, Badge, Stack, Divider } from '@mantine/core';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useNotifications } from '../../hooks/useNotifications';
import { formatPercent } from '../../utils/formatters';

// Convert weights to target percentages
function getTargetPcts(weights, activeIndustries) {
  const shifted = {};
  let total = 0;
  for (const name of activeIndustries) {
    const weight = weights[name] || 0;
    shifted[name] = weight + 1; // -1→0, 0→1, +1→2
    total += shifted[name];
  }

  const targets = {};
  for (const [name, val] of Object.entries(shifted)) {
    targets[name] = total > 0 ? val / total : 0;
  }
  return targets;
}

// Calculate deviation: current% - target%
function getDeviation(name, currentPct, targets) {
  const targetPct = targets[name] || 0;
  return currentPct - targetPct;
}

function formatDeviation(deviation) {
  const pct = (deviation * 100).toFixed(1);
  return (deviation >= 0 ? '+' : '') + pct + '%';
}

function getDeviationBadgeClass(deviation) {
  if (Math.abs(deviation) < 0.02) return { color: 'gray', variant: 'light' };
  return deviation > 0
    ? { color: 'red', variant: 'light' }
    : { color: 'blue', variant: 'light' };
}

function getDeviationBarColor(deviation) {
  if (Math.abs(deviation) < 0.02) return 'gray';
  return deviation > 0 ? 'red' : 'blue';
}

function getDeviationBarStyle(deviation) {
  const maxDev = 0.50;
  const pct = Math.min(Math.abs(deviation), maxDev) / maxDev * 50;

  if (deviation >= 0) {
    return { width: `${pct}%`, left: '50%', right: 'auto' };
  } else {
    return { width: `${pct}%`, right: '50%', left: 'auto' };
  }
}

function formatWeight(weight) {
  if (weight === 0 || weight === undefined) return '0';
  return (weight > 0 ? '+' : '') + weight.toFixed(2);
}

function getWeightBadgeClass(weight) {
  if (weight > 0.1) return { color: 'green', variant: 'light' };
  if (weight < -0.1) return { color: 'red', variant: 'light' };
  return { color: 'gray', variant: 'light' };
}

export function IndustryChart() {
  const {
    allocation,
    industryTargets,
    editingIndustry,
    activeIndustries,
    startEditIndustry,
    cancelEditIndustry,
    adjustIndustrySlider,
    saveIndustryTargets,
    loading,
  } = usePortfolioStore();
  const { showNotification } = useNotifications();

  const handleSave = async () => {
    try {
      await saveIndustryTargets();
      showNotification('Industry targets saved successfully', 'success');
    } catch (error) {
      showNotification(`Failed to save industry targets: ${error.message}`, 'error');
    }
  };

  const industryAllocations = allocation.industry || [];

  const targets = useMemo(() => {
    return getTargetPcts(industryTargets, activeIndustries);
  }, [industryTargets, activeIndustries]);

  const sortedIndustries = useMemo(() => {
    return [...activeIndustries].sort();
  }, [activeIndustries]);

  return (
    <div>
      <Group justify="space-between" mb="md">
        <Text size="xs" fw={500}>Industry Groups</Text>
        {!editingIndustry && (
          <Button
            size="xs"
            variant="subtle"
            color="violet"
            onClick={startEditIndustry}
          >
            Edit Weights
          </Button>
        )}
      </Group>

      {/* View Mode - Show deviation from target allocation */}
      {!editingIndustry && (
        <Stack gap="sm">
          {industryAllocations.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No industry allocation data available
            </Text>
          ) : (
            industryAllocations.map((industry) => {
            const deviation = getDeviation(industry.name, industry.current_pct, targets);
            const badgeClass = getDeviationBadgeClass(deviation);
            const barColor = getDeviationBarColor(deviation);
            const barStyle = getDeviationBarStyle(deviation);

            return (
              <div key={industry.name}>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" truncate style={{ maxWidth: '200px' }}>
                    {industry.name}
                  </Text>
                  <Group gap="xs" style={{ flexShrink: 0 }}>
                    <Text size="xs" ff="monospace">
                      {formatPercent(industry.current_pct)}
                    </Text>
                    <Badge size="xs" {...badgeClass} ff="monospace">
                      {formatDeviation(deviation)}
                    </Badge>
                  </Group>
                </Group>
                {/* Deviation bar */}
                <div
                  style={{
                    height: '6px',
                    backgroundColor: 'var(--mantine-color-gray-3)',
                    borderRadius: '999px',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      bottom: 0,
                      left: '50%',
                      width: '1px',
                      backgroundColor: 'var(--mantine-color-dark-4)',
                      zIndex: 10,
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      bottom: 0,
                      borderRadius: '999px',
                      backgroundColor: `var(--mantine-color-${barColor}-5)`,
                      ...barStyle,
                    }}
                  />
                </div>
              </div>
            );
          }))}
        </Stack>
      )}

      {/* Edit Mode - Weight sliders for active industries */}
      {editingIndustry && (
        <Stack gap="md">
          {/* Weight Scale Legend */}
          <Group justify="space-between">
            <Text size="xs" c="red">-1 Avoid</Text>
            <Text size="xs" c="dimmed">0 Neutral</Text>
            <Text size="xs" c="green">+1 Prioritize</Text>
          </Group>

          <Divider />

          {/* Dynamic Industry Sliders */}
          {sortedIndustries.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No active industries available
            </Text>
          ) : (
            sortedIndustries.map((name) => {
            const weight = industryTargets[name] || 0;
            const badgeClass = getWeightBadgeClass(weight);

            return (
              <div key={name}>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" truncate style={{ maxWidth: '200px' }}>
                    {name}
                  </Text>
                  <Badge size="xs" {...badgeClass} ff="monospace" style={{ flexShrink: 0 }}>
                    {formatWeight(weight)}
                  </Badge>
                </Group>
                <Slider
                  value={weight}
                  onChange={(val) => adjustIndustrySlider(name, val)}
                  min={-1}
                  max={1}
                  step={0.01}
                  color="violet"
                  marks={[
                    { value: -1, label: '-1' },
                    { value: 0, label: '0' },
                    { value: 1, label: '+1' },
                  ]}
                />
              </div>
            );
          }))}

          <Divider />

          {/* Buttons */}
          <Group grow>
            <Button
              variant="subtle"
              onClick={cancelEditIndustry}
            >
              Cancel
            </Button>
            <Button
              color="violet"
              onClick={handleSave}
              disabled={loading.industrySave}
              loading={loading.industrySave}
            >
              Save
            </Button>
          </Group>
        </Stack>
      )}
    </div>
  );
}
