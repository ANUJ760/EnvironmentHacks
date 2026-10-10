import nextPlugin from '@next/eslint-plugin-next';

export default [
  { ignores: ['.next/**', '.next-check/**', 'node_modules/**', 'playwright-report/**', 'test-results/**'] },
  {
    plugins: {
      '@next/next': nextPlugin,
    },
    rules: {
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs['core-web-vitals'].rules,
    },
  },
];
