import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/api/query-keys';
import { fetchGateway } from '@/lib/api/browser-client';
import type { components } from '@/lib/api/api-types';

export type FeatureCollection = components['schemas']['FeatureCollection'];
export type LandcoverView = components['schemas']['LandcoverView'];
export type WeatherView = components['schemas']['WeatherView'];
export type AirView = components['schemas']['AirView'];
export type DatasetView = components['schemas']['DatasetView'];

export function useCityFeatures(cityId?: string, bbox?: string, category?: string) {
  return useQuery({
    queryKey: queryKeys.cities.features(cityId || '', bbox || '', category),
    queryFn: async ({ signal }) => {
      if (!cityId || !bbox) throw new Error('City ID and bbox required');
      let url = `/api/gateway/v1/cities/${cityId}/features?bbox=${encodeURIComponent(bbox)}&limit=100`;
      if (category) {
        url += `&category=${encodeURIComponent(category)}`;
      }
      const { data } = await fetchGateway<FeatureCollection>(url, { signal });
      return data;
    },
    enabled: !!cityId && !!bbox,
    staleTime: 5 * 60 * 1000,
  });
}

export function useLandcover(cityId?: string) {
  return useQuery({
    queryKey: queryKeys.cities.landcover(cityId || ''),
    queryFn: async () => {
      if (!cityId) throw new Error('City ID required');
      const { data } = await fetchGateway<LandcoverView>(`/api/gateway/v1/cities/${cityId}/landcover`);
      return data;
    },
    enabled: !!cityId,
    staleTime: 60 * 60 * 1000, // 1 hour
  });
}

export function useWeather(cityId?: string) {
  return useQuery({
    queryKey: queryKeys.cities.weather(cityId || ''),
    queryFn: async () => {
      if (!cityId) throw new Error('City ID required');
      const { data } = await fetchGateway<WeatherView>(`/api/gateway/v1/cities/${cityId}/observations/weather`);
      return data;
    },
    enabled: !!cityId,
    staleTime: 15 * 60 * 1000, // 15 mins
  });
}

export function useAir(cityId?: string, parameter: string = 'pm25') {
  return useQuery({
    queryKey: queryKeys.cities.air(cityId || '', parameter),
    queryFn: async () => {
      if (!cityId) throw new Error('City ID required');
      const { data } = await fetchGateway<AirView>(`/api/gateway/v1/cities/${cityId}/observations/air?parameter=${parameter}`);
      return data;
    },
    enabled: !!cityId,
    staleTime: 10 * 60 * 1000, // 10 mins
  });
}

export function useDatasets(cityId?: string) {
  return useQuery({
    queryKey: queryKeys.cities.datasets(cityId || ''),
    queryFn: async () => {
      if (!cityId) throw new Error('City ID required');
      const { data } = await fetchGateway<DatasetView[]>(`/api/gateway/v1/cities/${cityId}/datasets`);
      return data;
    },
    enabled: !!cityId,
    staleTime: 30 * 60 * 1000,
  });
}
