/**
 * Stock Sparkline Component
 * Custom SVG-based sparkline chart for security table
 */
class StockSparkline extends HTMLElement {
  static get observedAttributes() {
    return ['symbol', 'has-position'];
  }

  connectedCallback() {
    this.render();
    this.setupWatcher();
  }

  attributeChangedCallback() {
    if (this.isConnected) {
      this.render();
    }
  }

  setupWatcher() {
    // Watch for Alpine store updates
    if (typeof Alpine !== 'undefined') {
      Alpine.effect(() => {
        const store = Alpine.store('app');
        if (store && store.sparklines) {
          this.render();
        }
      });
    } else {
      document.addEventListener('alpine:init', () => {
        Alpine.effect(() => {
          const store = Alpine.store('app');
          if (store && store.sparklines) {
            this.render();
          }
        });
      });
    }
  }

  render() {
    const symbol = this.getAttribute('symbol');
    const hasPosition = this.getAttribute('has-position') === 'true';

    if (!symbol) {
      this.innerHTML = '<span class="text-gray-600 text-xs">-</span>';
      return;
    }

    // Get data from Alpine store
    let data = null;
    if (typeof Alpine !== 'undefined') {
      const store = Alpine.store('app');
      if (store && store.sparklines) {
        data = store.sparklines[symbol];
      }
    }

    if (!data || data.length < 2) {
      this.innerHTML = '<span class="text-gray-600 text-xs">-</span>';
      return;
    }

    // Render SVG
    this.innerHTML = this.renderSVG(data, hasPosition, symbol);
  }

  renderSVG(data, hasPosition, symbol) {
    const width = 80;
    const height = 32;
    const padding = 1;

    // Extract values and find min/max
    const values = data.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1; // Avoid division by zero

    // Calculate scaling factors
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Generate path data
    const points = data.map((d, i) => {
      const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
      const y = padding + (1 - (d.value - minValue) / valueRange) * chartHeight;
      return { x, y, value: d.value };
    });

    // Create path for line
    const pathData = points.map((p, i) =>
      i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`
    ).join(' ');

    // Create area path (line + bottom line)
    const firstPoint = points[0];
    const lastPoint = points[points.length - 1];
    const areaPath = `${pathData} L ${lastPoint.x} ${height - padding} L ${firstPoint.x} ${height - padding} Z`;

    if (hasPosition) {
      // Baseline chart: green above baseline, red below
      const baselineValue = data[0].value;
      const baselineY = padding + (1 - (baselineValue - minValue) / valueRange) * chartHeight;

      // Create segments with baseline intersections
      const segments = [];
      let currentSegment = { points: [], type: points[0].value >= baselineValue ? 'above' : 'below' };

      points.forEach((p, i) => {
        const isAbove = p.value >= baselineValue;
        const segmentType = isAbove ? 'above' : 'below';

        if (segmentType !== currentSegment.type && i > 0) {
          // Calculate intersection with baseline
          const prevPoint = points[i - 1];
          const t = (baselineValue - prevPoint.value) / (p.value - prevPoint.value);
          const intersectX = prevPoint.x + t * (p.x - prevPoint.x);
          const intersectY = baselineY;

          // Add intersection point to current segment
          currentSegment.points.push({ x: intersectX, y: intersectY, value: baselineValue });

          // Close current segment and start new one
          segments.push(currentSegment);
          currentSegment = { points: [{ x: intersectX, y: intersectY, value: baselineValue }], type: segmentType };
        }

        currentSegment.points.push(p);
      });

      // Add last segment
      if (currentSegment.points.length > 0) {
        segments.push(currentSegment);
      }

      // Build SVG paths
      const paths = segments.map(seg => {
        if (seg.points.length === 0) return null;

        const pathData = seg.points.map((p, i) =>
          i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`
        ).join(' ');

        // For area: connect line to baseline (not bottom of chart)
        const firstX = seg.points[0].x;
        const lastX = seg.points[seg.points.length - 1].x;
        const areaPath = `${pathData} L ${lastX} ${baselineY} L ${firstX} ${baselineY} Z`;

        const lineColor = seg.type === 'above' ? '#10b981' : '#ef4444';
        const gradientId = seg.type === 'above' ? `gradient-above-${symbol}` : `gradient-below-${symbol}`;

        return { pathData, areaPath, lineColor, gradientId, type: seg.type };
      }).filter(p => p !== null);

      const gradients = [];
      if (paths.some(p => p.type === 'above')) {
        gradients.push(`
          <linearGradient id="gradient-above-${symbol}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#10b981;stop-opacity:0.4" />
            <stop offset="100%" style="stop-color:#10b981;stop-opacity:0.1" />
          </linearGradient>
        `);
      }
      if (paths.some(p => p.type === 'below')) {
        gradients.push(`
          <linearGradient id="gradient-below-${symbol}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#ef4444;stop-opacity:0.1" />
            <stop offset="100%" style="stop-color:#ef4444;stop-opacity:0.4" />
          </linearGradient>
        `);
      }

      const pathElements = paths.map(p => `
        <path d="${p.areaPath}" fill="url(#${p.gradientId})" opacity="0.4"/>
        <path d="${p.pathData}" stroke="${p.lineColor}" stroke-width="1" fill="none" vector-effect="non-scaling-stroke"/>
      `).join('');

      return `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
          <defs>
            ${gradients.join('')}
          </defs>
          ${pathElements}
        </svg>
      `;
    } else {
      // Area chart: blue
      return `
        <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
          <!-- Area fill -->
          <path d="${areaPath}"
                fill="url(#gradient-${symbol})"
                opacity="0.4"/>
          <!-- Line -->
          <path d="${pathData}"
                stroke="#3b82f6"
                stroke-width="1"
                fill="none"
                vector-effect="non-scaling-stroke"/>
          <!-- Gradient -->
          <defs>
            <linearGradient id="gradient-${symbol}" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:0.4" />
              <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0.1" />
            </linearGradient>
          </defs>
        </svg>
      `;
    }
  }
}

customElements.define('security-sparkline', StockSparkline);
