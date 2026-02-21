import { extendTheme, type ThemeConfig } from '@chakra-ui/react'

const baseConfig: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
}

const baseFonts = {
  heading: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif`,
  body: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif`,
}

const theme = extendTheme({
  config: baseConfig,
  colors: {
    brand: {
      50: '#e6fff0',
      100: '#b3ffd6',
      200: '#80ffbb',
      300: '#4dffa1',
      400: '#1aff86',
      500: '#1DB954',
      600: '#17a34a',
      700: '#128c3f',
      800: '#0d7633',
      900: '#085f28',
    },
    // Lifted gray scale — slightly brighter across the board
    gray: {
      50: '#f7fafc',
      100: '#edf2f7',
      200: '#e2e8f0',
      300: '#cbd5e0',
      400: '#a0aec0',
      500: '#718096',
      600: '#4a5568',
      700: '#323b4a',
      800: '#222a38',
      900: '#191f2b',
    },
    spotify: {
      green: '#1DB954',
      black: '#191414',
      white: '#FFFFFF',
      gray: '#535353',
    },
  },
  fonts: baseFonts,
  styles: {
    global: {
      body: {
        bg: 'gray.900',
        color: 'white',
        letterSpacing: '0.01em',
      },
      // Subtle glow on focus for all interactive elements
      '*:focus-visible': {
        boxShadow: '0 0 0 2px rgba(255, 255, 255, 0.25) !important',
        outline: 'none !important',
      },
    },
  },
  components: {
    Heading: {
      baseStyle: {
        letterSpacing: '0.02em',
      },
    },
    Text: {
      baseStyle: {
        lineHeight: '1.65',
      },
    },
    Button: {
      baseStyle: {
        transition: 'all 0.2s ease',
      },
      variants: {
        spotify: {
          bg: 'brand.500',
          color: 'white',
          boxShadow: '0 0 12px rgba(255, 255, 255, 0.15)',
          _hover: {
            bg: 'brand.600',
            transform: 'scale(1.02)',
            boxShadow: '0 0 20px rgba(255, 255, 255, 0.25)',
          },
          _active: { bg: 'brand.700' },
        },
      },
    },
    Input: {
      variants: {
        outline: {
          field: {
            _focus: {
              borderColor: 'whiteAlpha.400',
              boxShadow: '0 0 0 1px rgba(255, 255, 255, 0.15), 0 0 12px rgba(255, 255, 255, 0.08)',
            },
          },
        },
      },
    },
    Textarea: {
      variants: {
        outline: {
          _focus: {
            borderColor: 'whiteAlpha.400',
            boxShadow: '0 0 0 1px rgba(255, 255, 255, 0.15), 0 0 12px rgba(255, 255, 255, 0.08)',
          },
        },
      },
    },
    Tag: {
      baseStyle: {
        container: {
          transition: 'all 0.15s ease',
        },
      },
    },
  },
})

export default theme
