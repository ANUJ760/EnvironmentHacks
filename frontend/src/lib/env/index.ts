import { z } from 'zod';

const envSchema = z.object({
  APP_ENV: z.enum(['development', 'test', 'production']).default('development'),
  APP_BASE_URL: z.string().url().default('http://localhost:3000'),
  ECOTWIN_API_INTERNAL_URL: z.string().url().default('http://127.0.0.1:8000'),
  NEXT_PUBLIC_APP_LABEL: z.string().default('EcoTwin'),
});

let parsedEnv: z.infer<typeof envSchema> | null = null;

export function getServerEnv(): z.infer<typeof envSchema> {
  if (parsedEnv) return parsedEnv;

  const result = envSchema.safeParse({
    APP_ENV: process.env.APP_ENV || 'development',
    APP_BASE_URL: process.env.APP_BASE_URL || 'http://localhost:3000',
    ECOTWIN_API_INTERNAL_URL: process.env.ECOTWIN_API_INTERNAL_URL || 'http://127.0.0.1:8000',
    NEXT_PUBLIC_APP_LABEL: process.env.NEXT_PUBLIC_APP_LABEL || 'EcoTwin',
  });

  if (!result.success) {
    console.error('Invalid environment variables:', result.error.format());
    throw new Error('Environment configuration validation failed');
  }

  // Production safety guards
  if (result.data.APP_ENV === 'production') {
    if (!result.data.APP_BASE_URL.startsWith('https://')) {
      throw new Error('Production APP_BASE_URL must use HTTPS');
    }
  }

  parsedEnv = result.data;
  return parsedEnv;
}

export const publicConfig = {
  appLabel: process.env.NEXT_PUBLIC_APP_LABEL || 'EcoTwin',
};
