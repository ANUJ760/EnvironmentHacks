import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';
import type { components } from '@/lib/api/api-types';

export type ResultView = components['schemas']['ResultView'];
export type Metric = components['schemas']['Metric'];

export function useResult(resultId?: string) {
  return useQuery({
    queryKey: queryKeys.results.detail(resultId || ''),
    queryFn: async () => {
      if (!resultId) throw new Error('Result ID required');
      const { data } = await fetchGateway<ResultView>(`/api/gateway/v1/results/${resultId}`);
      return data;
    },
    enabled: !!resultId,
    staleTime: Infinity, // Immutable simulation results never change
  });
}
