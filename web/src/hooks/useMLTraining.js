/**
 * useMLTraining Hook
 *
 * Manages ML training status, training (via SSE stream), and deletion
 * for a single security symbol.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMLTrainingStatus, deleteMLTrainingData, getMLTrainStreamUrl } from '../api/client';

export function useMLTraining(symbol, { enabled = false } = {}) {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef(null);

  const [isTraining, setIsTraining] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState(null);

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['ml-training-status', symbol],
    queryFn: () => getMLTrainingStatus(symbol),
    enabled: !!symbol && enabled,
  });

  // Cleanup event source on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const train = useCallback(() => {
    setIsTraining(true);
    setProgress(0);
    setMessage('Starting...');
    setError(null);

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(getMLTrainStreamUrl(symbol));
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.error) {
        setError(data.error);
        setIsTraining(false);
        eventSource.close();
        return;
      }

      setProgress(data.progress || 0);
      setMessage(data.message || '');

      if (data.complete) {
        setIsTraining(false);
        queryClient.setQueryData(['ml-training-status', symbol], {
          model_exists: true,
          model_info: data.metrics,
        });
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      setError('Connection lost');
      setIsTraining(false);
      eventSource.close();
    };
  }, [symbol, queryClient]);

  const deleteMutation = useMutation({
    mutationFn: () => deleteMLTrainingData(symbol),
    onSuccess: () => {
      queryClient.setQueryData(['ml-training-status', symbol], {
        model_exists: false,
        sample_count: 0,
      });
    },
    onError: () => {
      setError('Failed to delete training data');
    },
  });

  return {
    status,
    train,
    isTraining,
    progress,
    message,
    error,
    setError,
    deleteTraining: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
  };
}
