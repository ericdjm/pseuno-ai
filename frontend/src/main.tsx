import React from 'react'
import ReactDOM from 'react-dom/client'
import posthog from 'posthog-js'
import { ChakraProvider } from '@chakra-ui/react'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import theme from './themes'

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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ChakraProvider theme={theme}>
        <App />
      </ChakraProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
