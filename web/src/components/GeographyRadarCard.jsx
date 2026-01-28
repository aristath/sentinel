/**
 * Geography Radar Card Component
 *
 * Displays geographic allocation of the portfolio using radar chart visualization.
 */
import { useMemo } from 'react';
import { Card, Group, Text, Badge, Divider } from '@mantine/core';
import { RadarChart } from './RadarChart';
import { GeoChart } from './GeoChart';
import { useAllocation, useAvailableGeographies, useAllocationTargets } from '../hooks/useAllocation';

function getTargetPcts(weights, activeItems) {
  let total = 0;
  for (const name of activeItems) {
    const weight = weights[name] || 0;
    total += weight;
  }

  const targets = {};
  for (const name of activeItems) {
    const weight = weights[name] || 0;
    targets[name] = total > 0 ? weight / total : 0;
  }
  return targets;
}

export function GeographyRadarCard({ securities = [], recommendations = [] }) {
  const { data: allocationData } = useAllocation();
  const { data: geographiesData } = useAvailableGeographies();
  const { data: targetsData } = useAllocationTargets();

  const geographyTargetsWeights = targetsData?.geography || {};
  const activeGeographies = geographiesData?.geographies || [];
  const geographyAlloc = Array.isArray(allocationData?.geography) ? allocationData.geography : [];

  const radarData = useMemo(() => {
    if (activeGeographies.length === 0 || geographyAlloc.length === 0) {
      return null;
    }

    const labels = [...activeGeographies].sort();
    const currentData = labels.map((geo) => {
      const item = geographyAlloc.find((a) => a.name === geo);
      return item ? item.current_pct : 0;
    });

    const weights = {};
    for (const geo of labels) {
      if (geographyTargetsWeights[geo] !== undefined) {
        weights[geo] = geographyTargetsWeights[geo];
      } else {
        const item = geographyAlloc.find((a) => a.name === geo);
        if (item && item.target_pct !== undefined) {
          weights[geo] = item.target_pct / 100;
        }
      }
    }
    const targetPcts = getTargetPcts(weights, labels);
    const targetData = labels.map((geo) => (targetPcts[geo] || 0) * 100);

    // Calculate post-plan allocation from securities and recommendations
    let postPlanData = [];
    if (securities.length > 0) {
      // Calculate total current portfolio value
      const totalCurrentValue = securities.reduce((sum, s) => sum + (s.value_eur || 0), 0);

      // Build a map of symbol -> recommendation delta
      const recMap = {};
      (recommendations || []).forEach((r) => {
        recMap[r.symbol] = r.value_delta_eur || 0;
      });

      // Calculate total post-plan value
      const totalPostPlanValue = securities.reduce((sum, s) => {
        const delta = recMap[s.symbol] || 0;
        return sum + (s.value_eur || 0) + delta;
      }, 0);

      // Aggregate post-plan values by geography
      const postPlanByGeo = {};
      securities.forEach((s) => {
        const geo = s.geography;
        if (!geo) return;
        const delta = recMap[s.symbol] || 0;
        const postValue = (s.value_eur || 0) + delta;
        postPlanByGeo[geo] = (postPlanByGeo[geo] || 0) + postValue;
      });

      // Convert to percentages
      postPlanData = labels.map((geo) => {
        const value = postPlanByGeo[geo] || 0;
        return totalPostPlanValue > 0 ? (value / totalPostPlanValue) * 100 : 0;
      });
    }

    const allValues = [...targetData, ...currentData, ...postPlanData];
    const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

    return { labels, targetData, currentData, postPlanData, maxValue };
  }, [activeGeographies, geographyAlloc, geographyTargetsWeights, securities, recommendations]);

  const geographyTargets = useMemo(() => {
    if (Object.keys(geographyTargetsWeights).length > 0) {
      return geographyTargetsWeights;
    }
    const targets = {};
    geographyAlloc.forEach((a) => {
      if (a.target_pct !== undefined && a.target_pct > 0) {
        targets[a.name] = a.target_pct / 100;
      }
    });
    return targets;
  }, [geographyTargetsWeights, geographyAlloc]);

  return (
    <Card className="geo-radar-card" p="md" withBorder>
      <Group className="geo-radar-card__header" justify="space-between" mb="md">
        <Text className="geo-radar-card__title" size="sm" tt="uppercase" c="dimmed" fw={600}>
          Geography Allocation
        </Text>
      </Group>

      {radarData && (
        <RadarChart
          labels={radarData.labels}
          targetData={radarData.targetData}
          currentData={radarData.currentData}
          postPlanData={radarData.postPlanData}
          maxValue={radarData.maxValue}
        />
      )}

      <Divider className="geo-radar-card__divider" my="md" />

      <GeoChart targets={geographyTargets} />
    </Card>
  );
}
