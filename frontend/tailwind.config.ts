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
        background: '#000000',
        ink: 'var(--ink)',
        primary: {
          DEFAULT: '#55d9ff',
          hover: '#8eeaff',
          light: '#071727',
        },
        forest: {
          DEFAULT: '#55d9ff',
          dark: '#071923',
        },
        accent: {
          DEFAULT: '#55d9ff',
          light: '#e0f2fe',
        },
        border: '#53cfff38',
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
        sans: ['Courier New', 'Courier', 'monospace'],
        mono: ['Courier New', 'Courier', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
