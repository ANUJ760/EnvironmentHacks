import { z } from 'zod';

const envSchema = z.object({
  APP_ENV: z.enum(['development', 'test', 'production']).default('development'),
  APP_BASE_URL: z.string().url().default('http://localhost:3000'),
  ECOTWIN_API_INTERNAL_URL: z.string().url().default('http://127.0.0.1:8000'),
  FRONTEND_AUTH_MODE: z.enum(['dev', 'cognito']).default('dev'),
  ECOTWIN_DEV_BEARER_TOKEN: z.string().optional().default(''),
  NEXTAUTH_SECRET: z.string().min(16).default('local-development-secret-only-change-in-production-must-be-long-enough-32bytes'),
  NEXTAUTH_URL: z.string().url().default('http://localhost:3000'),
  COGNITO_ISSUER: z.string().optional().default(''),
  COGNITO_CLIENT_ID: z.string().optional().default(''),
  COGNITO_CLIENT_SECRET: z.string().optional().default(''),
  NEXT_PUBLIC_APP_LABEL: z.string().default('EcoTwin'),
});

let parsedEnv: z.infer<typeof envSchema> | null = null;

export function getServerEnv(): z.infer<typeof envSchema> {
  if (parsedEnv) return parsedEnv;

  const result = envSchema.safeParse({
    APP_ENV: process.env.APP_ENV || 'development',
    APP_BASE_URL: process.env.APP_BASE_URL || 'http://localhost:3000',
    ECOTWIN_API_INTERNAL_URL: process.env.ECOTWIN_API_INTERNAL_URL || 'http://127.0.0.1:8000',
    FRONTEND_AUTH_MODE: process.env.FRONTEND_AUTH_MODE || 'dev',
    ECOTWIN_DEV_BEARER_TOKEN: process.env.ECOTWIN_DEV_BEARER_TOKEN || '',
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET || 'local-development-secret-only-change-in-production-must-be-long-enough-32bytes',
    NEXTAUTH_URL: process.env.NEXTAUTH_URL || 'http://localhost:3000',
    COGNITO_ISSUER: process.env.COGNITO_ISSUER || '',
    COGNITO_CLIENT_ID: process.env.COGNITO_CLIENT_ID || '',
    COGNITO_CLIENT_SECRET: process.env.COGNITO_CLIENT_SECRET || '',
    NEXT_PUBLIC_APP_LABEL: process.env.NEXT_PUBLIC_APP_LABEL || 'EcoTwin',
  });

  if (!result.success) {
    console.error('Invalid environment variables:', result.error.format());
    throw new Error('Environment configuration validation failed');
  }

  // Production safety guards
  if (result.data.APP_ENV === 'production') {
    if (result.data.FRONTEND_AUTH_MODE === 'dev') {
      throw new Error('Production environment must not use FRONTEND_AUTH_MODE=dev');
    }
    if (!result.data.APP_BASE_URL.startsWith('https://')) {
      throw new Error('Production APP_BASE_URL must use HTTPS');
    }
    if (!result.data.COGNITO_ISSUER || !result.data.COGNITO_CLIENT_ID) {
      throw new Error('Production requires COGNITO_ISSUER and COGNITO_CLIENT_ID');
    }
  }

  parsedEnv = result.data;
  return parsedEnv;
}

export const publicConfig = {
  appLabel: process.env.NEXT_PUBLIC_APP_LABEL || 'EcoTwin',
};
