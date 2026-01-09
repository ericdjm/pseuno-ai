/**
 * Main App Component for Pseuno AI
 */

import { useState, useEffect, useRef } from 'react';
import {
  Box,
  Container,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Flex,
  Avatar,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertDescription,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverCloseButton,
  PopoverHeader,
  PopoverBody,
} from '@chakra-ui/react';
import { FaSpotify } from 'react-icons/fa';

import * as api from './api';
import { usePersistedSettings, useSessionStorageState } from './hooks';
import { TasteDisplay } from './components/TasteDisplay';
import { PrivacyNote } from './components/PrivacyNote';
import AdvancedGenerationControls from './components/AdvancedGenerationControls';
import AdvancedResultsDisplay from './components/AdvancedResultsDisplay';
import SavedPromptsLibrary from './components/SavedPromptsLibrary';

type StyleMode = 'songStylePrompt' | 'pastSunoPrompts' | 'favorites';

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

  // Generation state (persisted to sessionStorage for back/forward survival)
  const [advancedResult, setAdvancedResult] = useSessionStorageState<api.AdvancedGenerateResponse | null>(
    'advancedResult',
    null
  );
  const [generating, setGenerating] = useState(false);

  // Saved prompts state
  const [savedPromptsRefresh, setSavedPromptsRefresh] = useState(0);
  const [savedPrompts, setSavedPrompts] = useState<api.SavedSunoPrompt[]>([]);
  const [selectedSavedPrompt, setSelectedSavedPrompt] = useState<api.SavedSunoPrompt | null>(null);
  // Persist selectedSavedPromptId so we can reselect after prompts load
  const [selectedSavedPromptId, setSelectedSavedPromptId] = useSessionStorageState<number | null>(
    'selectedSavedPromptId',
    null
  );
  // Persist styleMode for back/forward
  const [styleMode, setStyleMode] = useSessionStorageState<StyleMode>('styleMode', 'songStylePrompt');

  // Ref to scroll to generation controls
  const generationControlsRef = useRef<HTMLDivElement>(null);

  // Refresh prompts when mode changes (to load favorites vs all)
  // The handlePromptsLoaded callback will validate/clear selection if needed
  useEffect(() => {
    if (styleMode === 'pastSunoPrompts' || styleMode === 'favorites') {
      setSavedPromptsRefresh((n) => n + 1);
    }
  }, [styleMode]);

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
      setProfileError(null);
      setProfileLoading(false);
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
    // Refresh prompts list since generation now auto-saves
    setSavedPromptsRefresh((n) => n + 1);
  };

  const handlePromptsLoaded = (prompts: api.SavedSunoPrompt[]) => {
    setSavedPrompts(prompts);
    
    // Always validate that the selected prompt exists in the new list
    // This handles cases like: switching to favorites mode when a non-favorite was selected
    if (selectedSavedPromptId !== null) {
      const foundInList = prompts.find((p) => p.id === selectedSavedPromptId);
      if (foundInList) {
        // Prompt exists in new list - update the object reference (may have changed)
        setSelectedSavedPrompt(foundInList);
      } else {
        // Prompt doesn't exist in new list - clear selection
        setSelectedSavedPrompt(null);
        setSelectedSavedPromptId(null);
      }
    }
  };

  // Keep selectedSavedPromptId in sync when user selects a prompt
  const handleSelectSavedPrompt = (prompt: api.SavedSunoPrompt | null) => {
    setSelectedSavedPrompt(prompt);
    setSelectedSavedPromptId(prompt?.id ?? null);
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
            <Box flex="1" />
            {authLoading ? (
              <Spinner size="sm" />
            ) : (
              <Popover placement="bottom-end">
                <PopoverTrigger>
                  <Button
                    variant="ghost"
                    p={0}
                    minW="auto"
                    aria-label="Profile menu"
                  >
                    <Avatar
                      size="sm"
                      src={authStatus.user_image || undefined}
                      name={authStatus.authenticated ? authStatus.user_name : undefined}
                    />
                  </Button>
                </PopoverTrigger>
                <PopoverContent bg="gray.800" borderColor="gray.700" w="240px">
                  <PopoverArrow bg="gray.800" />
                  <PopoverCloseButton />
                  <PopoverHeader borderColor="gray.700">
                    {authStatus.authenticated ? 'Signed in' : 'Guest'}
                  </PopoverHeader>
                  <PopoverBody>
                    {authStatus.authenticated ? (
                      <VStack align="stretch" spacing={3}>
                        <Text fontSize="sm" color="gray.400">
                          {authStatus.user_name || 'Spotify user'}
                        </Text>
                        <Button size="sm" variant="outline" onClick={handleLogout}>
                          Logout
                        </Button>
                      </VStack>
                    ) : (
                      <VStack align="stretch" spacing={3}>
                        <Text fontSize="sm" color="gray.400">
                          Sign in to personalize with Spotify.
                        </Text>
                        <Button
                          leftIcon={<FaSpotify />}
                          variant="spotify"
                          size="sm"
                          onClick={handleLogin}
                        >
                          Sign in with Spotify
                        </Button>
                      </VStack>
                    )}
                  </PopoverBody>
                </PopoverContent>
              </Popover>
            )}
          </Flex>
        </Container>
      </Box>

      {/* Main Content */}
      <Container maxW="container.lg" py={8}>
        <VStack spacing={8} align="stretch">
          <Box textAlign={{ base: 'left', md: 'center' }}>
            <Heading size="xl">Generate Music Prompts</Heading>
            <Text fontSize="lg" color="gray.400" maxW="2xl" mx={{ md: 'auto' }} mt={2}>
              Use the generator right away, or connect Spotify from the profile
              menu to personalize your prompts.
            </Text>
          </Box>

          {!authStatus.authenticated && (
            <Alert status="info" borderRadius="md">
              <AlertIcon />
              <AlertDescription>
                You are in guest mode. Connect Spotify from the avatar to unlock taste-based
                suggestions.
              </AlertDescription>
            </Alert>
          )}

          {/* Profile Error */}
          {profileError && (
            <Alert status="error" borderRadius="md">
              <AlertIcon />
              <AlertDescription>{profileError}</AlertDescription>
            </Alert>
          )}

          {authStatus.authenticated && (
            <TasteDisplay
              profile={profile}
              loading={profileLoading}
              timeRange={settings.timeRange}
              onTimeRangeChange={(tr) => updateSettings({ timeRange: tr })}
            />
          )}

          {/* Generation Controls */}
          <Box ref={generationControlsRef}>
            <AdvancedGenerationControls
              onGenerate={handleAdvancedGenerate}
              isLoading={generating}
              setIsLoading={setGenerating}
              profile={profile}
              savedPrompts={savedPrompts}
              selectedSavedPrompt={selectedSavedPrompt}
              onSelectSavedPrompt={handleSelectSavedPrompt}
              styleMode={styleMode}
              onStyleModeChange={setStyleMode}
              onPromptUpdated={() => setSavedPromptsRefresh((n) => n + 1)}
            />
          </Box>

          {/* Results */}
          {advancedResult && (
            <AdvancedResultsDisplay
              result={advancedResult}
              onFavoriteToggled={() => setSavedPromptsRefresh((n: number) => n + 1)}
              onPromptSaved={() => setSavedPromptsRefresh((n: number) => n + 1)}
            />
          )}

          {/* Hidden SavedPromptsLibrary - for loading prompts based on mode */}
          <Box display="none">
            <SavedPromptsLibrary
              refreshTrigger={savedPromptsRefresh}
              onPromptsLoaded={handlePromptsLoaded}
              favoritesOnly={styleMode === 'favorites'}
            />
          </Box>

          {/* Privacy Note */}
          <PrivacyNote />
        </VStack>
      </Container>
    </Box>
  );
}

export default App;
