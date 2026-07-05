// Aether theme tokens — Material Design 3 inspired
// Supports light and dark themes via CSS custom properties

import type { InjectionKey, Ref } from 'vue'
import { ref, inject, provide } from 'vue'

export interface Theme {
  name: 'light' | 'dark'
  colors: Record<string, string>
  fontSize: Record<string, string>
  spacing: Record<string, string>
  radius: Record<string, string>
  shadow: Record<string, string>
}

export const lightTheme: Theme = {
  name: 'light',
  colors: {
    primary: '#1a73e8',
    primaryHover: '#1557b0',
    primaryLight: '#e8f0fe',
    surface: '#ffffff',
    surfaceVariant: '#f8f9fa',
    background: '#f1f3f4',
    onSurface: '#202124',
    onSurfaceVariant: '#5f6368',
    outline: '#dadce0',
    outlineVariant: '#e0e0e0',
    error: '#ea4335',
    errorLight: '#fce8e6',
    success: '#34a853',
    successLight: '#e6f4ea',
    warning: '#f9ab00',
    warningLight: '#fef7e0',
    info: '#4285f4',
    infoLight: '#e8f0fe',
  },
  fontSize: {
    xs: '10px',
    sm: '12px',
    md: '14px',
    lg: '16px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '32px',
  },
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    '2xl': '32px',
    '3xl': '48px',
  },
  radius: {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
  },
  shadow: {
    sm: '0 1px 2px rgba(0,0,0,0.06)',
    md: '0 2px 8px rgba(0,0,0,0.08)',
    lg: '0 4px 16px rgba(0,0,0,0.12)',
    xl: '0 8px 32px rgba(0,0,0,0.16)',
  },
}

export const darkTheme: Theme = {
  name: 'dark',
  colors: {
    primary: '#8ab4f8',
    primaryHover: '#aecbfa',
    primaryLight: '#1a2332',
    surface: '#1e1e1e',
    surfaceVariant: '#2d2d2d',
    background: '#121212',
    onSurface: '#e8eaed',
    onSurfaceVariant: '#9aa0a6',
    outline: '#3c4043',
    outlineVariant: '#5f6368',
    error: '#f28b82',
    errorLight: '#3c1e1c',
    success: '#81c995',
    successLight: '#1c3c24',
    warning: '#fdd663',
    warningLight: '#3c351c',
    info: '#8ab4f8',
    infoLight: '#1a2332',
  },
  fontSize: lightTheme.fontSize,
  spacing: lightTheme.spacing,
  radius: lightTheme.radius,
  shadow: {
    sm: '0 1px 3px rgba(0,0,0,0.3)',
    md: '0 2px 10px rgba(0,0,0,0.4)',
    lg: '0 4px 20px rgba(0,0,0,0.5)',
    xl: '0 8px 40px rgba(0,0,0,0.6)',
  },
}

export const THEME_KEY: InjectionKey<{
  theme: Ref<Theme>
  toggleTheme: () => void
}> = Symbol('theme')

export function createThemeProvider() {
  const saved = localStorage.getItem('aether-theme')
  const theme = ref<Theme>(saved === 'dark' ? darkTheme : lightTheme)

  function toggleTheme() {
    theme.value = theme.value.name === 'light' ? darkTheme : lightTheme
    localStorage.setItem('aether-theme', theme.value.name)
  }

  function applyTheme(t: Theme) {
    const root = document.documentElement
    for (const [key, value] of Object.entries(t.colors)) {
      root.style.setProperty(`--color-${key}`, value)
    }
    for (const [key, value] of Object.entries(t.fontSize)) {
      root.style.setProperty(`--font-${key}`, value)
    }
    for (const [key, value] of Object.entries(t.spacing)) {
      root.style.setProperty(`--space-${key}`, value)
    }
    for (const [key, value] of Object.entries(t.radius)) {
      root.style.setProperty(`--radius-${key}`, value)
    }
    for (const [key, value] of Object.entries(t.shadow)) {
      root.style.setProperty(`--shadow-${key}`, value)
    }
  }

  provide(THEME_KEY, { theme, toggleTheme })

  // Apply initially and on change
  applyTheme(theme.value)
  return { theme, toggleTheme }
}

export function useTheme() {
  const ctx = inject(THEME_KEY)
  if (!ctx) throw new Error('useTheme() must be used within a theme provider')
  return ctx
}
