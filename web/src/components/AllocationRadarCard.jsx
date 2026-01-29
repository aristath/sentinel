/**
 * Allocation Radar Card Component
 *
 * Displays allocation of the portfolio using radar chart visualization.
 * Parameterized by `type` prop ("geography" or "industry").
 */
import { useMemo } from 'react';
import { Card, Group, Text, Divider } from '@mantine/core';
import { RadarChart } from './RadarChart';
import { AllocationWeightEditor } from './AllocationWeightEditor';
import {
  useAllocation,
  useAvailableGeographies,
  useAvailableIndustries,
  useAllocationTargets,
} from '../hooks/useAllocation';

function getTargetPcts(weights, activeItems) {
  let total = 0;
  for (const name of activeItems) {
    total += weights[name] || 0;
  }
  const targets = {};
  for (const name of activeItems) {
    targets[name] = total > 0 ? (weights[name] || 0) / total : 0;
  }
  return targets;
}

const CONFIG = {
  geography: {
    label: 'Geography Allocation',
    targetsKey: 'geography',
    dataKey: 'geographies',
    securityField: 'geography',
    useAvailable: useAvailableGeographies,
    cssPrefix: 'geo-radar-card',
  },
  industry: {
    label: 'Industry Allocation',
    targetsKey: 'industry',
    dataKey: 'industries',
    securityField: 'industry',
    useAvailable: useAvailableIndustries,
    cssPrefix: 'industry-radar-card',
  },
};

export function AllocationRadarCard({ type, securities = [], recommendations = [] }) {
  const config = CONFIG[type];
  const { data: allocationData } = useAllocation();
  const { data: availableData } = config.useAvailable();
  const { data: targetsData } = useAllocationTargets();

  const targetsWeights = targetsData?.[config.targetsKey] || {};
  const activeItems = availableData?.[config.dataKey] || [];
  const allocData = Array.isArray(allocationData?.[config.targetsKey]) ? allocationData[config.targetsKey] : [];

  const radarData = useMemo(() => {
    if (activeItems.length === 0 || allocData.length === 0) {
      return null;
    }

    const labels = [...activeItems].sort();
    const currentData = labels.map((item) => {
      const found = allocData.find((a) => a.name === item);
      return found ? found.current_pct : 0;
    });

    // Build weights from targets or fallback to allocation data
    const weights = {};
    for (const item of labels) {
      if (targetsWeights[item] !== undefined) {
        weights[item] = targetsWeights[item];
      } else {
        const found = allocData.find((a) => a.name === item);
        if (found && found.target_pct !== undefined) {
          weights[item] = found.target_pct / 100;
        }
      }
    }
    const targetPcts = getTargetPcts(weights, labels);
    const targetData = labels.map((item) => (targetPcts[item] || 0) * 100);

    // Calculate post-plan allocation from securities and recommendations
    let postPlanData = [];
    if (securities.length > 0) {
      const recMap = {};
      (recommendations || []).forEach((r) => {
        recMap[r.symbol] = r.value_delta_eur || 0;
      });

      const totalPostPlanValue = securities.reduce((sum, s) => {
        const delta = recMap[s.symbol] || 0;
        return sum + (s.value_eur || 0) + delta;
      }, 0);

      const postPlanByItem = {};
      securities.forEach((s) => {
        const key = s[config.securityField];
        if (!key) return;
        const delta = recMap[s.symbol] || 0;
        const postValue = (s.value_eur || 0) + delta;
        postPlanByItem[key] = (postPlanByItem[key] || 0) + postValue;
      });

      postPlanData = labels.map((item) => {
        const value = postPlanByItem[item] || 0;
        return totalPostPlanValue > 0 ? (value / totalPostPlanValue) * 100 : 0;
      });
    }

    const allValues = [...targetData, ...currentData, ...postPlanData];
    const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

    return { labels, targetData, currentData, postPlanData, maxValue };
  }, [activeItems, allocData, targetsWeights, securities, recommendations, config.securityField]);

  const editorTargets = useMemo(() => {
    if (Object.keys(targetsWeights).length > 0) {
      return targetsWeights;
    }
    const targets = {};
    allocData.forEach((a) => {
      if (a.target_pct !== undefined && a.target_pct > 0) {
        targets[a.name] = a.target_pct / 100;
      }
    });
    return targets;
  }, [targetsWeights, allocData]);

  const prefix = config.cssPrefix;

  return (
    <Card className={prefix} p="md" withBorder>
      <Group className={`${prefix}__header`} justify="space-between" mb="md">
        <Text className={`${prefix}__title`} size="sm" tt="uppercase" c="dimmed" fw={600}>
          {config.label}
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

      <Divider className={`${prefix}__divider`} my="md" />

      <AllocationWeightEditor type={type} targets={editorTargets} />
    </Card>
  );
}
