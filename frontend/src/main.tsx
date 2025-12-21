import React from 'react'
import ReactDOM from 'react-dom/client'
import { ChakraProvider, extendTheme } from '@chakra-ui/react'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'

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
