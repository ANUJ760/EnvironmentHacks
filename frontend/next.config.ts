import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: true,
  outputFileTracingIncludes: {
    '/api/map/worker/*': ['./node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', './node_modules/maplibre-gl/dist/maplibre-gl-shared.mjs'],
  },
};

export default nextConfig;
