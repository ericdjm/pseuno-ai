/**
 * Main App Component for Pseuno AI
 * Two-panel layout: PromptLibrarySidebar + WorkingPromptPanel
 */

import { useState, useEffect, useReducer } from 'react';
import {
  Box,
  VStack,
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
import PromptLibrarySidebar from './components/PromptLibrarySidebar';
import WorkingPromptPanel from './components/WorkingPromptPanel';
import NewSongView from './components/NewSongView';
import NewLyricsForStyleView from './components/NewLyricsForStyleView';
import {
  workingReducer,
  createInitialWorkingState,
} from './types/workingState';

// Right pane view modes
type RightPaneMode = 'new_song' | 'new_lyrics_for_style' | 'song_view';

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

  // WorkingState (single source of truth for current prompt/song)
  const [workingState, dispatch] = useReducer(workingReducer, undefined, createInitialWorkingState);

  // Prompt library refresh trigger
  const [libraryRefresh, setLibraryRefresh] = useState(0);

  // Right pane view mode
  const [rightPaneMode, setRightPaneMode] = useState<RightPaneMode>('new_song');
  
  // Reset key for NewSongView - increment to clear inputs
  const [newSongResetKey, setNewSongResetKey] = useState(0);
  
  // For new_lyrics_for_style mode, we need to know which style we're generating for
  const [newLyricsForStyleId, setNewLyricsForStyleId] = useState<number | null>(null);

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

  // Default to New Song when nothing is selected (avoid the empty "No prompt loaded" surface).
  useEffect(() => {
    if (rightPaneMode !== 'song_view') return;
    if (!workingState.stylePromptId && !workingState.lyricsThreadId) {
      setRightPaneMode('new_song');
    }
  }, [rightPaneMode, workingState.stylePromptId, workingState.lyricsThreadId]);

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
    // Fetch the saved prompt to get full details, then switch to song_view.
    // We must dispatch BEFORE setRightPaneMode('song_view') because there's a useEffect
    // that resets to 'new_song' if song_view is active but no prompt is loaded yet.
    if (result.prompt_id) {
      try {
        const savedPrompt = await api.getSavedPrompt(result.prompt_id);
        // Get the threads (should have one initial thread)
        const threads = await api.getPromptThreads(result.prompt_id);
        const thread = threads.length > 0 ? threads[0] : null;

        dispatch({
          type: 'SET_GENERATED',
          prompt: savedPrompt,
          threadId: thread?.id ?? null,
          threadTitle: thread?.title,
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

    // Now that workingState has a prompt loaded, switch to song_view
    setRightPaneMode('song_view');

    // Refresh library
    setLibraryRefresh((n) => n + 1);
  };

  // Handle selecting a StylePrompt from sidebar
  const handleSelectStylePrompt = async (
    prompt: api.SavedSunoPrompt,
    threads: api.LyricsThreadSummary[]
  ) => {
    dispatch({ type: 'LOAD_STYLE_PROMPT', prompt });
    setRightPaneMode('song_view');

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
    setRightPaneMode('song_view');

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

  // Handle opening new lyrics variation view
  const handleNewLyricsVariation = (prompt: api.SavedSunoPrompt) => {
    // Ensure workingState has the correct style prompt loaded
    if (workingState.stylePromptId !== prompt.id) {
      dispatch({ type: 'LOAD_STYLE_PROMPT', prompt });
    }
    setNewLyricsForStyleId(prompt.id);
    setRightPaneMode('new_lyrics_for_style');
  };

  // Handle new lyrics generation complete (from NewLyricsForStyleView)
  const handleNewLyricsGenerated = (thread: api.LyricsThread) => {
    // Dispatch first to populate workingState, then switch view
    dispatch({ type: 'SELECT_THREAD', thread });
    setRightPaneMode('song_view');
    setLibraryRefresh((n) => n + 1);
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
            onNewPrompt={() => {
              setRightPaneMode('new_song');
              setNewSongResetKey(k => k + 1);
            }}
            onCloseSidebar={() => handleToggleSidebar(false)}
            authStatus={authStatus}
            onLogin={handleLogin}
          />
        )}


        {/* Right: View based on rightPaneMode */}
        {rightPaneMode === 'new_song' && (
          <NewSongView
            onGenerate={handleAdvancedGenerate}
            onCancel={() => setRightPaneMode('song_view')}
            profile={profile}
            profileLoading={profileLoading}
            isAuthenticated={authStatus.authenticated}
            timeRange={settings.timeRange}
            onTimeRangeChange={(tr) => updateSettings({ timeRange: tr })}
            resetKey={newSongResetKey}
          />
        )}

        {rightPaneMode === 'new_lyrics_for_style' && newLyricsForStyleId && (
          <NewLyricsForStyleView
            stylePromptId={newLyricsForStyleId}
            stylePromptText={workingState.styleFields.suno_prompt}
            styleTitle={workingState.styleFields.title}
            onGenerate={handleNewLyricsGenerated}
            onCancel={() => setRightPaneMode('song_view')}
          />
        )}

        {rightPaneMode === 'song_view' && (
          <WorkingPromptPanel
            state={workingState}
            dispatch={dispatch}
          />
        )}
      </Flex>
    </Box>
  );
}

export default App;
