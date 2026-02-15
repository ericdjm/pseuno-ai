import React from 'react'
import ReactDOM from 'react-dom/client'
import posthog from 'posthog-js'
import { ChakraProvider, extendTheme } from '@chakra-ui/react'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'

// Silence console output in production
if (import.meta.env.PROD) {
  const noop = () => {};
  console.log = noop;
  console.warn = noop;
  console.error = noop;
}

// Initialize PostHog (analytics, feature flags, etc.)
const posthogKey = import.meta.env.VITE_POSTHOG_KEY
const posthogHost = import.meta.env.VITE_POSTHOG_HOST
const appEnv = import.meta.env.VITE_APP_ENV || 'unknown'

if (posthogKey && posthogHost) {
  posthog.init(posthogKey, {
    api_host: posthogHost,
    person_profiles: 'identified_only', // Only create profiles for identified users (privacy-friendly)
    capture_pageview: true, // Auto-capture pageviews
    capture_pageleave: true, // Capture when users leave pages
  })
  // Attach environment to all events (single project for dev + prod)
  posthog.register({ environment: appEnv })

  // E2E + local debugging convenience: expose posthog instance in dev.
  // This lets Playwright verify capture payloads without depending on transport details.
  if (import.meta.env.DEV) {
    ;(window as any).posthog = posthog
  }
}

// Custom theme with Spotify-inspired colors
const theme = extendTheme({
  config: {
    initialColorMode: 'dark',
    useSystemColorMode: false,
  },
  colors: {
    brand: {
      50: '#e6fff0',
      100: '#b3ffd6',
      200: '#80ffbb',
      300: '#4dffa1',
      400: '#1aff86',
      500: '#1DB954', // Spotify green
      600: '#17a34a',
      700: '#128c3f',
      800: '#0d7633',
      900: '#085f28',
    },
    spotify: {
      green: '#1DB954',
      black: '#191414',
      white: '#FFFFFF',
      gray: '#535353',
    }
  },
  fonts: {
    heading: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif`,
    body: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif`,
  },
  styles: {
    global: {
      body: {
        bg: 'gray.900',
        color: 'white',
      }
    }
  },
  components: {
    Button: {
      variants: {
        spotify: {
          bg: 'spotify.green',
          color: 'white',
          _hover: {
            bg: 'brand.600',
            transform: 'scale(1.02)',
          },
          _active: {
            bg: 'brand.700',
          }
        }
      }
    }
  }
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ChakraProvider theme={theme}>
        <App />
      </ChakraProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
