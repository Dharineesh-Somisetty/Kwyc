/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                brand: 'rgb(var(--brand) / <alpha-value>)',
                brandSoft: 'rgb(var(--brand-soft) / <alpha-value>)',
                brandGreen: 'rgb(var(--brand-green) / <alpha-value>)',
                bg1: 'rgb(var(--bg1) / <alpha-value>)',
                bg2: 'rgb(var(--bg2) / <alpha-value>)',
                primary: {
                    50: '#eef2ff',
                    100: '#e0e7ff',
                    200: '#c7d2fe',
                    300: '#a5b4fc',
                    400: '#818cf8',
                    500: '#6366f1',
                    600: '#4f46e5',
                    700: '#4338ca',
                    800: '#3730a3',
                    900: '#312e81',
                },
                accent: {
                    50: '#ecfdf5',
                    100: '#d1fae5',
                    200: '#a7f3d0',
                    300: '#6ee7b7',
                    400: '#34d399',
                    500: '#10b981',
                    600: '#059669',
                    700: '#047857',
                    800: '#065f46',
                    900: '#064e3b',
                },
                warning: {
                    light: '#fef3cd',
                    DEFAULT: '#f59e0b',
                    dark: '#d97706',
                },
                danger: {
                    light: '#fef2f2',
                    DEFAULT: '#ef4444',
                    dark: '#b91c1c',
                },
                success: {
                    light: '#ecfdf5',
                    DEFAULT: '#10b981',
                    dark: '#047857',
                }
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                display: ['Outfit', 'Inter', 'system-ui', 'sans-serif'],
            },
            boxShadow: {
                'glass': '0 2px 16px rgba(0, 0, 0, 0.06)',
                'glow': '0 0 24px rgba(99, 102, 241, 0.2)',
                'glow-accent': '0 0 20px rgba(16, 185, 129, 0.2)',
                'card': '0 2px 16px rgba(0, 0, 0, 0.06)',
                'card-hover': '0 4px 24px rgba(0, 0, 0, 0.10)',
            },
            backdropBlur: {
                xs: '2px',
            },
            animation: {
                'fade-in': 'fadeIn 0.5s ease-in',
                'slide-up': 'slideUp 0.5s ease-out',
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'spin-slow': 'spin 3s linear infinite',
            },
            keyframes: {
                fadeIn: {
                    '0%': { opacity: '0' },
                    '100%': { opacity: '1' },
                },
                slideUp: {
                    '0%': { transform: 'translateY(20px)', opacity: '0' },
                    '100%': { transform: 'translateY(0)', opacity: '1' },
                },
            },
        },
    },
    plugins: [],
}
