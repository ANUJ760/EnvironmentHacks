import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';

export interface ModelContract {
  id: string;
  version: string;
  required_inputs: string[];
  evidence_class: string;
  available: boolean;
  additional_user_inputs: string[];
}

export interface ModelsResponse {
  models: ModelContract[];
  unavailable_models: Array<{ id: string; reason_code: string }>;
}

export function useModels(cityId?: string) {
  return useQuery({
    queryKey: queryKeys.models.forCity(cityId),
    queryFn: async () => {
      const url = `/api/gateway/v1/models${cityId ? `?city_id=${cityId}` : ''}`;
      const { data } = await fetchGateway<ModelsResponse>(url);
      return data;
    },
    staleTime: 30 * 60 * 1000,
  });
}
