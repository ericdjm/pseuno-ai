/**
 * Main App Component for Pseuno AI
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Container,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Flex,
  Spacer,
  Avatar,
  useToast,
  Spinner,
  Center,
  Alert,
  AlertIcon,
  AlertDescription,
} from '@chakra-ui/react';
import { FaSpotify } from 'react-icons/fa';

import * as api from './api';
import { usePersistedSettings } from './hooks';
import { TasteDisplay } from './components/TasteDisplay';
import { PrivacyNote } from './components/PrivacyNote';
import AdvancedGenerationControls from './components/AdvancedGenerationControls';
import AdvancedResultsDisplay from './components/AdvancedResultsDisplay';

function App() {
  const toast = useToast();
  const { settings, updateSettings } = usePersistedSettings();

  // Auth state
  const [authStatus, setAuthStatus] = useState<api.AuthStatus>({ authenticated: false });
  const [authLoading, setAuthLoading] = useState(true);

  // Profile state
  const [profile, setProfile] = useState<api.SpotifyProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Generation state
  const [advancedResult, setAdvancedResult] = useState<api.AdvancedGenerateResponse | null>(null);
  const [generating, setGenerating] = useState(false);

  // Check for OAuth callback
  useEffect(() => {
    const error = api.checkUrlError();
    const success = api.checkUrlSuccess();

    if (error) {
      toast({
        title: 'Login failed',
        description: error,
        status: 'error',
        duration: 5000,
      });
      api.clearUrlParams();
    } else if (success) {
      toast({
        title: 'Successfully logged in!',
        status: 'success',
        duration: 3000,
      });
      api.clearUrlParams();
    }
  }, [toast]);

  // Check auth status on mount
  useEffect(() => {
    async function checkAuth() {
      setAuthLoading(true);
      try {
        const status = await api.checkAuthStatus();
        setAuthStatus(status);
      } catch (e) {
        console.error('Auth check failed:', e);
      } finally {
        setAuthLoading(false);
      }
    }
    checkAuth();
  }, []);

  // Load profile when authenticated or time range changes
  useEffect(() => {
    if (!authStatus.authenticated) {
      setProfile(null);
      return;
    }

    async function loadProfile() {
      setProfileLoading(true);
      setProfileError(null);
      try {
        const data = await api.getProfile(settings.timeRange);
        setProfile(data);
      } catch (e) {
        const error = e as api.ApiError;
        setProfileError(error.detail || 'Failed to load profile');
        if (error.status === 401) {
          setAuthStatus({ authenticated: false });
        }
      } finally {
        setProfileLoading(false);
      }
    }
    loadProfile();
  }, [authStatus.authenticated, settings.timeRange]);

  // Handlers
  const handleLogin = async () => {
    try {
      await api.login();
    } catch (e) {
      toast({
        title: 'Login failed',
        description: 'Could not connect to Spotify',
        status: 'error',
      });
    }
  };

  const handleLogout = async () => {
    await api.logout();
    setAuthStatus({ authenticated: false });
    setProfile(null);
    setAdvancedResult(null);
    toast({
      title: 'Logged out',
      status: 'info',
      duration: 2000,
    });
  };

  const handleAdvancedGenerate = (result: api.AdvancedGenerateResponse) => {
    setAdvancedResult(result);
  };

  return (
    <Box minH="100vh" bg="gray.900">
      {/* Header */}
      <Box bg="gray.800" borderBottom="1px" borderColor="gray.700" py={4}>
        <Container maxW="container.lg">
          <Flex align="center">
            <HStack spacing={3}>
              <Box color="brand.500" fontSize="2xl">
                🎵
              </Box>
              <Heading size="lg" fontWeight="bold">
                Pseuno AI
              </Heading>
            </HStack>
            <Spacer />
            {authLoading ? (
              <Spinner size="sm" />
            ) : authStatus.authenticated ? (
              <HStack spacing={4}>
                <HStack spacing={2}>
                  <Avatar
                    size="sm"
                    src={authStatus.user_image || undefined}
                    name={authStatus.user_name}
                  />
                  <Text fontSize="sm" color="gray.300">
                    {authStatus.user_name}
                  </Text>
                </HStack>
                <Button size="sm" variant="ghost" onClick={handleLogout}>
                  Logout
                </Button>
              </HStack>
            ) : (
              <Button
                leftIcon={<FaSpotify />}
                variant="spotify"
                size="md"
                onClick={handleLogin}
              >
                Login with Spotify
              </Button>
            )}
          </Flex>
        </Container>
      </Box>

      {/* Main Content */}
      <Container maxW="container.lg" py={8}>
        {!authStatus.authenticated ? (
          // Not logged in
          <Center py={20}>
            <VStack spacing={6} textAlign="center">
              <Heading size="xl">
                Generate Personalized Music Prompts
              </Heading>
              <Text fontSize="lg" color="gray.400" maxW="md">
                Connect your Spotify to analyze your music taste and create
                custom prompts for Suno AI based on what you actually listen to.
              </Text>
              <Button
                leftIcon={<FaSpotify />}
                variant="spotify"
                size="lg"
                onClick={handleLogin}
              >
                Login with Spotify
              </Button>
              <PrivacyNote />
            </VStack>
          </Center>
        ) : (
          // Logged in
          <VStack spacing={8} align="stretch">
            {/* Profile Error */}
            {profileError && (
              <Alert status="error" borderRadius="md">
                <AlertIcon />
                <AlertDescription>{profileError}</AlertDescription>
              </Alert>
            )}

            {/* Taste Display */}
            <TasteDisplay
              profile={profile}
              loading={profileLoading}
              timeRange={settings.timeRange}
              onTimeRangeChange={(tr) => updateSettings({ timeRange: tr })}
            />

            {/* Generation Controls */}
            <Box>
              <AdvancedGenerationControls
                onGenerate={handleAdvancedGenerate}
                isLoading={generating}
                setIsLoading={setGenerating}
                profile={profile}
              />
            </Box>

            {/* Results */}
            {advancedResult && (
              <AdvancedResultsDisplay result={advancedResult} />
            )}

            {/* Privacy Note */}
            <PrivacyNote />
          </VStack>
        )}
      </Container>
    </Box>
  );
}

export default App;
