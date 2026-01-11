/**
 * Main App Component for Pseuno AI
 * Two-panel layout: PromptLibrarySidebar + WorkingPromptPanel
 */

import { useState, useEffect, useReducer, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
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
  CloseButton,
} from '@chakra-ui/react';
import { HamburgerIcon } from '@chakra-ui/icons';
import { FaSpotify } from 'react-icons/fa';

import * as api from './api';
import { usePersistedSettings } from './hooks';
import PromptLibrarySidebar from './components/PromptLibrarySidebar';
import WorkingPromptPanel from './components/WorkingPromptPanel';
import NewSongView from './components/NewSongView';
import {
  workingReducer,
  createInitialWorkingState,
} from './types/workingState';

// Right pane view modes
type RightPaneMode = 'new_song' | 'song_view';

function App() {
  const toast = useToast();
  const { settings, updateSettings } = usePersistedSettings();

  // Auth state
  const [authStatus, setAuthStatus] = useState<api.AuthStatus>({ authenticated: false });
  const [authLoading, setAuthLoading] = useState(true);
  // Track if user was ever authenticated this session (to distinguish session expiry from guest usage)
  const [wasEverAuthenticated, setWasEverAuthenticated] = useState(false);
  const wasEverAuthenticatedRef = useRef(wasEverAuthenticated);
  wasEverAuthenticatedRef.current = wasEverAuthenticated;
  // Show re-auth banner when session expires (user was authenticated but got 401)
  const [showReauthBanner, setShowReauthBanner] = useState(false);

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

  // Sidebar visibility - auto-hide on small screens
  // Sidebar is 280px, content needs ~560px min, hide at md (768px) for more breathing room
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
        // Track that user was authenticated (for session expiry detection)
        if (status.authenticated) {
          setWasEverAuthenticated(true);
        }
      } catch (e) {
        console.error('Auth check failed:', e);
        // If auth check itself fails with 401, user is not authenticated
        if (e instanceof api.ApiError && e.status === 401) {
          setAuthStatus({ authenticated: false });
        }
      } finally {
        setAuthLoading(false);
      }
    }
    checkAuth();
  }, []);

  // Register global 401 handler - verify session before showing re-auth banner
  // A 401 might just be a Spotify token issue, not a session issue
  useEffect(() => {
    api.setOnUnauthorized(async () => {
      // Don't immediately log out - verify the session is actually invalid
      // by checking auth status. If session is still valid, it's just a Spotify token issue.
      try {
        const status = await api.checkAuthStatus();
        if (status.authenticated) {
          // Session is still valid - this was just a Spotify token issue
          console.log('401 received but session still valid - Spotify token may need refresh');
          // Show banner to prompt user to reconnect Spotify
          if (wasEverAuthenticatedRef.current) {
            setShowReauthBanner(true);
          }
          return;
        }
      } catch {
        // Auth check failed - session is definitely invalid
      }
      
      // Session is truly invalid
      setAuthStatus({ authenticated: false });
      setProfile(null);
      
      // Show re-auth banner only if user was previously authenticated (session expired)
      // Guest users just stay as guests without any prompt
      if (wasEverAuthenticatedRef.current) {
        console.warn('Session expired - showing re-auth banner');
        setShowReauthBanner(true);
      } else {
        console.log('401 received for guest user - staying as guest');
      }
    });
    
    // Cleanup on unmount
    return () => {
      api.setOnUnauthorized(null);
    };
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
        // Note: 401 handling is done by the global handler which verifies session validity
      } finally {
        setProfileLoading(false);
      }
    }
    loadProfile();
  }, [authStatus.authenticated, settings.timeRange]);

  // Handlers
  const handleLogin = async () => {
    // Dismiss re-auth banner since user is taking action
    setShowReauthBanner(false);
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
        const threadSummary = threads.length > 0 ? threads[0] : null;

        // Fetch full thread to get lyrics_text (source of truth)
        let fullThread: api.LyricsThread | null = null;
        if (threadSummary) {
          try {
            fullThread = await api.getLyricsThread(threadSummary.id);
          } catch (err) {
            console.error('Failed to fetch full thread:', err);
          }
        }

        dispatch({
          type: 'SET_GENERATED',
          prompt: savedPrompt,
          threadId: fullThread?.id ?? threadSummary?.id ?? null,
          threadTitle: fullThread?.title ?? threadSummary?.title,
          lyricsText: fullThread?.lyrics_text,
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
    } else {
      // No songs for this style yet → WorkingPromptPanel will auto-open draft tab
      dispatch({ type: 'CLEAR_THREAD' });
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

  // Handle unified refine response (from WorkingPromptPanel)
  const handleRefineApplied = async (response: api.UnifiedRefineResponse) => {
    // Check if persistence failed
    if (!response.updates_persisted) {
      toast({
        title: 'Changes not saved',
        description: 'The refinement was generated but failed to save to the database. Your changes may be lost.',
        status: 'error',
        duration: 6000,
      });
      // Still update the UI so user can see/copy the generated content
    }

    if (response.saved_prompt_id && response.saved_thread_id) {
      // Style changed: navigate to the new style + thread
      try {
        const savedPrompt = await api.getSavedPrompt(response.saved_prompt_id);
        const fullThread = await api.getLyricsThread(response.saved_thread_id);

        dispatch({ type: 'LOAD_STYLE_PROMPT', prompt: savedPrompt });
        dispatch({ type: 'SELECT_THREAD', thread: fullThread });

        // Refresh sidebar to show new style
        setLibraryRefresh((n) => n + 1);
      } catch (err) {
        console.error('Failed to load refined prompt:', err);
        toast({
          title: 'Refinement saved',
          description: 'Changes were saved but failed to reload. Try refreshing.',
          status: 'warning',
          duration: 4000,
        });
      }
    } else {
      // Style didn't change: update in-place
      dispatch({
        type: 'APPLY_REFINE_SNAPSHOT',
        snapshot: {
          suno_prompt: response.suno_prompt,
          lyrics_text: response.lyrics,
          lyrics_title: response.title,
          exclude: response.exclude,
          weirdness: response.weirdness,
        },
      });

      // Toast removed per user preference - silent edit
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
            onNewLyricsVariation={(prompt) => {
              // Go to song_view for this style; WorkingPromptPanel will auto-open draft tab
              if (workingState.stylePromptId !== prompt.id) {
                dispatch({ type: 'LOAD_STYLE_PROMPT', prompt });
              }
              dispatch({ type: 'CLEAR_THREAD' });
              setRightPaneMode('song_view');
            }}
            onNewPrompt={() => {
              setRightPaneMode('new_song');
              setNewSongResetKey(k => k + 1);
            }}
            onCloseSidebar={() => handleToggleSidebar(false)}
            authStatus={authStatus}
            onLogin={handleLogin}
            onThreadRenamed={(threadId, newTitle) => {
              // If the renamed thread is currently active, update the WorkingState
              if (workingState.lyricsThreadId === threadId) {
                dispatch({ type: 'EDIT_LYRICS_TITLE', value: newTitle });
                dispatch({ type: 'MARK_CLEAN', which: 'lyrics' });
              }
              // Trigger refresh of WorkingPromptPanel's threads
              setLibraryRefresh((n) => n + 1);
            }}
            onThreadDeleted={(threadId) => {
              // If the deleted thread was the active one, clear the right pane
              if (workingState.lyricsThreadId === threadId) {
                dispatch({ type: 'CLEAR_THREAD' });
              }
              // Trigger refresh of WorkingPromptPanel's threads
              setLibraryRefresh((n) => n + 1);
            }}
            onStyleRenamed={(promptId, newTitle) => {
              // If the renamed style is currently active, update the WorkingState
              if (workingState.stylePromptId === promptId) {
                dispatch({ type: 'EDIT_STYLE_FIELD', field: 'title', value: newTitle });
                dispatch({ type: 'MARK_CLEAN', which: 'style' });
              }
            }}
            onStyleDeleted={(promptId) => {
              // If the deleted style was the active one, go back to new song view
              if (workingState.stylePromptId === promptId) {
                dispatch({ type: 'RESET' });
                setRightPaneMode('new_song');
              }
            }}
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

        {rightPaneMode === 'song_view' && (
          <WorkingPromptPanel
            state={workingState}
            dispatch={dispatch}
            onRefineApplied={handleRefineApplied}
            onThreadUpdated={() => {
              // Refresh sidebar when a thread is renamed/updated from the right pane
              setLibraryRefresh((n) => n + 1);
            }}
            refreshKey={libraryRefresh}
          />
        )}
      </Flex>

      {/* Re-authentication banner - shown when session expires */}
      {showReauthBanner && (
        <Box
          position="fixed"
          bottom={0}
          left={sidebarOpen ? '280px' : 0}
          right={0}
          bg="rgba(60, 28, 28, 0.7)"
          backdropFilter="blur(8px)"
          borderTop="1px solid"
          borderColor="rgba(100, 40, 40, 0.4)"
          px={4}
          py={2}
          zIndex={50}
        >
          <HStack justify="center" spacing={4}>
            <HStack spacing={2}>
              <Box color="red.400">
                <FaSpotify size={14} />
              </Box>
              <Text fontSize="sm" color="red.300">
                Reconnect to access your songs & personalized features
              </Text>
            </HStack>
            <Button
              leftIcon={<FaSpotify />}
              size="xs"
              bg="rgba(130, 45, 45, 0.7)"
              color="gray.100"
              _hover={{ bg: 'rgba(150, 55, 55, 0.85)' }}
              onClick={handleLogin}
            >
              Reconnect
            </Button>
            <CloseButton
              size="sm"
              color="red.400"
              onClick={() => setShowReauthBanner(false)}
              aria-label="Dismiss"
              _hover={{ color: 'gray.200', bg: 'rgba(80, 35, 35, 0.5)' }}
            />
          </HStack>
        </Box>
      )}
    </Box>
  );
}

export default App;
