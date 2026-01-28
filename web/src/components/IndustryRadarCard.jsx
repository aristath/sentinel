/**
 * Industry Radar Card Component
 *
 * Displays industry/sector allocation of the portfolio using radar chart visualization.
 */
import { useMemo } from 'react';
import { Card, Group, Text, Divider } from '@mantine/core';
import { RadarChart } from './RadarChart';
import { IndustryChart } from './IndustryChart';
import { useAllocation, useAvailableIndustries, useAllocationTargets } from '../hooks/useAllocation';

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

export function IndustryRadarCard({ securities = [], recommendations = [] }) {
  const { data: allocationData } = useAllocation();
  const { data: industriesData } = useAvailableIndustries();
  const { data: targetsData } = useAllocationTargets();

  const industryTargetsWeights = targetsData?.industry || {};
  const activeIndustries = industriesData?.industries || [];
  const industryAlloc = Array.isArray(allocationData?.industry) ? allocationData.industry : [];

  const radarData = useMemo(() => {
    if (activeIndustries.length === 0 || industryAlloc.length === 0) {
      return null;
    }

    const labels = [...activeIndustries].sort();
    const currentData = labels.map((ind) => {
      const item = industryAlloc.find((a) => a.name === ind);
      return item ? item.current_pct : 0;
    });

    const weights = {};
    for (const ind of labels) {
      if (industryTargetsWeights[ind] !== undefined) {
        weights[ind] = industryTargetsWeights[ind];
      } else {
        const item = industryAlloc.find((a) => a.name === ind);
        if (item && item.target_pct !== undefined) {
          weights[ind] = item.target_pct / 100;
        }
      }
    }
    const targetPcts = getTargetPcts(weights, labels);
    const targetData = labels.map((ind) => (targetPcts[ind] || 0) * 100);

    // Calculate post-plan allocation from securities and recommendations
    let postPlanData = [];
    if (securities.length > 0) {
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

      // Aggregate post-plan values by industry
      const postPlanByInd = {};
      securities.forEach((s) => {
        const ind = s.industry;
        if (!ind) return;
        const delta = recMap[s.symbol] || 0;
        const postValue = (s.value_eur || 0) + delta;
        postPlanByInd[ind] = (postPlanByInd[ind] || 0) + postValue;
      });

      // Convert to percentages
      postPlanData = labels.map((ind) => {
        const value = postPlanByInd[ind] || 0;
        return totalPostPlanValue > 0 ? (value / totalPostPlanValue) * 100 : 0;
      });
    }

    const allValues = [...targetData, ...currentData, ...postPlanData];
    const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

    return { labels, targetData, currentData, postPlanData, maxValue };
  }, [activeIndustries, industryAlloc, industryTargetsWeights, securities, recommendations]);

  const industryTargets = useMemo(() => {
    if (Object.keys(industryTargetsWeights).length > 0) {
      return industryTargetsWeights;
    }
    const targets = {};
    industryAlloc.forEach((a) => {
      if (a.target_pct !== undefined && a.target_pct > 0) {
        targets[a.name] = a.target_pct / 100;
      }
    });
    return targets;
  }, [industryTargetsWeights, industryAlloc]);

  return (
    <Card className="industry-radar-card" p="md" withBorder>
      <Group className="industry-radar-card__header" justify="space-between" mb="md">
        <Text className="industry-radar-card__title" size="sm" tt="uppercase" c="dimmed" fw={600}>
          Industry Allocation
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

      <Divider className="industry-radar-card__divider" my="md" />

      <IndustryChart targets={industryTargets} />
    </Card>
  );
}
