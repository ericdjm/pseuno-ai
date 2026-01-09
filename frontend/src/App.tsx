/**
 * Main App Component for Pseuno AI
 * Two-panel layout: PromptLibrarySidebar + WorkingPromptPanel
 */

import { useState, useEffect, useReducer } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Flex,
  useToast,
  IconButton,
  Tooltip,
  Avatar,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverCloseButton,
  PopoverHeader,
  PopoverBody,
  Spinner,
  useBreakpointValue,
} from '@chakra-ui/react';
import { HamburgerIcon } from '@chakra-ui/icons';
import { FaSpotify } from 'react-icons/fa';

import * as api from './api';
import { usePersistedSettings } from './hooks';
import { TasteDisplay } from './components/TasteDisplay';
import AdvancedGenerationControls from './components/AdvancedGenerationControls';
import PromptLibrarySidebar from './components/PromptLibrarySidebar';
import WorkingPromptPanel from './components/WorkingPromptPanel';
import {
  workingReducer,
  createInitialWorkingState,
} from './types/workingState';

function App() {
  const toast = useToast();
  const { settings, updateSettings } = usePersistedSettings();

  // Auth state
  const [authStatus, setAuthStatus] = useState<api.AuthStatus>({ authenticated: false });
  const [authLoading, setAuthLoading] = useState(true);

  // Profile state
  const [profile, setProfile] = useState<api.SpotifyProfileResponse | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [, setProfileError] = useState<string | null>(null);

  // Generation state
  const [generating, setGenerating] = useState(false);

  // WorkingState (single source of truth for current prompt/song)
  const [workingState, dispatch] = useReducer(workingReducer, undefined, createInitialWorkingState);

  // Prompt library refresh trigger
  const [libraryRefresh, setLibraryRefresh] = useState(0);

  // Show generation controls in right panel (instead of WorkingPromptPanel)
  const [showNewPromptPanel, setShowNewPromptPanel] = useState(false);

  // Sidebar visibility - auto-hide on small screens
  const isLargeScreen = useBreakpointValue({ base: false, md: true });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userToggledSidebar, setUserToggledSidebar] = useState(false);

  // Auto-hide sidebar on small screens, restore on large screens (unless user manually closed it)
  useEffect(() => {
    if (isLargeScreen === undefined) return; // Still loading
    if (!userToggledSidebar) {
      setSidebarOpen(isLargeScreen);
    }
  }, [isLargeScreen, userToggledSidebar]);

  const handleToggleSidebar = (open: boolean) => {
    setSidebarOpen(open);
    setUserToggledSidebar(true);
  };

  // Legacy: still needed for generation controls
  const [savedPrompts] = useState<api.SavedSunoPrompt[]>([]);
  const [selectedSavedPrompt, setSelectedSavedPrompt] = useState<api.SavedSunoPrompt | null>(null);

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

  // Load profile when authenticated
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
    dispatch({ type: 'RESET' });
    toast({
      title: 'Logged out',
      status: 'info',
      duration: 2000,
    });
  };

  // Handle generation complete
  const handleAdvancedGenerate = async (result: api.AdvancedGenerateResponse) => {
    setShowNewPromptPanel(false);

    // Fetch the saved prompt to get full details
    if (result.prompt_id) {
      try {
        const savedPrompt = await api.getSavedPrompt(result.prompt_id);
        // Get the threads (should have one initial thread)
        const threads = await api.getPromptThreads(result.prompt_id);
        const threadId = threads.length > 0 ? threads[0].id : null;

        dispatch({
          type: 'SET_GENERATED',
          prompt: savedPrompt,
          threadId,
        });
      } catch (err) {
        console.error('Failed to load generated prompt:', err);
        // Fallback: just use the result data
        dispatch({
          type: 'SET_GENERATED',
          prompt: {
            id: result.prompt_id,
            suno_prompt: result.suno_prompt,
            lyrics: result.lyrics,
            exclude: result.exclude,
            weirdness: result.weirdness,
            style_influence: result.style_influence,
            title: result.concept_title,
            notes: null,
            is_favorite: result.is_favorite,
            auto_tags: result.auto_tags || [],
            generation_id: result.generation_id,
            visibility: 'private',
            share_id: '',
            parent_prompt_id: null,
            source_action: 'generate',
            threads_count: 1,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          } as api.SavedSunoPrompt,
          threadId: null,
        });
      }
    }

    // Refresh library
    setLibraryRefresh((n) => n + 1);
  };

  // Handle selecting a StylePrompt from sidebar
  const handleSelectStylePrompt = async (
    prompt: api.SavedSunoPrompt,
    threads: api.LyricsThreadSummary[]
  ) => {
    dispatch({ type: 'LOAD_STYLE_PROMPT', prompt });

    // Auto-select the most recent thread if available
    if (threads.length > 0) {
      const mostRecent = threads[0]; // Already sorted by updated_at desc
      try {
        const fullThread = await api.getLyricsThread(mostRecent.id);
        dispatch({ type: 'SELECT_THREAD', thread: fullThread });
      } catch (err) {
        console.error('Failed to load thread:', err);
      }
    }
  };

  // Handle selecting a specific thread
  const handleSelectThread = async (
    prompt: api.SavedSunoPrompt,
    threadSummary: api.LyricsThreadSummary
  ) => {
    // If different prompt, load it first
    if (workingState.stylePromptId !== prompt.id) {
      dispatch({ type: 'LOAD_STYLE_PROMPT', prompt });
    }

    try {
      const fullThread = await api.getLyricsThread(threadSummary.id);
      dispatch({ type: 'SELECT_THREAD', thread: fullThread });
    } catch (err) {
      console.error('Failed to load thread:', err);
      toast({
        title: 'Failed to load song',
        status: 'error',
        duration: 2000,
      });
    }
  };

  // Handle new lyrics variation
  const handleNewLyricsVariation = async (promptId: number) => {
    try {
      // Create a new thread, optionally seeding from current thread if same prompt
      const seedFromThreadId =
        workingState.stylePromptId === promptId && workingState.lyricsThreadId
          ? workingState.lyricsThreadId
          : undefined;

      const newThread = await api.createLyricsThread({
        style_prompt_id: promptId,
        seed_from_thread_id: seedFromThreadId,
      });

      dispatch({ type: 'SELECT_THREAD', thread: newThread });

      // Refresh library to show new thread
      setLibraryRefresh((n) => n + 1);

      toast({
        title: 'New lyrics variation created',
        status: 'success',
        duration: 2000,
      });
    } catch (err) {
      console.error('Failed to create lyrics variation:', err);
      toast({
        title: 'Failed to create variation',
        status: 'error',
        duration: 2000,
      });
    }
  };

  return (
    <Box h="100vh" w="100vw" bg="gray.900" display="flex" flexDirection="column" overflow="hidden" position="fixed" top={0} left={0}>
      {/* Floating profile avatar - top right */}
      <Box position="absolute" top={3} right={3} zIndex={10}>
            {authLoading ? (
              <Spinner size="sm" />
            ) : (
              <Popover placement="bottom-end">
                <PopoverTrigger>
              <Button variant="ghost" p={0} minW="auto" aria-label="Profile menu">
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
                      colorScheme="green"
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
      </Box>

      {/* Floating sidebar toggle when closed */}
      {!sidebarOpen && (
        <Tooltip label="Open sidebar" placement="right">
          <IconButton
            aria-label="Open sidebar"
            icon={<HamburgerIcon />}
            position="absolute"
            top={3}
            left={3}
            size="sm"
            variant="ghost"
            color="gray.400"
            _hover={{ color: 'white', bg: 'gray.700' }}
            onClick={() => handleToggleSidebar(true)}
            zIndex={10}
          />
        </Tooltip>
      )}

      {/* Two-panel layout */}
      <Flex flex={1} overflow="hidden">
        {/* Left: Prompt Library Sidebar */}
        {sidebarOpen && (
          <PromptLibrarySidebar
            refreshTrigger={libraryRefresh}
            activeStylePromptId={workingState.stylePromptId}
            activeThreadId={workingState.lyricsThreadId}
            onSelectStylePrompt={handleSelectStylePrompt}
            onSelectThread={handleSelectThread}
            onNewLyricsVariation={handleNewLyricsVariation}
            onNewPrompt={() => setShowNewPromptPanel(true)}
            onCloseSidebar={() => handleToggleSidebar(false)}
            authStatus={authStatus}
            onLogin={handleLogin}
          />
        )}


        {/* Right: Either New Prompt Generation or Working Prompt Panel */}
        {showNewPromptPanel ? (
          <Box flex={1} overflow="auto" bg="gray.900" py={4} pt={14} px={4} minW={0}>
          <Box maxW="800px" mx="auto">
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Generate New Prompt</Heading>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setShowNewPromptPanel(false)}
                >
                  Cancel
                </Button>
              </HStack>

              {/* Show taste display if authenticated */}
          {authStatus.authenticated && (
            <TasteDisplay
              profile={profile}
              loading={profileLoading}
              timeRange={settings.timeRange}
              onTimeRangeChange={(tr) => updateSettings({ timeRange: tr })}
            />
          )}

              {/* Generation Controls - new style only mode */}
            <AdvancedGenerationControls
              onGenerate={handleAdvancedGenerate}
              isLoading={generating}
              setIsLoading={setGenerating}
              profile={profile}
              savedPrompts={savedPrompts}
              selectedSavedPrompt={selectedSavedPrompt}
                onSelectSavedPrompt={setSelectedSavedPrompt}
                styleMode="songStylePrompt"
                onStyleModeChange={() => {}}
                onPromptUpdated={() => setLibraryRefresh((n) => n + 1)}
                newStyleOnly
              />
            </VStack>
          </Box>
          </Box>
        ) : (
          <WorkingPromptPanel
            state={workingState}
            dispatch={dispatch}
            onPromptSaved={() => setLibraryRefresh((n) => n + 1)}
            onFavoriteToggled={() => setLibraryRefresh((n) => n + 1)}
          />
        )}
      </Flex>
    </Box>
  );
}

export default App;
