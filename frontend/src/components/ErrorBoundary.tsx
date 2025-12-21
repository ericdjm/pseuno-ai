/**
 * Error Boundary Component
 * Catches and displays React errors gracefully
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  Button,
  Container,
  Heading,
  Text,
  VStack,
  Code,
} from '@chakra-ui/react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const isDark = true; // Assuming dark mode based on theme

      return (
        <Container maxW="container.md" py={20}>
          <VStack spacing={6} align="stretch">
            <Heading size="xl" color="red.400">
              Oops! Something went wrong
            </Heading>
            <Text fontSize="lg">
              We encountered an unexpected error. Please try refreshing the page.
            </Text>
            
            {this.state.error && (
              <Box
                p={4}
                bg={isDark ? 'gray.800' : 'gray.100'}
                borderRadius="md"
                borderLeft="4px solid"
                borderColor="red.400"
              >
                <Text fontWeight="bold" mb={2}>
                  Error Details:
                </Text>
                <Code display="block" whiteSpace="pre-wrap" p={2}>
                  {this.state.error.toString()}
                </Code>
              </Box>
            )}

            <Button
              colorScheme="green"
              size="lg"
              onClick={this.handleReset}
            >
              Reload Page
            </Button>

            <Text fontSize="sm" color="gray.500" textAlign="center">
              If this problem persists, please contact support or check the browser console for more details.
            </Text>
          </VStack>
        </Container>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
