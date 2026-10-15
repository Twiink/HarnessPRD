/** @type {import('tailwindcss').Config} */

// ReqFlow 工程图纸风格：冷灰钢色中性色 + 制图蓝，细线框代替阴影，近直角转角。
const steel = {
  50: '#f5f7f9',
  100: '#edf0f3',
  200: '#d6dde4',
  300: '#bcc6d0',
  400: '#8a99a8',
  500: '#5d6b78',
  600: '#46535f',
  700: '#34404b',
  800: '#26323d',
  900: '#1d2a36',
  950: '#121b24',
};

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slate: steel,
        gray: steel,
        primary: {
          50: '#eef4fb',
          100: '#dbe7f6',
          200: '#b8cfec',
          300: '#8bb0dd',
          400: '#5788c8',
          500: '#2f6db5',
          600: '#1f5fa8',
          700: '#194d89',
          800: '#153f6f',
          900: '#12345a',
        },
        ground: '#e9edf1',
        sheet: '#fbfcfd',
        ink: '#1d2a36',
        hair: '#cfd7df',
        rule: '#8a99a8',
        mark: '#c0392b',
        stamp: '#b7791f',
      },
      fontFamily: {
        sans: ['Barlow', '"Noto Sans SC"', 'system-ui', 'sans-serif'],
        cond: ['"Barlow Condensed"', 'Barlow', '"Noto Sans SC"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        sm: '1px',
        DEFAULT: '2px',
        md: '2px',
        lg: '3px',
        xl: '4px',
        '2xl': '6px',
      },
      boxShadow: {
        sm: 'none',
        DEFAULT: '0 1px 2px rgba(29, 42, 54, 0.08)',
        md: '0 6px 18px -6px rgba(29, 42, 54, 0.18)',
        lg: '0 16px 40px -12px rgba(29, 42, 54, 0.28)',
        xl: '0 24px 60px -16px rgba(29, 42, 54, 0.32)',
      },
    },
  },
  plugins: [],
}
