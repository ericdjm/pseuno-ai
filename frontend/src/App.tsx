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
import { GenerationControls } from './components/GenerationControls';
import { ResultsDisplay } from './components/ResultsDisplay';
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
  const [result, setResult] = useState<api.GenerateResponse | null>(null);
  const [generating, setGenerating] = useState(false);

  // Advanced generation state
  const [advancedResult, setAdvancedResult] = useState<api.AdvancedGenerateResponse | null>(null);
  const [generationMode, setGenerationMode] = useState<'basic' | 'advanced'>('basic');

  // Theme input
  const [theme, setTheme] = useState('');

  // Check for shared result in URL
  useEffect(() => {
    const shared = api.parseShareUrl();
    if (shared) {
      setResult(shared);
      toast({
        title: 'Shared result loaded',
        status: 'info',
        duration: 3000,
      });
    }
  }, [toast]);

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
    setResult(null);
    setAdvancedResult(null);
    toast({
      title: 'Logged out',
      status: 'info',
      duration: 2000,
    });
  };

  const handleGenerate = async () => {
    if (!profile) return;

    setGenerating(true);
    try {
      const response = await api.generate({
        time_range: settings.timeRange,
        theme: theme || undefined,
        energy: settings.energy,
        rhythm_complexity: settings.rhythmComplexity,
        darkness: settings.darkness,
        preset: settings.preset || undefined,
      });
      setResult(response);
      toast({
        title: 'Generated successfully!',
        status: 'success',
        duration: 2000,
      });
    } catch (e) {
      const error = e as api.ApiError;
      toast({
        title: 'Generation failed',
        description: error.detail || 'Please try again',
        status: 'error',
      });
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateVariation = async () => {
    // Just call generate again - the random elements will create variation
    await handleGenerate();
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
              <HStack mb={4}>
                <Button
                  variant={generationMode === 'basic' ? 'solid' : 'outline'}
                  colorScheme="green"
                  onClick={() => setGenerationMode('basic')}
                >
                  Basic Mode
                </Button>
                <Button
                  variant={generationMode === 'advanced' ? 'solid' : 'outline'}
                  colorScheme="purple"
                  onClick={() => setGenerationMode('advanced')}
                >
                  Advanced (Vibe-First)
                </Button>
              </HStack>

              {generationMode === 'basic' ? (
                <GenerationControls
                  settings={settings}
                  onSettingsChange={updateSettings}
                  theme={theme}
                  onThemeChange={setTheme}
                  onGenerate={handleGenerate}
                  generating={generating}
                  disabled={!profile || profileLoading}
                />
              ) : (
                <AdvancedGenerationControls
                  onGenerate={handleAdvancedGenerate}
                  isLoading={generating}
                  setIsLoading={setGenerating}
                  profile={profile}
                />
              )}
            </Box>

            {/* Results */}
            {generationMode === 'basic' && result && (
              <ResultsDisplay
                result={result}
                onGenerateVariation={handleGenerateVariation}
                generating={generating}
              />
            )}

            {generationMode === 'advanced' && advancedResult && (
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
