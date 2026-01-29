import { useState, useEffect, useRef } from 'react';

/**
 * Hook that tracks the width of a container element using ResizeObserver.
 * @param {number} [defaultWidth=600] - Default width before measurement
 * @returns {[React.RefObject, number]} - Ref to attach to container, current width
 */
export function useResponsiveWidth(defaultWidth = 600) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(defaultWidth);

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const newWidth = entry.contentRect.width;
        if (newWidth > 0) {
          setWidth(newWidth);
        }
      }
    });

    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  return [containerRef, width];
}
