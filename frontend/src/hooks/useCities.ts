import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';
import type { components } from '@/lib/api/api-types';

export type CityView = components['schemas']['CityView'];

export function useCities(cursor?: string, limit: number = 20) {
  return useQuery({
    queryKey: queryKeys.cities.list(cursor, limit),
    queryFn: async () => {
      const url = `/api/gateway/v1/cities?limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`;
      const { data } = await fetchGateway<CityView[]>(url);
      return data;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useCity(cityId?: string) {
  return useQuery({
    queryKey: queryKeys.cities.detail(cityId || ''),
    queryFn: async () => {
      if (!cityId) throw new Error('City ID required');
      const { data } = await fetchGateway<CityView>(`/api/gateway/v1/cities/${cityId}`);
      return data;
    },
    enabled: !!cityId,
    staleTime: 10 * 60 * 1000,
  });
}
