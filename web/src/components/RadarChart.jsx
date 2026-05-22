/**
 * Radar Chart Component
 *
 * SVG-based radar/spider chart for displaying multi-dimensional data.
 * Shows both target and current allocation percentages for comparison.
 *
 * Features:
 * - Circular radar chart with configurable number of axes
 * - Target allocation (dashed blue line)
 * - Current allocation (solid green line with filled area)
 * - Grid circles (0%, 25%, 50%, 75%, 100%)
 * - Radial lines from center to each axis
 * - Tick marks and labels on 0° axis
 * - Point labels (geography/industry names) outside chart
 * - Legend showing Target vs Current
 * - Auto-scaling based on data range
 *
 * Used by AllocationRadar component for geography and industry visualization.
 */
import { useEffect, useRef } from 'react';
import { catppuccin } from '../theme';

/**
 * Radar chart component
 *
 * Renders an SVG-based radar chart comparing target vs current vs post-plan allocation.
 *
 * @param {Object} props - Component props
 * @param {Array<string>} props.labels - Axis labels (geography/industry names)
 * @param {Array<number>} props.targetData - Target allocation percentages (0-100)
 * @param {Array<number>} props.currentData - Current allocation percentages (0-100)
 * @param {Array<number>} props.postPlanData - Post-plan allocation percentages (0-100)
 * @param {number|null} props.maxValue - Maximum value for scaling (auto-calculated if null)
 * @returns {JSX.Element} Radar chart SVG component
 */
// A series is "present" only if it has data we should render. In the default
// (non-negative) scale that means at least one non-zero value — an all-zero
// array is just a stub the caller passed to satisfy the prop. In bipolar mode
// (minValue < 0), an all-zero series is *meaningful* — it means "perfectly
// balanced on every axis" — so we render it (as a circle on the balance ring).
const hasSeriesData = (data, bipolar) =>
  Array.isArray(data) && data.length > 0 && (bipolar ? true : data.some((v) => v > 0));

