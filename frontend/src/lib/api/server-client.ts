import createClient from 'openapi-fetch';
import type { paths } from './api-types';
import { getServerEnv } from '../env';

export function createServerApiClient(customToken?: string) {
  const env = getServerEnv();
  const token = customToken;

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return createClient<paths>({
    baseUrl: env.ECOTWIN_API_INTERNAL_URL,
    headers,
  });
}
