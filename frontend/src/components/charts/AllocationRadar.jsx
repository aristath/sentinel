import { useMemo } from 'react';
import { RadarChart } from './RadarChart';
import { usePortfolioStore } from '../../stores/portfolioStore';

/**
 * Allocation Radar Component
 * Displays country and industry allocations as radar charts
 */
// Helper function to convert weights to percentages
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

export function AllocationRadar({ type = 'both' }) {
  const { allocation, activeCountries, activeIndustries } = usePortfolioStore();

  // Calculate country data
  const geoData = useMemo(() => {
    if (type !== 'country' && type !== 'both') return null;

    const labels = Array.from(activeCountries || []);
    if (labels.length === 0 || !allocation.country || allocation.country.length === 0) {
      return null;
    }

    const currentData = labels.map(country => {
      const item = allocation.country.find(a => a.name === country);
      return item ? item.current_pct * 100 : 0;
    });

    const weights = {};
    allocation.country.forEach(a => {
      weights[a.name] = a.target_pct || 0;
    });

    const targetPcts = getTargetPcts(weights, labels);
    const targetData = labels.map(country => (targetPcts[country] || 0) * 100);

    const allValues = [...targetData, ...currentData];
    const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

    return { labels, targetData, currentData, maxValue };
  }, [type, allocation.country, activeCountries]);

  // Calculate industry data
  const industryData = useMemo(() => {
    if (type !== 'industry' && type !== 'both') return null;

    const labels = Array.from(activeIndustries || []);
    if (labels.length === 0 || !allocation.industry || allocation.industry.length === 0) {
      return null;
    }

    const currentData = labels.map(industry => {
      const item = allocation.industry.find(a => a.name === industry);
      return item ? item.current_pct * 100 : 0;
    });

    const weights = {};
    allocation.industry.forEach(a => {
      weights[a.name] = a.target_pct || 0;
    });

    const targetPcts = getTargetPcts(weights, labels);
    const targetData = labels.map(industry => (targetPcts[industry] || 0) * 100);

    const allValues = [...targetData, ...currentData];
    const maxValue = allValues.length > 0 ? Math.max(...allValues) : 100;

    return { labels, targetData, currentData, maxValue };
  }, [type, allocation.industry, activeIndustries]);

  return (
    <div>
      {/* Country Radar */}
      {(type === 'country' || type === 'both') && geoData && (
        <div style={{ marginBottom: type === 'both' ? '16px' : 0 }}>
          <RadarChart
            labels={geoData.labels}
            targetData={geoData.targetData}
            currentData={geoData.currentData}
            maxValue={geoData.maxValue}
          />
        </div>
      )}

      {/* Industry Radar */}
      {(type === 'industry' || type === 'both') && industryData && (
        <div>
          <RadarChart
            labels={industryData.labels}
            targetData={industryData.targetData}
            currentData={industryData.currentData}
            maxValue={industryData.maxValue}
          />
        </div>
      )}
    </div>
  );
}