export function RadarChart({
  labels = [],
  targetData = [],
  currentData = [],
  postPlanData = [],
  maxValue = null,
  // `minValue` defines the value at the radar's center. Default 0 keeps the
  // traditional radar (radius = magnitude). Set to a negative number to put
  // the chart in bipolar mode where the *middle ring* (radius 0.5) represents
  // the geometric center of the value range — typically 0 for "no deviation".
  minValue = 0,
  // When set, the grid circle closest to this value gets a distinctive stroke
  // — used to highlight the "balanced / on-target" reference ring in bipolar
  // deviation charts. Pass `null` to disable.
  balanceValue = null,
  targetLabel = 'Target',
  currentLabel = 'Current',
  postPlanLabel = 'Post-Plan',
}) {
  const svgRef = useRef(null);

  // Render SVG chart when data changes
  useEffect(() => {
    if (!svgRef.current) return;

    // Validate data - clear chart if no labels
    if (!labels || labels.length === 0) {
      svgRef.current.innerHTML = '';
      return;
    }

    // Validate length of any non-empty series. An empty array means "not
    // provided" and is the caller's way of opting out of that polyline; we
    // only flag a real shape mismatch.
    const lengthMismatch = [targetData, currentData, postPlanData].some(
      (arr) => arr.length > 0 && arr.length !== labels.length,
    );
    if (lengthMismatch) {
      console.warn('RadarChart: Data length mismatch');
      return;
    }

    // Resolve the value range. In default mode (minValue=0) we auto-detect the
    // max from data and round up to the nearest 25 for clean tick labels (the
    // historic behavior). In bipolar mode the caller has already chosen a
    // symmetric scale based on actual data, so we honor it verbatim — no
    // rounding, no auto-detection from data.
    const bipolar = minValue < 0;
    let rangeMin = minValue;
    let rangeMax = maxValue;
    if (!bipolar) {
      const allValues = [...targetData, ...currentData, ...postPlanData];
      let maxVal = rangeMax;
      if (!maxVal || maxVal <= 0) {
        maxVal = allValues.length > 0 ? Math.max(...allValues) : 100;
      }
      rangeMax = Math.ceil(maxVal / 25) * 25;
    }
    const valueSpan = rangeMax - rangeMin;
    // Map a raw data value to a [0..1] normalized radius position.
    const toRadiusFraction = (v) => {
      if (valueSpan <= 0) return 0;
      return Math.max(0, Math.min(1, (v - rangeMin) / valueSpan));
    };

    // Chart dimensions and constants
    const centerX = 250;
    const centerY = 250;
    const radius = 180;
    const numPoints = labels.length;

    // Clear previous content
    svgRef.current.innerHTML = '';

    // Create SVG namespace
    const svgNS = 'http://www.w3.org/2000/svg';

    // Create SVG groups for organized rendering
    const gridGroup = document.createElementNS(svgNS, 'g');
    gridGroup.setAttribute('class', 'radar-chart__grid');

    const radialGroup = document.createElementNS(svgNS, 'g');
    radialGroup.setAttribute('class', 'radar-chart__radial-lines');

    const tickGroup = document.createElementNS(svgNS, 'g');
    tickGroup.setAttribute('class', 'radar-chart__ticks');

    const dataGroup = document.createElementNS(svgNS, 'g');
    dataGroup.setAttribute('class', 'radar-chart__data');

    const labelGroup = document.createElementNS(svgNS, 'g');
    labelGroup.setAttribute('class', 'radar-chart__labels');

    const legendGroup = document.createElementNS(svgNS, 'g');
    legendGroup.setAttribute('class', 'radar-chart__legend');

    // Draw 5 concentric grid circles. The circle nearest the `balanceValue`
    // (if any) gets a thicker stroke and the subtext color so it reads as the
    // "this is the on-target reference" line.
    const balanceFraction = balanceValue !== null ? toRadiusFraction(balanceValue) : null;
    for (let i = 0; i <= 4; i++) {
      const level = i / 4;
      const isBalanceRing =
        balanceFraction !== null && Math.abs(level - balanceFraction) < 1e-6;
      const circle = document.createElementNS(svgNS, 'circle');
      circle.setAttribute('cx', centerX);
      circle.setAttribute('cy', centerY);
      circle.setAttribute('r', radius * level);
      circle.setAttribute('fill', 'none');
      circle.setAttribute('stroke', isBalanceRing ? catppuccin.overlay2 : catppuccin.surface0);
      circle.setAttribute('stroke-width', isBalanceRing ? '1.6' : '1');
      circle.setAttribute(
        'class',
        isBalanceRing ? 'radar-chart__grid-circle radar-chart__grid-circle--balance' : 'radar-chart__grid-circle',
      );
      gridGroup.appendChild(circle);
    }

    // Calculate angles and coordinates for each data point
    // Angles start at -90° (top) and distribute evenly around circle
    const angles = [];
    const coordinates = [];

    for (let i = 0; i < numPoints; i++) {
      const angle = (360 / numPoints) * i - 90;  // Start at top (-90°)
      const angleRad = (angle * Math.PI) / 180;
      angles.push(angleRad);

      // Calculate endpoint coordinates for each axis
      const x = centerX + radius * Math.cos(angleRad);
      const y = centerY + radius * Math.sin(angleRad);
      coordinates.push({ x, y, angle: angleRad });
    }

    // Draw radial lines from center to each axis endpoint
    coordinates.forEach(coord => {
      const line = document.createElementNS(svgNS, 'line');
      line.setAttribute('x1', centerX);
      line.setAttribute('y1', centerY);
      line.setAttribute('x2', coord.x);
      line.setAttribute('y2', coord.y);
      line.setAttribute('stroke', catppuccin.surface0);
      line.setAttribute('stroke-width', '1');
      line.setAttribute('class', 'radar-chart__radial-line');
      radialGroup.appendChild(line);
    });

    // Draw tick marks and labels on top radial line (0° axis)
    // Shows percentage values at each grid level
    const tickLevels = [0, 0.25, 0.5, 0.75, 1.0];
    const tickLength = 5;
    const tickLabelOffset = 15;

    tickLevels.forEach((level) => {
      const tickRadius = radius * level;
      const tickX = centerX + tickRadius;  // On 0° axis (right side)
      const tickY = centerY;

      // Tick mark (vertical line)
      const tick = document.createElementNS(svgNS, 'line');
      tick.setAttribute('x1', tickX);
      tick.setAttribute('y1', tickY - tickLength);
      tick.setAttribute('x2', tickX);
      tick.setAttribute('y2', tickY + tickLength);
      tick.setAttribute('stroke', catppuccin.overlay0);
      tick.setAttribute('stroke-width', '1');
      tick.setAttribute('class', 'radar-chart__tick');
      tickGroup.appendChild(tick);

      // Tick label — interpolate between rangeMin and rangeMax. In bipolar
      // mode we show signed values (`-40`, `0`, `+40`) so the direction of
      // each radial position is unambiguous.
      const rawValue = rangeMin + valueSpan * level;
      const tickValue = Math.round(rawValue);
      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', tickX);
      label.setAttribute('y', tickY - tickLabelOffset);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', catppuccin.overlay0);
      label.setAttribute('font-size', '9');
      label.setAttribute('font-family', 'JetBrains Mono, Fira Code, IBM Plex Mono, monospace');
      label.setAttribute('class', 'radar-chart__tick-label');
      label.textContent = bipolar && tickValue > 0 ? `+${tickValue}` : tickValue.toString();
      tickGroup.appendChild(label);
    });

    // Calculate data-point coordinates for each series. Values map through
    // `toRadiusFraction` so they respect both the bipolar shift and the
    // clamping at the chart's outer ring.
    const showTarget = hasSeriesData(targetData, bipolar);
    const showCurrent = hasSeriesData(currentData, bipolar);
    const showPostPlan = hasSeriesData(postPlanData, bipolar);

    const targetPoints = [];
    const currentPoints = [];
    const postPlanPoints = [];

    coordinates.forEach((coord, i) => {
      const targetValue = toRadiusFraction(targetData[i] ?? 0);
      const currentValue = toRadiusFraction(currentData[i] ?? 0);
      const postPlanValue = postPlanData[i] !== undefined ? toRadiusFraction(postPlanData[i]) : 0;

      // Calculate radius for each point based on normalized value
      const targetRadius = radius * targetValue;
      const currentRadius = radius * currentValue;
      const postPlanRadius = radius * postPlanValue;

      // Calculate x,y coordinates for each point
      targetPoints.push({
        x: centerX + targetRadius * Math.cos(coord.angle),
        y: centerY + targetRadius * Math.sin(coord.angle)
      });

      currentPoints.push({
        x: centerX + currentRadius * Math.cos(coord.angle),
        y: centerY + currentRadius * Math.sin(coord.angle)
      });

      postPlanPoints.push({
        x: centerX + postPlanRadius * Math.cos(coord.angle),
        y: centerY + postPlanRadius * Math.sin(coord.angle)
      });
    });

    // Draw Current dataset (filled polygon + solid polyline)
    // Green color indicates current allocation
    if (showCurrent && currentPoints.length > 0) {
      // Filled polygon for area visualization
      const currentPolygon = document.createElementNS(svgNS, 'polygon');
      const currentPolygonPoints = currentPoints.map(p => `${p.x},${p.y}`).join(' ');
      currentPolygon.setAttribute('points', currentPolygonPoints);
      currentPolygon.setAttribute('fill', catppuccin.green);
      currentPolygon.setAttribute('fill-opacity', '0.2');
      currentPolygon.setAttribute('stroke', 'none');
      currentPolygon.setAttribute('class', 'radar-chart__current-polygon');
      dataGroup.appendChild(currentPolygon);

      // Solid polyline connecting all points
      const currentPolyline = document.createElementNS(svgNS, 'polyline');
      const currentPolylinePoints = [...currentPoints, currentPoints[0]].map(p => `${p.x},${p.y}`).join(' ');  // Close polygon
      currentPolyline.setAttribute('points', currentPolylinePoints);
      currentPolyline.setAttribute('fill', 'none');
      currentPolyline.setAttribute('stroke', catppuccin.green);
      currentPolyline.setAttribute('stroke-opacity', '0.8');
      currentPolyline.setAttribute('stroke-width', '2');
      currentPolyline.setAttribute('class', 'radar-chart__current-line');
      dataGroup.appendChild(currentPolyline);

      // Data point markers (circles)
      currentPoints.forEach(point => {
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', catppuccin.green);
        circle.setAttribute('fill-opacity', '0.8');
        circle.setAttribute('class', 'radar-chart__current-point');
        dataGroup.appendChild(circle);
      });
    }

    // Draw Target dataset (dashed polyline)
    // Blue dashed line indicates target allocation
    if (showTarget && targetPoints.length > 0) {
      const targetPolyline = document.createElementNS(svgNS, 'polyline');
      const targetPolylinePoints = [...targetPoints, targetPoints[0]].map(p => `${p.x},${p.y}`).join(' ');  // Close polygon
      targetPolyline.setAttribute('points', targetPolylinePoints);
      targetPolyline.setAttribute('fill', 'none');
      targetPolyline.setAttribute('stroke', catppuccin.blue);
      targetPolyline.setAttribute('stroke-opacity', '0.8');
      targetPolyline.setAttribute('stroke-width', '2');
      targetPolyline.setAttribute('stroke-dasharray', '5,5');  // Dashed line
      targetPolyline.setAttribute('class', 'radar-chart__target-line');
      dataGroup.appendChild(targetPolyline);

      // Data point markers (circles)
      targetPoints.forEach(point => {
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', catppuccin.blue);
        circle.setAttribute('fill-opacity', '0.8');
        circle.setAttribute('class', 'radar-chart__target-point');
        dataGroup.appendChild(circle);
      });
    }

    // Draw Post-Plan dataset (dashed polyline)
    // Yellow dashed line indicates post-plan allocation
    if (showPostPlan && postPlanPoints.length > 0) {
      const postPlanPolyline = document.createElementNS(svgNS, 'polyline');
      const postPlanPolylinePoints = [...postPlanPoints, postPlanPoints[0]].map(p => `${p.x},${p.y}`).join(' ');  // Close polygon
      postPlanPolyline.setAttribute('points', postPlanPolylinePoints);
      postPlanPolyline.setAttribute('fill', 'none');
      postPlanPolyline.setAttribute('stroke', catppuccin.yellow);
      postPlanPolyline.setAttribute('stroke-opacity', '0.8');
      postPlanPolyline.setAttribute('stroke-width', '2');
      postPlanPolyline.setAttribute('stroke-dasharray', '5,5');  // Dashed line
      postPlanPolyline.setAttribute('class', 'radar-chart__postplan-line');
      dataGroup.appendChild(postPlanPolyline);

      // Data point markers (circles)
      postPlanPoints.forEach(point => {
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', catppuccin.yellow);
        circle.setAttribute('fill-opacity', '0.8');
        circle.setAttribute('class', 'radar-chart__postplan-point');
        dataGroup.appendChild(circle);
      });
    }

    // Draw axis labels (geography/industry names) outside the chart area.
    // Long names are truncated with an ellipsis so they don't overflow the
    // card; the full name lives in a `<title>` child element for hover.
    // 18 chars fits most TRBC industry names (e.g. "Aerospace & Defense"
    // = 19 chars, just over the line — still readable when ellipsized).
    const labelOffset = 20;
    const maxLabelChars = 18;
    coordinates.forEach((coord, i) => {
      const labelX = coord.x + labelOffset * Math.cos(coord.angle);
      const labelY = coord.y + labelOffset * Math.sin(coord.angle);
      const fullText = labels[i] ?? '';
      const displayText =
        fullText.length > maxLabelChars ? `${fullText.slice(0, maxLabelChars - 1)}…` : fullText;

      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', labelX);
      label.setAttribute('y', labelY);
      label.setAttribute('text-anchor', coord.x > centerX ? 'start' : coord.x < centerX ? 'end' : 'middle');
      label.setAttribute('dominant-baseline', 'middle');
      label.setAttribute('fill', catppuccin.text);
      label.setAttribute('font-size', '10');
      label.setAttribute('font-family', 'JetBrains Mono, Fira Code, IBM Plex Mono, monospace');
      label.setAttribute('class', 'radar-chart__point-label');
      label.appendChild(document.createTextNode(displayText));
      // Native tooltip on hover — only worth attaching when we actually
      // truncated, so the unchanged labels don't get a redundant overlay.
      if (displayText !== fullText) {
        const title = document.createElementNS(svgNS, 'title');
        title.textContent = fullText;
        label.appendChild(title);
      }
      labelGroup.appendChild(label);
    });

    // Legend at bottom of chart — only entries with actual data are drawn.
    // Items are centered as a group so a one-line legend doesn't sit lopsided.
    const legendY = 480;
    const legendItems = [];
    if (showTarget) legendItems.push({ label: targetLabel, color: catppuccin.blue, dashed: true });
    if (showCurrent) legendItems.push({ label: currentLabel, color: catppuccin.green, dashed: false });
    if (showPostPlan) legendItems.push({ label: postPlanLabel, color: catppuccin.yellow, dashed: true });

    const swatchWidth = 20;
    const swatchTextGap = 5;
    const itemGap = 18;
    const charWidth = 6; // approximate per-character width at 10px monospace

    const widths = legendItems.map((it) => swatchWidth + swatchTextGap + it.label.length * charWidth);
    const totalWidth = widths.reduce((a, w) => a + w, 0) + Math.max(0, legendItems.length - 1) * itemGap;
    let cursorX = centerX - totalWidth / 2;

    legendItems.forEach((item, idx) => {
      const line = document.createElementNS(svgNS, 'line');
      line.setAttribute('x1', cursorX);
      line.setAttribute('y1', legendY);
      line.setAttribute('x2', cursorX + swatchWidth);
      line.setAttribute('y2', legendY);
      line.setAttribute('stroke', item.color);
      line.setAttribute('stroke-opacity', '0.8');
      line.setAttribute('stroke-width', '2');
      if (item.dashed) line.setAttribute('stroke-dasharray', '5,5');
      legendGroup.appendChild(line);

      const text = document.createElementNS(svgNS, 'text');
      text.setAttribute('x', cursorX + swatchWidth + swatchTextGap);
      text.setAttribute('y', legendY);
      text.setAttribute('dominant-baseline', 'middle');
      text.setAttribute('fill', catppuccin.subtext0);
      text.setAttribute('font-size', '10');
      text.setAttribute('font-family', 'JetBrains Mono, Fira Code, IBM Plex Mono, monospace');
      text.textContent = item.label;
      legendGroup.appendChild(text);

      cursorX += widths[idx] + itemGap;
    });

    // Append all groups to SVG in render order (background to foreground)
    svgRef.current.appendChild(gridGroup);      // Grid circles (background)
    svgRef.current.appendChild(radialGroup);    // Radial lines
    svgRef.current.appendChild(tickGroup);       // Tick marks and labels
    svgRef.current.appendChild(dataGroup);      // Data polygons and lines
    svgRef.current.appendChild(labelGroup);      // Point labels
    svgRef.current.appendChild(legendGroup);    // Legend (foreground)
  }, [labels, targetData, currentData, postPlanData, maxValue, minValue, balanceValue, targetLabel, currentLabel, postPlanLabel]);

  return (
    <div className="radar-chart" style={{ position: 'relative', width: '100%', aspectRatio: '1' }}>
      {/* SVG container with fixed viewBox for consistent scaling */}
      <svg
        className="radar-chart__svg"
        ref={svgRef}
        viewBox="0 0 500 500"
        style={{ width: '100%', height: '100%' }}
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
}
