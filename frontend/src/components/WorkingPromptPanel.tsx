/**
 * WorkingPromptPanel - Right panel showing the current Style and its Songs.
 * 
 * Layout:
 * 1. Style Name (title) with Suno link
 * 2. Style Section (collapsible) with Refine button, Exclude, Weirdness/Influence
 * 3. Song Tabs - all LyricsThreads for this StylePrompt
 * 4. Song Content - title, Edit button, lyrics textarea with autosave
 */

import { useState, useRef, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Textarea,
  IconButton,
  Badge,
  Divider,
  useToast,
  Spinner,
  Link,
  Collapse,
  Button,
  Tooltip,
  Input,
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import { CopyIcon, ChevronRightIcon, ChevronDownIcon, ExternalLinkIcon, EditIcon, AddIcon, DeleteIcon } from '@chakra-ui/icons';
import { LuSparkles } from 'react-icons/lu';
import type { WorkingState, WorkingAction } from '../types/workingState';
import { 
  updateLyricsThread, 
  refineAll, 
  UnifiedRefineResponse, 
  getPromptThreads, 
  LyricsThreadSummary,
  getLyricsThread,
  deleteLyricsThread,
  updateSavedPrompt,
} from '../api';

interface WorkingPromptPanelProps {
  state: WorkingState;
  dispatch: React.Dispatch<WorkingAction>;
  onRefineApplied?: (response: UnifiedRefineResponse) => Promise<void>;
  onRequestNewLyricsVariation?: (stylePromptId: number) => void;
  onThreadUpdated?: () => void;
  refreshKey?: number;
}

export default function WorkingPromptPanel({
  state,
  dispatch,
  onRefineApplied,
  onRequestNewLyricsVariation,
  onThreadUpdated,
  refreshKey,
}: WorkingPromptPanelProps) {
  const toast = useToast();

  // All threads for this StylePrompt
  const [threads, setThreads] = useState<LyricsThreadSummary[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingThread, setDeletingThread] = useState(false);
  const [threadToDelete, setThreadToDelete] = useState<{ id: number; title: string } | null>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);

  // Collapsible sections
  const [styleExpanded, setStyleExpanded] = useState(false);
  const [excludeExpanded, setExcludeExpanded] = useState(false);

  // Style Refine composer state (creates new StylePrompt)
  const [styleRefineOpen, setStyleRefineOpen] = useState(false);
  const [styleRefineText, setStyleRefineText] = useState('');
  const [isRefiningStyle, setIsRefiningStyle] = useState(false);
  const styleRefineInputRef = useRef<HTMLInputElement>(null);

  // Lyrics Edit composer state (updates in-place)
  const [lyricsEditOpen, setLyricsEditOpen] = useState(false);
  const [lyricsEditText, setLyricsEditText] = useState('');
  const [isEditingLyrics, setIsEditingLyrics] = useState(false);
  const lyricsEditInputRef = useRef<HTMLInputElement>(null);

  // Lyrics save debounce
  const [savingLyrics, setSavingLyrics] = useState(false);
  const lyricsSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Song renaming state
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Style renaming state
  const [isRenamingStyle, setIsRenamingStyle] = useState(false);
  const [styleRenameValue, setStyleRenameValue] = useState('');
  const styleRenameInputRef = useRef<HTMLInputElement>(null);

  // Fetch all threads when stylePromptId changes
  useEffect(() => {
    if (!state.stylePromptId) {
      setThreads([]);
      return;
    }

    const fetchThreads = async () => {
      setLoadingThreads(true);
      try {
        const fetchedThreads = await getPromptThreads(state.stylePromptId!);
        setThreads(fetchedThreads);
      } catch (err) {
        console.error('Failed to fetch threads:', err);
        setThreads([]);
      } finally {
        setLoadingThreads(false);
      }
    };

    fetchThreads();
  }, [state.stylePromptId, state.lyricsThreadId, refreshKey]);

  // Reset refine/edit state when navigating to a different prompt
  useEffect(() => {
    setStyleRefineOpen(false);
    setStyleRefineText('');
    setLyricsEditOpen(false);
    setLyricsEditText('');
  }, [state.stylePromptId]);

  // Build Suno URL with style as query param
  const buildSunoUrl = () => {
    const baseUrl = 'https://suno.com/create';
    const params = new URLSearchParams();
    if (state.styleFields.suno_prompt) {
      params.set('style', state.styleFields.suno_prompt);
    }
    return `${baseUrl}?${params.toString()}`;
  };

  // Handle tab selection
  const handleTabChange = async (index: number) => {
    // If clicking "+ New" tab (last tab), create a new thread
    if (index === threads.length) {
      if (state.stylePromptId && onRequestNewLyricsVariation) {
        onRequestNewLyricsVariation(state.stylePromptId);
      }
      return;
    }

    const selectedThread = threads[index];
    if (!selectedThread || selectedThread.id === state.lyricsThreadId) return;

    // Fetch full thread data and update state
    try {
      const fullThread = await getLyricsThread(selectedThread.id);
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

  const openDeleteDialog = (threadId: number, title: string) => {
    setThreadToDelete({ id: threadId, title });
    setDeleteDialogOpen(true);
  };

  const handleConfirmDeleteSong = async () => {
    if (!threadToDelete) return;
    const deletingId = threadToDelete.id;
    const wasSelected = deletingId === state.lyricsThreadId;

    setDeletingThread(true);
    try {
      await deleteLyricsThread(deletingId);

      const prevThreads = threads;
      const deletedIndex = prevThreads.findIndex((t) => t.id === deletingId);
      const nextThreads = prevThreads.filter((t) => t.id !== deletingId);
      setThreads(nextThreads);

      // If we deleted the selected thread, pick a neighbor; if none, clear selection (style remains).
      if (wasSelected) {
        if (nextThreads.length === 0) {
          dispatch({ type: 'CLEAR_THREAD' });
          if (state.stylePromptId && onRequestNewLyricsVariation) {
            onRequestNewLyricsVariation(state.stylePromptId);
          }
        } else {
          const candidateIndex = Math.max(0, Math.min(deletedIndex - 1, nextThreads.length - 1));
          const candidate = nextThreads[candidateIndex];
          const fullThread = await getLyricsThread(candidate.id);
          dispatch({ type: 'SELECT_THREAD', thread: fullThread });
        }
      }

      toast({
        title: 'Song deleted',
        status: 'success',
        duration: 2000,
      });
    } catch (err) {
      console.error('Failed to delete song:', err);
      toast({
        title: 'Failed to delete song',
        status: 'error',
        duration: 2500,
      });
    } finally {
      setDeletingThread(false);
      setDeleteDialogOpen(false);
      setThreadToDelete(null);
    }
  };

  // Start renaming the current song
  const handleStartRename = () => {
    setRenameValue(state.lyricsFields.lyrics_title || '');
    setIsRenaming(true);
    setTimeout(() => renameInputRef.current?.focus(), 50);
  };

  // Save renamed song title
  const handleSaveRename = async () => {
    if (!state.lyricsThreadId) return;
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === state.lyricsFields.lyrics_title) {
      setIsRenaming(false);
      return;
    }

    try {
      const updated = await updateLyricsThread(state.lyricsThreadId, { title: trimmed });
      dispatch({ type: 'SAVE_THREAD_SUCCESS', thread: updated });
      // Update threads list
      setThreads((prev) => prev.map((t) => (t.id === updated.id ? { ...t, title: updated.title } : t)));
      // Notify parent to refresh sidebar
      onThreadUpdated?.();
      toast({
        title: 'Song renamed',
        status: 'success',
        duration: 1500,
      });
    } catch (err) {
      console.error('Failed to rename song:', err);
      toast({
        title: 'Failed to rename song',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setIsRenaming(false);
    }
  };

  // Start renaming the style
  const handleStartStyleRename = () => {
    setStyleRenameValue(state.styleFields.title || '');
    setIsRenamingStyle(true);
    setTimeout(() => styleRenameInputRef.current?.focus(), 50);
  };

  // Save renamed style title
  const handleSaveStyleRename = async () => {
    if (!state.stylePromptId) return;
    const trimmed = styleRenameValue.trim();
    if (!trimmed || trimmed === state.styleFields.title) {
      setIsRenamingStyle(false);
      return;
    }

    try {
      await updateSavedPrompt(state.stylePromptId, { title: trimmed });
      dispatch({ type: 'EDIT_STYLE_FIELD', field: 'title', value: trimmed });
      // Notify parent to refresh sidebar
      onThreadUpdated?.();
      toast({
        title: 'Style renamed',
        status: 'success',
        duration: 1500,
      });
    } catch (err) {
      console.error('Failed to rename style:', err);
      toast({
        title: 'Failed to rename style',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setIsRenamingStyle(false);
    }
  };

  // Debounced save for lyrics
  const handleLyricsChange = (value: string) => {
    dispatch({ type: 'EDIT_LYRICS_TEXT', value });

    // Debounce save
    if (lyricsSaveTimeoutRef.current) {
      clearTimeout(lyricsSaveTimeoutRef.current);
    }
    lyricsSaveTimeoutRef.current = setTimeout(() => {
      saveLyrics(value);
    }, 2000);
  };

  const saveLyrics = async (lyrics_text: string) => {
    if (!state.lyricsThreadId) return;
    setSavingLyrics(true);
    try {
      const updated = await updateLyricsThread(state.lyricsThreadId, { lyrics_text });
      dispatch({ type: 'SAVE_THREAD_SUCCESS', thread: updated });
      
      // Update threads list with new title
      setThreads(prev => prev.map(t => 
        t.id === updated.id ? { ...t, title: updated.title } : t
      ));
    } catch (err) {
      console.error('Failed to save lyrics:', err);
      toast({
        title: 'Failed to save lyrics',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setSavingLyrics(false);
    }
  };

  // Handle STYLE refine submission (creates new StylePrompt + forks thread)
  const handleStyleRefineSubmit = async () => {
    if (!styleRefineText.trim()) {
      toast({
        title: 'Please describe how to change the style',
        status: 'warning',
        duration: 2000,
      });
      return;
    }

    if (!state.stylePromptId) {
      toast({
        title: 'No prompt loaded',
        status: 'error',
        duration: 2000,
      });
      return;
    }

    setIsRefiningStyle(true);

    toast({
      title: 'Refining style...',
      description: 'Creating new style version',
      status: 'loading',
      duration: null,
      id: 'refine-style-progress',
    });

    try {
      const response = await refineAll({
        suno_prompt: state.styleFields.suno_prompt,
        lyrics: state.lyricsFields.lyrics_text,
        exclude: state.styleFields.exclude,
        title: state.lyricsFields.lyrics_title,
        weirdness: state.styleFields.weirdness,
        style_influence: state.styleFields.style_influence,
        auto_tags: state.styleFields.auto_tags,
        base_prompt_id: state.stylePromptId ?? undefined,
        base_thread_id: state.lyricsThreadId ?? undefined,
        change_request: styleRefineText.trim(),
        refine_target: 'style',
      });

      setStyleRefineOpen(false);
      setStyleRefineText('');
      toast.close('refine-style-progress');

      if (onRefineApplied) {
        await onRefineApplied(response);
      }
    } catch (err) {
      console.error('Style refine failed:', err);
      toast.close('refine-style-progress');
      toast({
        title: 'Style refinement failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error',
        duration: 4000,
      });
    } finally {
      setIsRefiningStyle(false);
    }
  };

  // Handle LYRICS edit submission (updates current LyricsThread in-place)
  const handleLyricsEditSubmit = async () => {
    if (!lyricsEditText.trim()) {
      toast({
        title: 'Please describe how to edit the lyrics',
        status: 'warning',
        duration: 2000,
      });
      return;
    }

    if (!state.lyricsThreadId) {
      toast({
        title: 'No lyrics thread loaded',
        status: 'error',
        duration: 2000,
      });
      return;
    }

    setIsEditingLyrics(true);

    toast({
      title: 'Editing lyrics...',
      description: 'Updating your lyrics',
      status: 'loading',
      duration: null,
      id: 'edit-lyrics-progress',
    });

    try {
      const response = await refineAll({
        suno_prompt: state.styleFields.suno_prompt,
        lyrics: state.lyricsFields.lyrics_text,
        exclude: state.styleFields.exclude,
        title: state.lyricsFields.lyrics_title,
        weirdness: state.styleFields.weirdness,
        style_influence: state.styleFields.style_influence,
        auto_tags: state.styleFields.auto_tags,
        base_prompt_id: state.stylePromptId ?? undefined,
        base_thread_id: state.lyricsThreadId ?? undefined,
        change_request: lyricsEditText.trim(),
        refine_target: 'lyrics',
      });

      setLyricsEditOpen(false);
      setLyricsEditText('');
      toast.close('edit-lyrics-progress');

      if (onRefineApplied) {
        await onRefineApplied(response);
      }
    } catch (err) {
      console.error('Lyrics edit failed:', err);
      toast.close('edit-lyrics-progress');
      toast({
        title: 'Lyrics edit failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error',
        duration: 4000,
      });
    } finally {
      setIsEditingLyrics(false);
    }
  };

  // Copy to clipboard
  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: `${label} copied!`,
      status: 'success',
      duration: 2000,
    });
  };

  // If no prompt loaded, show empty state
  if (!state.stylePromptId && state.mode === 'new') {
    return (
      <Box flex={1} display="flex" alignItems="center" justifyContent="center" bg="gray.900" pt={10} minW={0}>
        <VStack spacing={4} color="gray.500">
          <Text fontSize="xl">No prompt loaded</Text>
          <Text fontSize="sm">Generate a new prompt or select one from the library</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box flex={1} overflow="auto" bg="gray.900" py={6} pt="10vh" px={4} minW={0} display="flex" alignItems="flex-start" justifyContent="center">
      <Box maxW="560px" w="100%">
        <VStack spacing={4} align="stretch">
          {/* === STYLE HEADER === */}
          <HStack justify="space-between" align="center">
            {isRenamingStyle ? (
              <Input
                ref={styleRenameInputRef}
                value={styleRenameValue}
                onChange={(e) => setStyleRenameValue(e.target.value)}
                size="md"
                fontWeight="semibold"
                fontSize="xl"
                variant="flushed"
                borderColor="purple.400"
                _focus={{ borderColor: 'purple.400', boxShadow: 'none' }}
                maxW="400px"
                spellCheck={false}
                onBlur={handleSaveStyleRename}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSaveStyleRename();
                  }
                  if (e.key === 'Escape') {
                    setIsRenamingStyle(false);
                  }
                }}
              />
            ) : (
              <Tooltip label="Double-click to rename" placement="top" hasArrow>
                <Text
                  fontWeight="semibold"
                  fontSize="xl"
                  cursor="text"
                  onDoubleClick={handleStartStyleRename}
                  _hover={{ color: 'gray.300' }}
                  transition="color 0.1s"
                >
                  {state.styleFields.title || 'Untitled Style'}
                </Text>
              </Tooltip>
            )}
            <Link
              href={buildSunoUrl()}
              isExternal
              color="gray.400"
              fontSize="sm"
              _hover={{ color: 'purple.300' }}
            >
              Open in Suno <ExternalLinkIcon mx="2px" />
            </Link>
          </HStack>

          {/* === STYLE SECTION (Collapsible) === */}
          <Box>
            <HStack
              justify="space-between"
              cursor="pointer"
              onClick={() => setStyleExpanded(!styleExpanded)}
              py={1}
            >
              <HStack spacing={2}>
                {styleExpanded ? (
                  <ChevronDownIcon color="gray.500" />
                ) : (
                  <ChevronRightIcon color="gray.500" />
                )}
                <Text fontWeight="bold" fontSize="sm">Style</Text>
                {!styleExpanded && (
                  <Text fontSize="xs" color="gray.500">
                    Weird {state.styleFields.weirdness}% · Influence {state.styleFields.style_influence}%
                  </Text>
                )}
              </HStack>
              <HStack spacing={3} onClick={(e) => e.stopPropagation()}>
                {/* Refine Style button */}
                <Tooltip label="Refine style with AI (creates new version)" placement="top" hasArrow>
                  <HStack
                    spacing={1}
                    cursor="pointer"
                    onClick={(e) => {
                      e.stopPropagation();
                      setStyleRefineOpen(!styleRefineOpen);
                      if (!styleRefineOpen) {
                        setTimeout(() => styleRefineInputRef.current?.focus(), 100);
                      }
                    }}
                    px={1.5}
                    py={0.5}
                    borderRadius="md"
                    bg={styleRefineOpen ? 'purple.800' : 'transparent'}
                    _hover={{ bg: styleRefineOpen ? 'purple.700' : 'whiteAlpha.100' }}
                    transition="all 0.15s"
                  >
                    <Box as={LuSparkles} boxSize={3.5} color={styleRefineOpen ? 'purple.200' : 'gray.500'} />
                    <Text fontSize="xs" color={styleRefineOpen ? 'purple.200' : 'gray.500'}>
                      Refine
                    </Text>
                  </HStack>
                </Tooltip>
                <IconButton
                  aria-label="Copy style"
                  icon={<CopyIcon />}
                  size="xs"
                  variant="ghost"
                  color="gray.500"
                  _hover={{ color: 'white' }}
                  onClick={() => copyToClipboard(state.styleFields.suno_prompt, 'Style')}
                />
              </HStack>
            </HStack>

            {/* Style Refine Input */}
            <Collapse in={styleRefineOpen} animateOpacity>
              <Box bg="purple.900" borderRadius="md" p={3} mt={2} border="1px solid" borderColor="purple.700">
                <VStack spacing={2} align="stretch">
                  <Input
                    ref={styleRefineInputRef}
                    value={styleRefineText}
                    onChange={(e) => setStyleRefineText(e.target.value)}
                    placeholder='e.g. "add more synths", "make it darker", "less electronic"'
                    bg="gray.900"
                    borderColor="purple.600"
                    _hover={{ borderColor: 'purple.500' }}
                    _focus={{ borderColor: 'purple.400', boxShadow: 'none' }}
                    fontSize="sm"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && styleRefineText.trim()) {
                        e.preventDefault();
                        handleStyleRefineSubmit();
                      }
                      if (e.key === 'Escape') {
                        setStyleRefineOpen(false);
                        setStyleRefineText('');
                      }
                    }}
                  />
                  <HStack justify="space-between">
                    <Text fontSize="xs" color="purple.300">
                      Creates a new style version
                    </Text>
                    <HStack spacing={2}>
                      <Button
                        size="xs"
                        variant="ghost"
                        color="gray.400"
                        _hover={{ color: 'white' }}
                        onClick={() => {
                          setStyleRefineOpen(false);
                          setStyleRefineText('');
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        size="xs"
                        bg="purple.600"
                        color="white"
                        _hover={{ bg: 'purple.500' }}
                        onClick={handleStyleRefineSubmit}
                        isLoading={isRefiningStyle}
                        loadingText="Refining..."
                        isDisabled={!styleRefineText.trim()}
                      >
                        Refine
                      </Button>
                    </HStack>
                  </HStack>
                </VStack>
              </Box>
            </Collapse>

            <Collapse in={styleExpanded} animateOpacity>
              <VStack spacing={3} align="stretch" mt={2}>
                {/* Weirdness/Influence when expanded */}
                <HStack spacing={4}>
                  <Text fontSize="xs" color="gray.400">
                    Weirdness: {state.styleFields.weirdness}%
                  </Text>
                  <Text fontSize="xs" color="gray.400">
                    Style Influence: {state.styleFields.style_influence}%
                  </Text>
                </HStack>

                {/* Style prompt content */}
                <Box
                  bg="gray.800"
                  borderRadius="md"
                  p={2}
                  fontSize="sm"
                  color="gray.300"
                  maxH="200px"
                  overflowY="auto"
                >
                  {state.styleFields.suno_prompt || '(empty)'}
                </Box>
              </VStack>
            </Collapse>
          </Box>

          {/* Exclude section - always visible outside of Style collapse */}
          {state.styleFields.exclude && (
            <Box>
              <HStack
                justify="space-between"
                cursor="pointer"
                onClick={() => setExcludeExpanded(!excludeExpanded)}
                py={1}
              >
                <HStack spacing={2}>
                  {excludeExpanded ? (
                    <ChevronDownIcon color="gray.500" />
                  ) : (
                    <ChevronRightIcon color="gray.500" />
                  )}
                  <Text fontWeight="bold" fontSize="sm">Exclude</Text>
                  {!excludeExpanded && (
                    <Text fontSize="xs" color="gray.500">
                      {state.styleFields.exclude.split(',').length} items
                    </Text>
                  )}
                </HStack>
                <IconButton
                  aria-label="Copy exclude"
                  icon={<CopyIcon />}
                  size="xs"
                  variant="ghost"
                  color="gray.500"
                  _hover={{ color: 'white' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    copyToClipboard(state.styleFields.exclude, 'Exclude');
                  }}
                />
              </HStack>
              <Collapse in={excludeExpanded} animateOpacity>
                <Box bg="gray.800" borderRadius="md" p={2} mt={1} fontSize="sm" color="gray.300">
                  {state.styleFields.exclude}
                </Box>
              </Collapse>
            </Box>
          )}

          <Divider borderColor="gray.700" />

          {/* === SONG TABS === */}
          <Box>
            {loadingThreads ? (
              <HStack spacing={2} py={2}>
                <Spinner size="sm" color="gray.500" />
                <Text fontSize="sm" color="gray.500">Loading songs...</Text>
              </HStack>
            ) : threads.length === 0 ? (
              <VStack align="stretch" spacing={3} py={3}>
                <Text fontSize="sm" color="gray.500">No lyrics yet for this style.</Text>
                <Button
                  size="sm"
                  bg="gray.800"
                  color="gray.200"
                  _hover={{ bg: 'gray.700' }}
                  alignSelf="flex-start"
                  leftIcon={<AddIcon />}
                  onClick={() => {
                    if (state.stylePromptId && onRequestNewLyricsVariation) {
                      onRequestNewLyricsVariation(state.stylePromptId);
                    }
                  }}
                >
                  New lyrics
                </Button>
              </VStack>
            ) : (
              <HStack 
                spacing={0}
                overflowX="auto" 
                overflowY="hidden"
                borderBottom="1px solid"
                borderColor="gray.700"
                css={{
                  '&::-webkit-scrollbar': { height: '4px' },
                  '&::-webkit-scrollbar-thumb': { background: '#4A5568', borderRadius: '2px' },
                }}
              >
                {threads.map((thread, idx) => {
                  const isSelected = thread.id === state.lyricsThreadId;
                  return (
                    <HStack
                      key={thread.id}
                      px={3}
                      py={2}
                      spacing={1}
                      cursor="pointer"
                      fontSize="sm"
                      whiteSpace="nowrap"
                      color={isSelected ? 'white' : 'gray.500'}
                      bg={isSelected ? 'gray.800' : 'transparent'}
                      borderTopRadius="md"
                      borderBottom="2px solid"
                      borderColor={isSelected ? 'purple.500' : 'transparent'}
                      mb="-1px"
                      _hover={{ 
                        color: isSelected ? 'white' : 'gray.300',
                        bg: isSelected ? 'gray.800' : 'whiteAlpha.50',
                      }}
                      transition="all 0.15s"
                      onClick={() => handleTabChange(idx)}
                    >
                      <Text>{thread.title || `Song ${idx + 1}`}</Text>
                    </HStack>
                  );
                })}
                {/* "+ New" button */}
                <Tooltip label="New lyrics variation" placement="top" hasArrow>
                  <Box
                    px={2}
                    py={2}
                    cursor="pointer"
                    color="gray.600"
                    _hover={{ color: 'gray.400' }}
                    transition="all 0.15s"
                    onClick={() => handleTabChange(threads.length)}
                  >
                    <AddIcon boxSize={3} />
                  </Box>
                </Tooltip>
              </HStack>
            )}
          </Box>

          {/* === SONG CONTENT === */}
          {state.lyricsThreadId && (
            <Box px={3} pt={3}>
              {/* Song Title Row */}
              <HStack justify="space-between" align="center" mb={3}>
                <HStack spacing={2} flex={1}>
                  {isRenaming ? (
                    <Input
                      ref={renameInputRef}
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      size="md"
                      fontWeight="medium"
                      fontSize="md"
                      variant="flushed"
                      borderColor="purple.400"
                      _focus={{ borderColor: 'purple.400', boxShadow: 'none' }}
                      maxW="300px"
                      spellCheck={false}
                      onBlur={handleSaveRename}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleSaveRename();
                        }
                        if (e.key === 'Escape') {
                          setIsRenaming(false);
                        }
                      }}
                    />
                  ) : (
                    <Tooltip label="Double-click to rename" placement="top" hasArrow>
                      <Text
                        fontWeight="medium"
                        fontSize="md"
                        cursor="text"
                        onDoubleClick={handleStartRename}
                        _hover={{ color: 'gray.300' }}
                        transition="color 0.1s"
                      >
                        {state.lyricsFields.lyrics_title || 'Untitled Song'}
                      </Text>
                    </Tooltip>
                  )}
                  {/* Copy title button - next to title */}
                  <IconButton
                    aria-label="Copy title"
                    icon={<CopyIcon />}
                    size="xs"
                    variant="ghost"
                    color="gray.500"
                    _hover={{ color: 'white' }}
                    onClick={() => copyToClipboard(
                      state.lyricsFields.lyrics_title || 'Untitled Song',
                      'Title'
                    )}
                  />
                  {savingLyrics && (
                    <>
                      <Spinner size="xs" color="gray.500" />
                      <Text fontSize="xs" color="gray.500">Saving...</Text>
                    </>
                  )}
                  {state.dirty.lyrics && !savingLyrics && (
                    <Badge colorScheme="yellow" fontSize="2xs">unsaved</Badge>
                  )}
                </HStack>
                <HStack spacing={2}>
                  {/* Edit Lyrics button with text */}
                  <Tooltip label="Edit lyrics with AI (updates in-place)" placement="top" hasArrow>
                    <HStack
                      spacing={1}
                      cursor="pointer"
                      onClick={() => {
                        setLyricsEditOpen(!lyricsEditOpen);
                        if (!lyricsEditOpen) {
                          setTimeout(() => lyricsEditInputRef.current?.focus(), 100);
                        }
                      }}
                      px={1.5}
                      py={0.5}
                      borderRadius="md"
                      bg={lyricsEditOpen ? 'blue.800' : 'transparent'}
                      _hover={{ bg: lyricsEditOpen ? 'blue.700' : 'whiteAlpha.100' }}
                      transition="all 0.15s"
                    >
                      <EditIcon boxSize={3.5} color={lyricsEditOpen ? 'blue.200' : 'gray.500'} />
                      <Text fontSize="xs" color={lyricsEditOpen ? 'blue.200' : 'gray.500'}>
                        Edit
                      </Text>
                    </HStack>
                  </Tooltip>
                  {/* Delete song button */}
                  <Tooltip label="Delete this song" placement="top" hasArrow>
                    <IconButton
                      aria-label="Delete song"
                      icon={<DeleteIcon />}
                      size="xs"
                      variant="ghost"
                      color="gray.600"
                      _hover={{ color: 'red.400', bg: 'whiteAlpha.100' }}
                      onClick={() => {
                        if (state.lyricsThreadId) {
                          openDeleteDialog(
                            state.lyricsThreadId,
                            state.lyricsFields.lyrics_title || 'this song'
                          );
                        }
                      }}
                    />
                  </Tooltip>
                </HStack>
              </HStack>

              {/* Lyrics Edit Input */}
              <Collapse in={lyricsEditOpen} animateOpacity>
                <Box bg="blue.900" borderRadius="md" p={3} mb={3} border="1px solid" borderColor="blue.700">
                  <VStack spacing={2} align="stretch">
                    <Input
                      ref={lyricsEditInputRef}
                      value={lyricsEditText}
                      onChange={(e) => setLyricsEditText(e.target.value)}
                      placeholder='e.g. "make the chorus more emotional", "add a bridge", "less repetition"'
                      bg="gray.900"
                      borderColor="blue.600"
                      _hover={{ borderColor: 'blue.500' }}
                      _focus={{ borderColor: 'blue.400', boxShadow: 'none' }}
                      fontSize="sm"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && lyricsEditText.trim()) {
                          e.preventDefault();
                          handleLyricsEditSubmit();
                        }
                        if (e.key === 'Escape') {
                          setLyricsEditOpen(false);
                          setLyricsEditText('');
                        }
                      }}
                    />
                    <HStack justify="space-between">
                      <Text fontSize="xs" color="blue.300">
                        Updates lyrics in-place
                      </Text>
                      <HStack spacing={2}>
                        <Button
                          size="xs"
                          variant="ghost"
                          color="gray.400"
                          _hover={{ color: 'white' }}
                          onClick={() => {
                            setLyricsEditOpen(false);
                            setLyricsEditText('');
                          }}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="xs"
                          bg="blue.600"
                          color="white"
                          _hover={{ bg: 'blue.500' }}
                          onClick={handleLyricsEditSubmit}
                          isLoading={isEditingLyrics}
                          loadingText="Editing..."
                          isDisabled={!lyricsEditText.trim()}
                        >
                          Edit
                        </Button>
                      </HStack>
                    </HStack>
                  </VStack>
                </Box>
              </Collapse>

              {/* Lyrics Textarea with copy button */}
              <Box position="relative">
                <Textarea
                  value={state.lyricsFields.lyrics_text}
                  onChange={(e) => handleLyricsChange(e.target.value)}
                  bg="gray.800"
                  fontFamily="monospace"
                  fontSize="sm"
                  minH="calc(60vh - 100px)"
                  resize="vertical"
                  placeholder="(No lyrics - instrumental or not generated yet)"
                  pr={10}
                />
                {/* Copy lyrics button - top right of textarea */}
                <Tooltip label="Copy lyrics" placement="left" hasArrow>
                  <IconButton
                    aria-label="Copy lyrics"
                    icon={<CopyIcon />}
                    size="xs"
                    variant="ghost"
                    color="gray.500"
                    _hover={{ color: 'white', bg: 'gray.700' }}
                    position="absolute"
                    top={2}
                    right={2}
                    onClick={() => copyToClipboard(state.lyricsFields.lyrics_text, 'Lyrics')}
                  />
                </Tooltip>
              </Box>
            </Box>
          )}

          {/* Delete song confirmation dialog */}
          <AlertDialog
            isOpen={deleteDialogOpen}
            leastDestructiveRef={cancelDeleteRef}
            onClose={() => {
              if (deletingThread) return;
              setDeleteDialogOpen(false);
              setThreadToDelete(null);
            }}
            isCentered
          >
            <AlertDialogOverlay
              bg="rgba(0,0,0,0.55)"
              backdropFilter="blur(6px)"
              display="flex"
              alignItems="center"
              justifyContent="center"
            >
              <AlertDialogContent bg="gray.800" borderColor="gray.600" margin="0">
                <AlertDialogHeader fontSize="lg" fontWeight="bold" color="white">
                  Delete song?
                </AlertDialogHeader>
                <AlertDialogBody color="gray.300">
                  This will permanently delete{' '}
                  <Text as="span" fontWeight="semibold" color="white">
                    {threadToDelete?.title || 'this song'}
                  </Text>
                  . This can’t be undone.
                </AlertDialogBody>
                <AlertDialogFooter>
                  <Button ref={cancelDeleteRef} onClick={() => setDeleteDialogOpen(false)} variant="ghost" color="gray.300">
                    Cancel
                  </Button>
                  <Button
                    ml={3}
                    colorScheme="red"
                    onClick={handleConfirmDeleteSong}
                    isLoading={deletingThread}
                    loadingText="Deleting..."
                  >
                    Delete
                  </Button>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialogOverlay>
          </AlertDialog>
        </VStack>
      </Box>
    </Box>
  );
}
