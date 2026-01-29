/**
 * Build a smooth SVG path through the given points using quadratic curves.
 * @param {Array<{x: number, y: number}>} pts - Array of points
 * @returns {string} SVG path data string
 */
export function buildSmoothPath(pts) {
  if (pts.length < 2) return '';

  let d = `M ${pts[0].x},${pts[0].y}`;

  if (pts.length === 2) {
    d += ` L ${pts[1].x},${pts[1].y}`;
  } else {
    for (let i = 1; i < pts.length - 1; i++) {
      const xc = (pts[i].x + pts[i + 1].x) / 2;
      const yc = (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q ${pts[i].x},${pts[i].y} ${xc},${yc}`;
    }
    const last = pts[pts.length - 1];
    const prev = pts[pts.length - 2];
    d += ` Q ${prev.x},${prev.y} ${last.x},${last.y}`;
  }

  return d;
}
