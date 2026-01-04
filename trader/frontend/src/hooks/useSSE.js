import { useEffect, useRef } from 'react';

/**
 * Hook for Server-Sent Events (SSE)
 * @param {string} url - SSE endpoint URL
 * @param {Function} onMessage - Callback for message events
 * @param {Function} onError - Optional error callback
 */
export function useSSE(url, onMessage, onError) {
  const eventSourceRef = useRef(null);

  useEffect(() => {
    if (!url) return;

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (e) {
        console.error('Failed to parse SSE message:', e);
        if (onError) onError(e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE stream error:', error);
      if (onError) onError(error);
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [url, onMessage, onError]);
}
