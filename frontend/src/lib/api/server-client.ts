import createClient from 'openapi-fetch';
import type { paths } from './api-types';
import { getServerEnv } from '../env';

export function createServerApiClient(customToken?: string) {
  const env = getServerEnv();
  const token =
    customToken ||
    (env.FRONTEND_AUTH_MODE === 'dev' && env.ECOTWIN_DEV_BEARER_TOKEN
      ? env.ECOTWIN_DEV_BEARER_TOKEN
      : undefined);

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
