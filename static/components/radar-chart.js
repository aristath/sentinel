/**
 * Reusable Radar Chart Component
 * SVG-based radar chart that displays Target and Current datasets
 * 
 * Attributes (via Alpine.js :bind):
 * - :labels - Array of label strings (required)
 * - :target-data - Array of target values (required)
 * - :current-data - Array of current values (required)
 * - :max-value - Maximum value for scaling (optional, auto-calculated)
 */
class RadarChart extends HTMLElement {
  constructor() {
    super();
    this.labels = [];
    this.targetData = [];
    this.currentData = [];
    this.maxValue = null;
    this.svg = null;
  }

  connectedCallback() {
    // Create SVG container
    this.innerHTML = `
      <div class="relative w-full" style="aspect-ratio: 1;">
        <svg viewBox="0 0 400 400" class="w-full h-full" preserveAspectRatio="xMidYMid meet">
          <!-- SVG content will be rendered here -->
        </svg>
      </div>
    `;
    
    this.svg = this.querySelector('svg');
    
    // Set up Alpine.js reactive bindings
    this.setupAlpineBindings();
    
    // Initial render
    this.render();
  }

  setupAlpineBindings() {
    // For Alpine.js integration, watch for changes to data-* attributes
    // that Alpine sets via x-bind:data-* syntax
    const observer = new MutationObserver((mutations) => {
      let shouldUpdate = false;
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes') {
          shouldUpdate = true;
        }
      });
      if (shouldUpdate) {
        this.updateFromAttributes();
      }
    });
    
    observer.observe(this, {
      attributes: true,
      attributeFilter: ['data-labels', 'data-target-data', 'data-current-data', 'data-max-value']
    });
    
    // Initial update after a short delay to allow Alpine to set initial values
    setTimeout(() => {
      this.updateFromAttributes();
    }, 10);
  }

  updateFromAttributes() {
    // Get data from data-* attributes (set by Alpine x-bind:data-*)
    const labelsAttr = this.getAttribute('data-labels');
    const targetAttr = this.getAttribute('data-target-data');
    const currentAttr = this.getAttribute('data-current-data');
    const maxAttr = this.getAttribute('data-max-value');

    let updated = false;
    
    try {
      if (labelsAttr !== null && labelsAttr !== '') {
        const parsed = this.parseAttribute(labelsAttr);
        if (parsed !== null && Array.isArray(parsed)) {
          this.labels = parsed;
          updated = true;
        }
      }
      if (targetAttr !== null && targetAttr !== '') {
        const parsed = this.parseAttribute(targetAttr);
        if (parsed !== null && Array.isArray(parsed)) {
          this.targetData = parsed;
          updated = true;
        }
      }
      if (currentAttr !== null && currentAttr !== '') {
        const parsed = this.parseAttribute(currentAttr);
        if (parsed !== null && Array.isArray(parsed)) {
          this.currentData = parsed;
          updated = true;
        }
      }
      if (maxAttr !== null && maxAttr !== '') {
        const parsed = this.parseAttribute(maxAttr);
        if (parsed !== null && (typeof parsed === 'number' || !isNaN(parsed))) {
          this.maxValue = typeof parsed === 'number' ? parsed : parseFloat(parsed);
          updated = true;
        }
      }
      
      if (updated && this.labels.length > 0) {
        this.render();
      }
    } catch (e) {
      console.warn('RadarChart: Error parsing attributes', e);
    }
  }

  parseAttribute(value) {
    // Handle JSON strings or direct values
    if (typeof value === 'string') {
      try {
        return JSON.parse(value);
      } catch {
        // Not JSON, return as-is (might be a string value)
        return value;
      }
    }
    return value;
  }

  // Public method to update data programmatically
  updateData(labels, targetData, currentData, maxValue = null) {
    this.labels = labels || [];
    this.targetData = targetData || [];
    this.currentData = currentData || [];
    this.maxValue = maxValue;
    this.render();
  }

  render() {
    if (!this.svg) return;

    // Validate data
    if (!this.labels || this.labels.length === 0) {
      this.svg.innerHTML = '';
      return;
    }

    if (this.targetData.length !== this.labels.length || 
        this.currentData.length !== this.labels.length) {
      console.warn('RadarChart: Data length mismatch');
      return;
    }

    // Calculate max value if not provided
    const allValues = [...this.targetData, ...this.currentData];
    let maxVal = this.maxValue;
    if (!maxVal || maxVal <= 0) {
      maxVal = allValues.length > 0 ? Math.max(...allValues) : 100;
    }

    // Add 25% padding and round to nearest step of 25
    const paddedMax = Math.ceil(maxVal * 1.25);
    const roundedMax = Math.ceil(paddedMax / 25) * 25;

    // Constants
    const centerX = 200;
    const centerY = 200;
    const radius = 180;
    const numPoints = this.labels.length;

    // Clear previous content
    this.svg.innerHTML = '';

    // Create groups for organization
    const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    gridGroup.setAttribute('class', 'grid');
    
    const radialGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    radialGroup.setAttribute('class', 'radial-lines');
    
    const tickGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    tickGroup.setAttribute('class', 'ticks');
    
    const dataGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    dataGroup.setAttribute('class', 'data');
    
    const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    labelGroup.setAttribute('class', 'labels');
    
    const legendGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    legendGroup.setAttribute('class', 'legend');

    // Draw grid circles (5 levels: 0%, 25%, 50%, 75%, 100%)
    for (let i = 0; i <= 4; i++) {
      const level = i / 4;
      const circleRadius = radius * level;
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
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
      // Start at top (90 degrees offset), go clockwise
      const angle = (360 / numPoints) * i - 90;
      const angleRad = (angle * Math.PI) / 180;
      angles.push(angleRad);
      
      const x = centerX + radius * Math.cos(angleRad);
      const y = centerY + radius * Math.sin(angleRad);
      coordinates.push({ x, y, angle: angleRad });
    }

    // Draw radial lines from center to each point
    coordinates.forEach(coord => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
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
    
    tickLevels.forEach((level, i) => {
      const tickRadius = radius * level;
      const tickX = centerX + tickRadius;
      const tickY = centerY;
      
      // Tick mark
      const tick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      tick.setAttribute('x1', tickX);
      tick.setAttribute('y1', tickY - tickLength);
      tick.setAttribute('x2', tickX);
      tick.setAttribute('y2', tickY + tickLength);
      tick.setAttribute('stroke', '#6B7280');
      tick.setAttribute('stroke-width', '1');
      tickGroup.appendChild(tick);
      
      // Tick label
      const tickValue = Math.round(roundedMax * level);
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
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
      // Normalize values to 0-1 range based on roundedMax
      const targetValue = Math.max(0, Math.min(this.targetData[i] / roundedMax, 1));
      const currentValue = Math.max(0, Math.min(this.currentData[i] / roundedMax, 1));
      
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
      // Filled polygon
      const currentPolygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      const currentPolygonPoints = currentPoints.map(p => `${p.x},${p.y}`).join(' ');
      currentPolygon.setAttribute('points', currentPolygonPoints);
      currentPolygon.setAttribute('fill', 'rgba(34, 197, 94, 0.2)');
      currentPolygon.setAttribute('stroke', 'none');
      dataGroup.appendChild(currentPolygon);
      
      // Solid border
      const currentPolyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      const currentPolylinePoints = [...currentPoints, currentPoints[0]].map(p => `${p.x},${p.y}`).join(' ');
      currentPolyline.setAttribute('points', currentPolylinePoints);
      currentPolyline.setAttribute('fill', 'none');
      currentPolyline.setAttribute('stroke', 'rgba(34, 197, 94, 0.8)');
      currentPolyline.setAttribute('stroke-width', '2');
      dataGroup.appendChild(currentPolyline);
      
      // Points
      currentPoints.forEach(point => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', '3');
        circle.setAttribute('fill', 'rgba(34, 197, 94, 0.8)');
        dataGroup.appendChild(circle);
      });
    }

    // Draw Target dataset (dashed polyline)
    if (targetPoints.length > 0) {
      const targetPolyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      const targetPolylinePoints = [...targetPoints, targetPoints[0]].map(p => `${p.x},${p.y}`).join(' ');
      targetPolyline.setAttribute('points', targetPolylinePoints);
      targetPolyline.setAttribute('fill', 'none');
      targetPolyline.setAttribute('stroke', 'rgba(59, 130, 246, 0.8)');
      targetPolyline.setAttribute('stroke-width', '2');
      targetPolyline.setAttribute('stroke-dasharray', '5,5');
      dataGroup.appendChild(targetPolyline);
      
      // Points
      targetPoints.forEach(point => {
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
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
      
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', labelX);
      label.setAttribute('y', labelY);
      label.setAttribute('text-anchor', coord.x > centerX ? 'start' : coord.x < centerX ? 'end' : 'middle');
      label.setAttribute('dominant-baseline', 'middle');
      label.setAttribute('fill', '#D1D5DB');
      label.setAttribute('font-size', '10');
      label.setAttribute('font-family', 'system-ui, sans-serif');
      label.textContent = this.labels[i];
      labelGroup.appendChild(label);
    });

    // Draw legend at bottom
    const legendY = 380;
    const legendX = centerX;
    
    // Target legend item
    const targetLegendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    targetLegendLine.setAttribute('x1', legendX - 60);
    targetLegendLine.setAttribute('y1', legendY);
    targetLegendLine.setAttribute('x2', legendX - 40);
    targetLegendLine.setAttribute('y2', legendY);
    targetLegendLine.setAttribute('stroke', 'rgba(59, 130, 246, 0.8)');
    targetLegendLine.setAttribute('stroke-width', '2');
    targetLegendLine.setAttribute('stroke-dasharray', '5,5');
    legendGroup.appendChild(targetLegendLine);
    
    const targetLegendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    targetLegendText.setAttribute('x', legendX - 35);
    targetLegendText.setAttribute('y', legendY);
    targetLegendText.setAttribute('dominant-baseline', 'middle');
    targetLegendText.setAttribute('fill', '#9CA3AF');
    targetLegendText.setAttribute('font-size', '10');
    targetLegendText.setAttribute('font-family', 'system-ui, sans-serif');
    targetLegendText.textContent = 'Target';
    legendGroup.appendChild(targetLegendText);
    
    // Current legend item
    const currentLegendLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    currentLegendLine.setAttribute('x1', legendX + 10);
    currentLegendLine.setAttribute('y1', legendY);
    currentLegendLine.setAttribute('x2', legendX + 30);
    currentLegendLine.setAttribute('y2', legendY);
    currentLegendLine.setAttribute('stroke', 'rgba(34, 197, 94, 0.8)');
    currentLegendLine.setAttribute('stroke-width', '2');
    legendGroup.appendChild(currentLegendLine);
    
    const currentLegendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    currentLegendText.setAttribute('x', legendX + 35);
    currentLegendText.setAttribute('y', legendY);
    currentLegendText.setAttribute('dominant-baseline', 'middle');
    currentLegendText.setAttribute('fill', '#9CA3AF');
    currentLegendText.setAttribute('font-size', '10');
    currentLegendText.setAttribute('font-family', 'system-ui, sans-serif');
    currentLegendText.textContent = 'Current';
    legendGroup.appendChild(currentLegendText);

    // Append all groups to SVG
    this.svg.appendChild(gridGroup);
    this.svg.appendChild(radialGroup);
    this.svg.appendChild(tickGroup);
    this.svg.appendChild(dataGroup);
    this.svg.appendChild(labelGroup);
    this.svg.appendChild(legendGroup);
  }

  // Handle Alpine.js :bind syntax
  static get observedAttributes() {
    return ['data-labels', 'data-target-data', 'data-current-data', 'data-max-value'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue !== newValue) {
      this.updateFromAttributes();
    }
  }
}

customElements.define('radar-chart', RadarChart);

