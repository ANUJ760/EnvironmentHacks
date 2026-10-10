export const queryKeys = {
  cities: {
    all: ['cities'] as const,
    list: (cursor?: string, limit?: number) => ['cities', 'list', { cursor, limit }] as const,
    detail: (cityId: string) => ['cities', 'detail', cityId] as const,
    features: (cityId: string, bbox: string, category?: string) =>
      ['cities', 'features', cityId, { bbox, category }] as const,
    landcover: (cityId: string) => ['cities', 'landcover', cityId] as const,
    weather: (cityId: string, start?: string, end?: string) =>
      ['cities', 'weather', cityId, { start, end }] as const,
    air: (cityId: string, parameter: string = 'pm25') =>
      ['cities', 'air', cityId, { parameter }] as const,
    datasets: (cityId: string) => ['cities', 'datasets', cityId] as const,
  },
  models: {
    all: ['models'] as const,
    forCity: (cityId?: string) => ['models', { cityId }] as const,
  },
  scenarios: {
    all: ['scenarios'] as const,
    detail: (scenarioId: string) => ['scenarios', 'detail', scenarioId] as const,
    reports: (scenarioId: string) => ['scenarios', 'reports', scenarioId] as const,
  },
  jobs: {
    detail: (jobId: string) => ['jobs', 'detail', jobId] as const,
  },
  results: {
    detail: (resultId: string) => ['results', 'detail', resultId] as const,
  },
  status: {
    ready: ['status', 'readyz'] as const,
  },
};
