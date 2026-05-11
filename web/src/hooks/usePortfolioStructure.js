import { useQuery } from '@tanstack/react-query';
import { getPortfolioStructure } from '../api/client';

/**
 * Live PRAAMS portfolio analysis from freedom24 (cached server-side for
 * 5 min). The server-side cache is the source of truth for freshness; on
 * the client we just refetch every 5 minutes so newly-set credentials and
 * portfolio changes get picked up without a manual reload.
 */
export function usePortfolioStructure() {
  return useQuery({
    queryKey: ['portfolio-structure'],
    queryFn: () => getPortfolioStructure(),
    // 5-min server cache → match it client-side. retry: 1 because 503 from
    // missing credentials is a common steady state and shouldn't backoff hard.
    refetchInterval: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
    staleTime: 60 * 1000,
  });
}
