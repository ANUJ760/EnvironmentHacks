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
        background: '#F6F8F4',
        ink: '#172A24',
        primary: {
          DEFAULT: '#0C8055',
          hover: '#096342',
          light: '#E2F3EB',
        },
        forest: {
          DEFAULT: '#173F33',
          dark: '#0F2921',
        },
        accent: {
          DEFAULT: '#2F9E81',
          light: '#E6F6F2',
        },
        border: '#D8E5DD',
        warning: {
          DEFAULT: '#B56B1F',
          light: '#FEF3E7',
        },
        muted: '#526E64',
        surface: '#FFFFFF',
        'surface-elevated': '#FFFFFF',
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
