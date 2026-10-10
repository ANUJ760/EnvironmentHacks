import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  distDir: process.env.ECOTWIN_NEXT_DIST_DIR || '.next',
  poweredByHeader: false,
  reactStrictMode: true,
  outputFileTracingIncludes: {
    '/api/map/worker/*': ['./node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', './node_modules/maplibre-gl/dist/maplibre-gl-shared.mjs'],
  },
};

export default nextConfig;
