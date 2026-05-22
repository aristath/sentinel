/**
 * Composition Radar — deviation from ideal, current vs post-plan.
 *
 * The radar's center is `−max_cap`, outer ring is `+max_cap`, and the middle
 * ring is `0` (the "balanced" reference, drawn with a thicker stroke). Each
 * axis is a country/industry bucket; each polyline shows
 * `actual_pct − ideal_pct` (in percentage points) per axis. A polyline point
 * INSIDE the balance ring = underweight on that axis; OUTSIDE = overweight.
 * A perfectly balanced portfolio shows as a circle on the balance ring.
 *
 *   - Green solid  → current deviation (where you are now)
 *   - Yellow dash  → post-plan deviation (where you'd be after the recs)
 *
 * The scale auto-fits to the largest absolute deviation across both series
 * and all axes (rounded up to the nearest 5pp; floored at ±5pp so a perfectly
 * balanced portfolio still has visible rings).
 */
import { RadarChart } from './RadarChart';

const MAX_AXES = 10;
const OTHER_LABEL = 'Other';
const SCALE_STEP = 5;
const SCALE_FLOOR = 5;

function toMap(buckets) {
  const m = new Map();
  for (const b of buckets || []) m.set(b.name, b.pct);
  return m;
}

function buildAlignedDeviations(current, ideal, postPlan) {
  const c = toMap(current);
  const i = toMap(ideal);
  const p = toMap(postPlan);

  // Union of all bucket names — a security can be in the ideal but not yet
  // held (and vice versa). Every bucket gets a deviation on every series.
  const names = new Set([...c.keys(), ...i.keys(), ...p.keys()]);

  // Step 1 — *select* the axes to display. Rank by maximum |deviation| across
  // either series so the most-distorted buckets win the limited axis slots.
  const ranked = [...names]
    .map((name) => {
      const ii = i.get(name) || 0;
      const cDev = Math.abs((c.get(name) || 0) - ii);
      const pDev = Math.abs((p.get(name) || 0) - ii);
      return { name, dev: Math.max(cDev, pDev) };
    })
    .sort((a, b) => b.dev - a.dev);

  const topNames = ranked.slice(0, MAX_AXES).map((r) => r.name);
  const restNames = ranked.slice(MAX_AXES).map((r) => r.name);

  // Tail rolls into a single "Other" axis. Aggregating the absolute
  // allocations first and then taking the diff makes "Other" represent the
  // *net* allocation gap across the tail — honest summation.
  const restSum = (m) => restNames.reduce((acc, n) => acc + (m.get(n) || 0), 0);
  const showOther = restNames.length > 0;
  const candidateLabels = showOther ? [...topNames, OTHER_LABEL] : topNames;

  const currentDevFor = (name) => {
    if (name === OTHER_LABEL) return restSum(c) - restSum(i);
    return (c.get(name) || 0) - (i.get(name) || 0);
  };
  const postPlanDevFor = (name) => {
    if (name === OTHER_LABEL) return restSum(p) - restSum(i);
    return (p.get(name) || 0) - (i.get(name) || 0);
  };

  // Step 2 — *order* the chosen axes by signed CURRENT deviation, descending.
  // Result: largest positive at 12 o'clock, sweeping clockwise to the most
  // negative just counter-clockwise from the top. The current polyline reads
  // as a smooth curve from top-right around to top-left rather than a jagged
  // saw-tooth, even when deviations have mixed signs.
  const sortedLabels = candidateLabels
    .map((name) => ({ name, dev: currentDevFor(name) }))
    .sort((a, b) => b.dev - a.dev)
    .map((entry) => entry.name);

  // Backend deltas are fractions (0.39 for +39%); convert to percentage
  // points so the radar's tick labels read naturally as `+20`, `-20`, etc.
  const toPP = (arr) => arr.map((v) => v * 100);

  return {
    labels: sortedLabels,
    currentDev: toPP(sortedLabels.map(currentDevFor)),
    postPlanDev: toPP(sortedLabels.map(postPlanDevFor)),
  };
}

export function CompositionRadar({ current, ideal, postPlan }) {
  if (!current || current.length === 0) return null;

  const { labels, currentDev, postPlanDev } = buildAlignedDeviations(current, ideal, postPlan);

  // Symmetric scale: take the largest absolute deviation across all series
  // and axes, round up to a clean step. The floor keeps a perfectly balanced
  // portfolio from collapsing the value range to zero.
  const allDev = [...currentDev, ...postPlanDev];
  const peak = allDev.length > 0 ? Math.max(...allDev.map(Math.abs)) : 0;
  const maxCap = Math.max(SCALE_FLOOR, Math.ceil(peak / SCALE_STEP) * SCALE_STEP);

  return (
    <RadarChart
      labels={labels}
      currentData={currentDev}
      postPlanData={postPlanDev}
      minValue={-maxCap}
      maxValue={maxCap}
      balanceValue={0}
      currentLabel="Current vs ideal"
      postPlanLabel="After plan vs ideal"
    />
  );
}
