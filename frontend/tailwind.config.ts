import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#080b10',
        ink: 'var(--ink)',
        primary: {
          DEFAULT: '#0369a1',
          hover: '#075985',
          light: '#e0f2fe',
        },
        forest: {
          DEFAULT: '#082f49',
          dark: '#071923',
        },
        accent: {
          DEFAULT: '#0284c7',
          light: '#e0f2fe',
        },
        border: '#cbd5e1',
        warning: {
          DEFAULT: '#B56B1F',
          light: '#FEF3E7',
        },
        muted: 'var(--muted)',
        surface: '#FFFFFF',
        'surface-elevated': '#FFFFFF',
      },
      fontSize: {
        xs: ['0.875rem', '1.35rem'],
        sm: ['0.9375rem', '1.5rem'],
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
