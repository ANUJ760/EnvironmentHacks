import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';
import { useScenarioStore } from '@/stores/scenarioStore';
import { generateUUID } from '@/lib/scenarios';
import { ApiError } from '@/lib/api/problem';
import type { components } from '@/lib/api/api-types';

export type ScenarioView = components['schemas']['ScenarioView'];
export type SimulationRequest = components['schemas']['SimulationRequest'];
export type JobAccepted = components['schemas']['JobAccepted'];

export function useScenario(scenarioId?: string) {
  return useQuery({
    queryKey: queryKeys.scenarios.detail(scenarioId || ''),
    queryFn: async () => {
      if (!scenarioId) throw new Error('Scenario ID required');
      const { data, eTag } = await fetchGateway<ScenarioView>(`/api/gateway/v1/scenarios/${scenarioId}`);
      return { scenario: data, eTag };
    },
    enabled: !!scenarioId,
  });
}

export function useScenarioReports(scenarioId?: string) {
  return useQuery({
    queryKey: queryKeys.scenarios.reports(scenarioId || ''),
    queryFn: async () => {
      if (!scenarioId) throw new Error('Scenario ID required');
      const { data } = await fetchGateway<any[]>(`/api/gateway/v1/scenarios/${scenarioId}/reports`);
      return data;
    },
    enabled: !!scenarioId,
  });
}

export function useCreateScenario() {
  const queryClient = useQueryClient();
  const setScenario = useScenarioStore((s) => s.setScenario);

  return useMutation({
    mutationFn: async ({
      cityId,
      snapshotId,
      name,
    }: {
      cityId: string;
      snapshotId: string;
      name: string;
    }) => {
      const { data, eTag } = await fetchGateway<ScenarioView>('/api/gateway/v1/scenarios', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          city_id: cityId,
          snapshot_id: snapshotId,
          name,
        }),
      });
      return { data, eTag };
    },
    onSuccess: ({ data, eTag }) => {
      setScenario({
        id: data.id,
        name: data.name,
        snapshotId: data.snapshot_id,
        version: data.version,
        eTag,
        edits: (data.edits as any[]) || [],
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.scenarios.all });
    },
  });
}

export function useSaveEdits() {
  const queryClient = useQueryClient();
  const { scenarioId, eTag, edits, setETag, setVersion, setState, setConflict } = useScenarioStore();

  return useMutation({
    mutationFn: async () => {
      if (!scenarioId) throw new Error('No active scenario');
      if (!eTag) throw new Error('ETag required for scenario update');

      setState('saving');

      try {
        const { data, eTag: newETag } = await fetchGateway<ScenarioView>(
          `/api/gateway/v1/scenarios/${scenarioId}/edits`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            eTag,
            body: JSON.stringify({ edits }),
          }
        );
        return { data, eTag: newETag };
      } catch (err) {
        if (err instanceof ApiError && (err.status === 409 || err.status === 412)) {
          // Concurrency conflict: fetch latest server state
          const { data: serverScenario } = await fetchGateway<ScenarioView>(
            `/api/gateway/v1/scenarios/${scenarioId}`
          );
          setConflict({
            serverEdits: serverScenario.edits as any[],
            draftEdits: edits,
          });
        }
        throw err;
      }
    },
    onSuccess: ({ data, eTag: newETag }) => {
      setETag(newETag ?? null);
      setVersion(data.version);
      setState('saved_revision');
      queryClient.invalidateQueries({ queryKey: queryKeys.scenarios.detail(scenarioId!) });
    },
    onError: (err) => {
      if (!(err instanceof ApiError && (err.status === 409 || err.status === 412))) {
        setState('editing_unsaved');
      }
    },
  });
}

export function useSimulateScenario() {
  const { scenarioId, setState, setActiveJobId } = useScenarioStore();

  return useMutation({
    mutationFn: async (req: {
      requested_models: string[];
      event_rainfall_mm?: number | null;
      start_at?: string | null;
      end_at?: string | null;
      optimize_waste?: boolean;
    }) => {
      if (!scenarioId) throw new Error('No active scenario');

      setState('submitting');
      const idempotencyKey = generateUUID();

      const { data } = await fetchGateway<JobAccepted>(
        `/api/gateway/v1/scenarios/${scenarioId}/simulate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          idempotencyKey,
          body: JSON.stringify({
            ...req,
            report_schema_version: 1,
          }),
        }
      );
      return data;
    },
    onSuccess: (job) => {
      setActiveJobId(job.job_id);
      setState('queued');
    },
    onError: () => {
      setState('saved_revision');
    },
  });
}
