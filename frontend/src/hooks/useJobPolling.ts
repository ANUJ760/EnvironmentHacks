import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';
import { useScenarioStore } from '@/stores/scenarioStore';
import type { components } from '@/lib/api/api-types';

export type JobView = components['schemas']['JobView'];

export function useJobPolling(jobId: string | null) {
  const setState = useScenarioStore((s) => s.setState);

  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId || ''),
    queryFn: async () => {
      if (!jobId) throw new Error('Job ID required');
      const { data } = await fetchGateway<JobView>(`/api/gateway/v1/jobs/${jobId}`);

      const stateUpper = (data.state || '').toUpperCase();
      if (stateUpper === 'RUNNING') {
        setState('running');
      } else if (stateUpper === 'SUCCEEDED' || stateUpper === 'COMPLETED') {
        setState('succeeded');
      } else if (stateUpper === 'FAILED') {
        setState('failed');
      } else if (stateUpper === 'CANCELED') {
        setState('canceled');
      }

      return data;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const stateUpper = (query.state.data?.state || '').toUpperCase();
      if (['SUCCEEDED', 'COMPLETED', 'FAILED', 'CANCELED'].includes(stateUpper)) {
        return false;
      }
      return 2000; // Poll every 2 seconds while active
    },
    refetchIntervalInBackground: false,
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (jobId: string) => {
      const { data } = await fetchGateway(`/api/gateway/v1/jobs/${jobId}/cancel`, {
        method: 'POST',
      });
      return data;
    },
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.detail(jobId) });
    },
  });
}
