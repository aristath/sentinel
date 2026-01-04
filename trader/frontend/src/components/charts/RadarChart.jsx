import { useEffect, useRef } from 'react';

/**
 * Radar Chart Component
 * SVG-based radar chart that displays Target and Current datasets
 */
export function RadarChart({ labels = [], targetData = [], currentData = [], maxValue = null }) {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!svgRef.current) return;

    // Validate data
    if (!labels || labels.length === 0) {
      svgRef.current.innerHTML = '';
      return;
    }

    if (targetData.length !== labels.length || currentData.length !== labels.length) {
      console.warn('RadarChart: Data length mismatch');
      return;
    }

    // Calculate max value if not provided
    const allValues = [...targetData, ...currentData];
    let maxVal = maxValue;
    if (!maxVal || maxVal <= 0) {
      maxVal = allValues.length > 0 ? Math.max(...allValues) : 100;
    }

    // Add 25% padding and round to nearest step of 25
    const paddedMax = Math.ceil(maxVal * 1.25);
    const roundedMax = Math.ceil(paddedMax / 25) * 25;

    // Constants
    const centerX = 250;
    const centerY = 250;
    const radius = 180;
    const numPoints = labels.length;

    // Clear previous content
    svgRef.current.innerHTML = '';

    // Create SVG namespace
    const svgNS = 'http://www.w3.org/2000/svg';

    // Create groups
    const gridGroup = document.createElementNS(svgNS, 'g');
    gridGroup.setAttribute('class', 'grid');

    const radialGroup = document.createElementNS(svgNS, 'g');
    radialGroup.setAttribute('class', 'radial-lines');

    const tickGroup = document.createElementNS(svgNS, 'g');
    tickGroup.setAttribute('class', 'ticks');

    const dataGroup = document.createElementNS(svgNS, 'g');
    dataGroup.setAttribute('class', 'data');

    const labelGroup = document.createElementNS(svgNS, 'g');
    labelGroup.setAttribute('class', 'labels');

    const legendGroup = document.createElementNS(svgNS, 'g');
    legendGroup.setAttribute('class', 'legend');

    // Draw grid circles (5 levels: 0%, 25%, 50%, 75%, 100%)
    for (let i = 0; i <= 4; i++) {
      const level = i / 4;
      const circleRadius = radius * level;
      const circle = document.createElementNS(svgNS, 'circle');
      circle.setAttribute('cx', centerX);
      circle.setAttribute('cy', centerY);
      circle.setAttribute('r', circleRadius);
      circle.setAttribute('fill', 'none');
      circle.setAttribute('stroke', '#374151');
      circle.setAttribute('stroke-width', '1');
      gridGroup.appendChild(circle);
    }

    // Calculate angles and coordinates for each point
    const angles = [];
    const coordinates = [];

    for (let i = 0; i < numPoints; i++) {
      const angle = (360 / numPoints) * i - 90;
      const angleRad = (angle * Math.PI) / 180;
      angles.push(angleRad);

      const x = centerX + radius * Math.cos(angleRad);
      const y = centerY + radius * Math.sin(angleRad);
      coordinates.push({ x, y, angle: angleRad });
    }

    // Draw radial lines from center to each point
    coordinates.forEach(coord => {
      const line = document.createElementNS(svgNS, 'line');
      line.setAttribute('x1', centerX);
      line.setAttribute('y1', centerY);
      line.setAttribute('x2', coord.x);
      line.setAttribute('y2', coord.y);
      line.setAttribute('stroke', '#374151');
      line.setAttribute('stroke-width', '1');
      radialGroup.appendChild(line);
    });

    // Draw tick marks and labels on top radial line (0°)
    const tickLevels = [0, 0.25, 0.5, 0.75, 1.0];
    const tickLength = 5;
    const tickLabelOffset = 15;

    tickLevels.forEach((level) => {
      const tickRadius = radius * level;
      const tickX = centerX + tickRadius;
      const tickY = centerY;

      // Tick mark
      const tick = document.createElementNS(svgNS, 'line');
      tick.setAttribute('x1', tickX);
      tick.setAttribute('y1', tickY - tickLength);
      tick.setAttribute('x2', tickX);
      tick.setAttribute('y2', tickY + tickLength);
      tick.setAttribute('stroke', '#6B7280');
      tick.setAttribute('stroke-width', '1');
      tickGroup.appendChild(tick);

      // Tick label
      const tickValue = Math.round(roundedMax * level);
      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', tickX);
      label.setAttribute('y', tickY - tickLabelOffset);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#6B7280');
      label.setAttribute('font-size', '9');
      label.setAttribute('font-family', 'system-ui, sans-serif');
      label.textContent = tickValue.toString();
      tickGroup.appendChild(label);
    });

    // Calculate data point coordinates
    const targetPoints = [];
    const currentPoints = [];

    coordinates.forEach((coord, i) => {
      const targetValue = Math.max(0, Math.min(targetData[i] / roundedMax, 1));
      const currentValue = Math.max(0, Math.min(currentData[i] / roundedMax, 1));

      const targetRadius = radius * targetValue;
      const currentRadius = radius * currentValue;

      targetPoints.push({
        x: centerX + targetRadius * Math.cos(coord.angle),
        y: centerY + targetRadius * Math.sin(coord.angle)
      });

      currentPoints.push({
        x: centerX + currentRadius * Math.cos(coord.angle),
        y: centerY + currentRadius * Math.sin(coord.angle)
      });
    });

    // Draw Current dataset (filled polygon + solid polyline)
    if (currentPoints.length > 0) {
      const currentPolygon = document.createElementNS(svgNS, 'polygon');
      const currentPolygonPoints = currentPoints.map(p => `${p.x},${p.y}`).join(' ');
      currentPolygon.setAttribute('points', currentPolygonPoints);
      currentPolygon.setAttribute('fill', 'rgba(34, 197, 94, 0.2)');
      currentPolygon.setAttribute('stroke', 'none');
      dataGroup.appendChild(currentPolygon);

      const currentPolyline = document.createElementNS(svgNS, 'polyline');
      const currentPolylinePoints = [...currentPoints, currentPoints[0]].map(p => `${p.x},${p.y}`).join(' ');
      currentPolyline.setAttribute('points', currentPolylinePoints);
      currentPolyline.setAttribute('fill', 'none');
      currentPolyline.setAttribute('stroke', 'rgba(34, 197, 94, 0.8)');
      currentPolyline.setAttribute('stroke-width', '2');
      dataGroup.appendChild(currentPolyline);

      currentPoints.forEach(point => {
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', 'rgba(34, 197, 94, 0.8)');
        dataGroup.appendChild(circle);
      });
    }

    // Draw Target dataset (dashed polyline)
    if (targetPoints.length > 0) {
      const targetPolyline = document.createElementNS(svgNS, 'polyline');
      const targetPolylinePoints = [...targetPoints, targetPoints[0]].map(p => `${p.x},${p.y}`).join(' ');
      targetPolyline.setAttribute('points', targetPolylinePoints);
      targetPolyline.setAttribute('fill', 'none');
      targetPolyline.setAttribute('stroke', 'rgba(59, 130, 246, 0.8)');
      targetPolyline.setAttribute('stroke-width', '2');
      targetPolyline.setAttribute('stroke-dasharray', '5,5');
      dataGroup.appendChild(targetPolyline);

      targetPoints.forEach(point => {
        const circle = document.createElementNS(svgNS, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', 'rgba(59, 130, 246, 0.8)');
        dataGroup.appendChild(circle);
      });
    }

    // Draw point labels (geography/industry names) outside chart area
    const labelOffset = 20;
    coordinates.forEach((coord, i) => {
      const labelX = coord.x + labelOffset * Math.cos(coord.angle);
      const labelY = coord.y + labelOffset * Math.sin(coord.angle);

      const label = document.createElementNS(svgNS, 'text');
      label.setAttribute('x', labelX);
      label.setAttribute('y', labelY);
      label.setAttribute('text-anchor', coord.x > centerX ? 'start' : coord.x < centerX ? 'end' : 'middle');
      label.setAttribute('dominant-baseline', 'middle');
      label.setAttribute('fill', '#D1D5DB');
      label.setAttribute('font-size', '10');
      label.setAttribute('font-family', 'system-ui, sans-serif');
      label.textContent = labels[i];
      labelGroup.appendChild(label);
    });

    // Draw legend at bottom
    const legendY = 480;
    const legendX = centerX;

    // Target legend item
    const targetLegendLine = document.createElementNS(svgNS, 'line');
    targetLegendLine.setAttribute('x1', legendX - 60);
    targetLegendLine.setAttribute('y1', legendY);
    targetLegendLine.setAttribute('x2', legendX - 40);
    targetLegendLine.setAttribute('y2', legendY);
    targetLegendLine.setAttribute('stroke', 'rgba(59, 130, 246, 0.8)');
    targetLegendLine.setAttribute('stroke-width', '2');
    targetLegendLine.setAttribute('stroke-dasharray', '5,5');
    legendGroup.appendChild(targetLegendLine);

    const targetLegendText = document.createElementNS(svgNS, 'text');
    targetLegendText.setAttribute('x', legendX - 35);
    targetLegendText.setAttribute('y', legendY);
    targetLegendText.setAttribute('dominant-baseline', 'middle');
    targetLegendText.setAttribute('fill', '#9CA3AF');
    targetLegendText.setAttribute('font-size', '10');
    targetLegendText.setAttribute('font-family', 'system-ui, sans-serif');
    targetLegendText.textContent = 'Target';
    legendGroup.appendChild(targetLegendText);

    // Current legend item
    const currentLegendLine = document.createElementNS(svgNS, 'line');
    currentLegendLine.setAttribute('x1', legendX + 10);
    currentLegendLine.setAttribute('y1', legendY);
    currentLegendLine.setAttribute('x2', legendX + 30);
    currentLegendLine.setAttribute('y2', legendY);
    currentLegendLine.setAttribute('stroke', 'rgba(34, 197, 94, 0.8)');
    currentLegendLine.setAttribute('stroke-width', '2');
    legendGroup.appendChild(currentLegendLine);

    const currentLegendText = document.createElementNS(svgNS, 'text');
    currentLegendText.setAttribute('x', legendX + 35);
    currentLegendText.setAttribute('y', legendY);
    currentLegendText.setAttribute('dominant-baseline', 'middle');
    currentLegendText.setAttribute('fill', '#9CA3AF');
    currentLegendText.setAttribute('font-size', '10');
    currentLegendText.setAttribute('font-family', 'system-ui, sans-serif');
    currentLegendText.textContent = 'Current';
    legendGroup.appendChild(currentLegendText);

    // Append all groups to SVG
    svgRef.current.appendChild(gridGroup);
    svgRef.current.appendChild(radialGroup);
    svgRef.current.appendChild(tickGroup);
    svgRef.current.appendChild(dataGroup);
    svgRef.current.appendChild(labelGroup);
    svgRef.current.appendChild(legendGroup);
  }, [labels, targetData, currentData, maxValue]);

  return (
    <div style={{ position: 'relative', width: '100%', aspectRatio: '1' }}>
      <svg
        ref={svgRef}
        viewBox="0 0 500 500"
        style={{ width: '100%', height: '100%' }}
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
}

