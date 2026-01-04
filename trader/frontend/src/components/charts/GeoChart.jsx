import { useMemo } from 'react';
import { Group, Text, Button, Slider, Badge, Stack, Divider } from '@mantine/core';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { useNotifications } from '../../hooks/useNotifications';
import { formatPercent } from '../../utils/formatters';

// Generate consistent color for country name
function getCountryColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 70%, 50%)`;
}

// Convert weights to target percentages
function getTargetPcts(weights, activeCountries) {
  const shifted = {};
  let total = 0;
  for (const name of activeCountries) {
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

export function GeoChart() {
  const {
    allocation,
    countryTargets,
    editingCountry,
    activeCountries,
    startEditCountry,
    cancelEditCountry,
    adjustCountrySlider,
    saveCountryTargets,
    loading,
  } = usePortfolioStore();
  const { showNotification } = useNotifications();

  const handleSave = async () => {
    try {
      await saveCountryTargets();
      showNotification('Country targets saved successfully', 'success');
    } catch (error) {
      showNotification(`Failed to save country targets: ${error.message}`, 'error');
    }
  };

  const countryAllocations = allocation.country || [];

  const targets = useMemo(() => {
    return getTargetPcts(countryTargets, activeCountries);
  }, [countryTargets, activeCountries]);

  const sortedCountries = useMemo(() => {
    return [...activeCountries].sort();
  }, [activeCountries]);

  return (
    <div>
      <Group justify="space-between" mb="md">
        <Text size="xs" fw={500}>Country Groups</Text>
        {!editingCountry && (
          <Button
            size="xs"
            variant="subtle"
            onClick={startEditCountry}
          >
            Edit Weights
          </Button>
        )}
      </Group>

      {/* View Mode - Show deviation from target allocation */}
      {!editingCountry && (
        <Stack gap="sm">
          {countryAllocations.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No country allocation data available
            </Text>
          ) : (
            countryAllocations.map((country) => {
            const deviation = getDeviation(country.name, country.current_pct, targets);
            const badgeClass = getDeviationBadgeClass(deviation);
            const barColor = getDeviationBarColor(deviation);
            const barStyle = getDeviationBarStyle(deviation);

            return (
              <div key={country.name}>
                <Group justify="space-between" mb="xs">
                  <Group gap="xs">
                    <div
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        backgroundColor: getCountryColor(country.name),
                      }}
                    />
                    <Text size="sm">{country.name}</Text>
                  </Group>
                  <Group gap="xs">
                    <Text size="sm" ff="monospace">
                      {formatPercent(country.current_pct)}
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
                      backgroundColor: 'var(--mantine-color-gray-5)',
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

      {/* Edit Mode - Weight sliders for active countries */}
      {editingCountry && (
        <Stack gap="md">
          {/* Weight Scale Legend */}
          <Group justify="space-between">
            <Text size="xs" c="red">-1 Avoid</Text>
            <Text size="xs" c="dimmed">0 Neutral</Text>
            <Text size="xs" c="green">+1 Prioritize</Text>
          </Group>

          <Divider />

          {/* Dynamic Country Sliders */}
          {sortedCountries.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" p="md">
              No active countries available
            </Text>
          ) : (
            sortedCountries.map((name) => {
            const weight = countryTargets[name] || 0;
            const badgeClass = getWeightBadgeClass(weight);

            return (
              <div key={name}>
                <Group justify="space-between" mb="xs">
                  <Group gap="xs">
                    <div
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        backgroundColor: getCountryColor(name),
                      }}
                    />
                    <Text size="sm">{name}</Text>
                  </Group>
                  <Badge size="xs" {...badgeClass} ff="monospace">
                    {formatWeight(weight)}
                  </Badge>
                </Group>
                <Slider
                  value={weight}
                  onChange={(val) => adjustCountrySlider(name, val)}
                  min={-1}
                  max={1}
                  step={0.01}
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
              onClick={cancelEditCountry}
            >
              Cancel
            </Button>
            <Button
              onClick={saveCountryTargets}
              disabled={loading.countrySave}
              loading={loading.countrySave}
            >
              Save
            </Button>
          </Group>
        </Stack>
      )}
    </div>
  );
}
