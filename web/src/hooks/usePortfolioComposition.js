import { useQuery } from '@tanstack/react-query';
import { getPortfolioComposition } from '../api/client';

/**
 * Portfolio composition + risk/return metrics from /api/portfolio/composition.
 *
 * Live computation on the server (no cache there), but quotes/snapshots are
 * stable on a per-day cadence, so we refetch every 5 min on the client to
 * pick up new positions or settled prices without hammering the endpoint.
 */
export function usePortfolioComposition() {
  return useQuery({
    queryKey: ['portfolio-composition'],
    queryFn: getPortfolioComposition,
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
    staleTime: 60 * 1000,
  });
}
