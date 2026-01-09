/**
 * WorkingPromptPanel - Right panel showing the current Song.
 * 
 * Features:
 * - Song title (copy-pastable)
 * - Style prompt display with copy
 * - Exclude display with copy
 * - Lyrics editor with auto-save and checkpoints
 */

import { useState, useRef, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Textarea,
  IconButton,
  Badge,
  Divider,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  AlertDescription,
  CloseButton,
} from '@chakra-ui/react';
import {
  CopyIcon,
  TimeIcon,
  RepeatIcon,
} from '@chakra-ui/icons';
import type { WorkingState, WorkingAction } from '../types/workingState';
import type { LyricsCheckpoint } from '../api';
import {
  updateLyricsThread,
  createCheckpoint,
  listCheckpoints,
  restoreCheckpoint,
} from '../api';

interface WorkingPromptPanelProps {
  state: WorkingState;
  dispatch: React.Dispatch<WorkingAction>;
}

export default function WorkingPromptPanel({
  state,
  dispatch,
}: WorkingPromptPanelProps) {
  const toast = useToast();

  // Lyrics save debounce
  const [savingLyrics, setSavingLyrics] = useState(false);
  const lyricsSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Checkpoints loading
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(false);

  // Banner for when a new style version was created
  const [showStyleForkedBanner, setShowStyleForkedBanner] = useState(false);

  // Load checkpoints when thread changes
  useEffect(() => {
    if (state.lyricsThreadId) {
      loadCheckpoints();
    }
  }, [state.lyricsThreadId]);

  // Reset style forked banner when navigating to a different prompt
  useEffect(() => {
    setShowStyleForkedBanner(false);
  }, [state.stylePromptId]);

  const loadCheckpoints = async () => {
    if (!state.lyricsThreadId) return;
    setLoadingCheckpoints(true);
    try {
      const response = await listCheckpoints(state.lyricsThreadId);
      dispatch({ type: 'SET_CHECKPOINTS', checkpoints: response.checkpoints });
    } catch (err) {
      console.error('Failed to load checkpoints:', err);
    } finally {
      setLoadingCheckpoints(false);
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

  // Create checkpoint
  const handleCreateCheckpoint = async (label?: string) => {
    if (!state.lyricsThreadId) return;
    try {
      const checkpoint = await createCheckpoint(state.lyricsThreadId, { label });
      dispatch({ type: 'ADD_CHECKPOINT', checkpoint });
      toast({
        title: 'Checkpoint created',
        status: 'success',
        duration: 2000,
      });
    } catch (err) {
      console.error('Failed to create checkpoint:', err);
      toast({
        title: 'Failed to create checkpoint',
        status: 'error',
        duration: 2000,
      });
    }
  };

  // Restore checkpoint
  const handleRestoreCheckpoint = async (checkpoint: LyricsCheckpoint) => {
    if (!state.lyricsThreadId) return;
    try {
      const updated = await restoreCheckpoint(state.lyricsThreadId, checkpoint.id);
      dispatch({ type: 'RESTORE_CHECKPOINT', lyrics_text: updated.lyrics_text });
      // Reload checkpoints (a "Before restore" was created)
      loadCheckpoints();
      toast({
        title: 'Checkpoint restored',
        status: 'success',
        duration: 2000,
      });
    } catch (err) {
      console.error('Failed to restore checkpoint:', err);
      toast({
        title: 'Failed to restore',
        status: 'error',
        duration: 2000,
      });
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
    <Box flex={1} overflow="auto" bg="gray.900" py={6} pt={14} px={4} minW={0}>
      <Box maxW={{ base: '600px', lg: '560px' }} w="100%" mx="auto">
      <VStack spacing={4} align="stretch">
        {/* Header - Song title (copy-pastable) */}
        <HStack justify="space-between" align="center">
          <Text fontWeight="semibold" fontSize="xl">
            {state.lyricsFields.lyrics_title || state.styleFields.title || 'Untitled Song'}
          </Text>
          <IconButton
            aria-label="Copy title"
            icon={<CopyIcon />}
            size="xs"
            variant="ghost"
            onClick={() => copyToClipboard(
              state.lyricsFields.lyrics_title || state.styleFields.title || 'Untitled Song',
              'Title'
            )}
          />
        </HStack>

        {/* Style Forked Banner */}
        {showStyleForkedBanner && (
          <Alert status="info" variant="subtle" borderRadius="md">
            <AlertIcon />
            <AlertDescription flex={1} fontSize="sm">
              A new style version was created from your refinement. The sidebar has been updated.
            </AlertDescription>
            <CloseButton
              position="relative"
              right={-1}
              top={0}
              onClick={() => setShowStyleForkedBanner(false)}
            />
          </Alert>
        )}

        <Divider borderColor="gray.700" />

        {/* Style (formerly "Suno Prompt") */}
        <Box>
          <HStack justify="space-between" mb={2}>
            <Text fontWeight="bold">Style</Text>
            <HStack>
              <Text fontSize="xs" color="gray.500">
                {state.styleFields.suno_prompt.length} chars
              </Text>
              <IconButton
                aria-label="Copy style"
                icon={<CopyIcon />}
                size="xs"
                onClick={() => copyToClipboard(state.styleFields.suno_prompt, 'Style')}
              />
            </HStack>
          </HStack>
          <Box
            bg="gray.800"
            borderRadius="md"
            p={3}
            fontFamily="monospace"
            fontSize="sm"
            whiteSpace="pre-wrap"
            maxH="200px"
            overflowY="auto"
          >
            {state.styleFields.suno_prompt || '(empty)'}
          </Box>
        </Box>

        {/* Exclude */}
        {state.styleFields.exclude && (
          <Box>
            <HStack justify="space-between" mb={2}>
              <Text fontWeight="bold">Exclude</Text>
              <IconButton
                aria-label="Copy exclude"
                icon={<CopyIcon />}
                size="xs"
                onClick={() => copyToClipboard(state.styleFields.exclude, 'Exclude')}
              />
            </HStack>
            <Box bg="red.900" borderRadius="md" p={2} fontSize="sm">
              {state.styleFields.exclude}
            </Box>
          </Box>
        )}

        {/* Weirdness & Style Influence - simple percentages */}
        <HStack spacing={6}>
          <Text fontSize="sm" color="gray.400">
            Weirdness: {state.styleFields.weirdness}%
          </Text>
          <Text fontSize="sm" color="gray.400">
            Style Influence: {state.styleFields.style_influence}%
          </Text>
        </HStack>

        <Divider borderColor="gray.700" />

        {/* Lyrics */}
        <Box>
          <HStack justify="space-between" mb={2}>
            <HStack>
              <Text fontWeight="bold">Lyrics</Text>
              {savingLyrics && <Spinner size="xs" color="gray.500" />}
              {state.dirty.lyrics && !savingLyrics && (
                <Badge colorScheme="yellow" fontSize="2xs">unsaved</Badge>
              )}
            </HStack>
            <HStack>
              <Text fontSize="xs" color="gray.500">
                {state.lyricsFields.lyrics_text.length} chars
              </Text>
              <IconButton
                aria-label="Copy lyrics"
                icon={<CopyIcon />}
                size="xs"
                onClick={() => copyToClipboard(state.lyricsFields.lyrics_text, 'Lyrics')}
              />
            </HStack>
          </HStack>
          <Textarea
            value={state.lyricsFields.lyrics_text}
            onChange={(e) => handleLyricsChange(e.target.value)}
            bg="gray.800"
            fontFamily="monospace"
            fontSize="sm"
            rows={12}
            resize="vertical"
            placeholder="(No lyrics - instrumental or not generated yet)"
            isDisabled={!state.lyricsThreadId}
          />
        </Box>

        {/* Checkpoints */}
        {state.lyricsThreadId && (
          <Box>
            <HStack justify="space-between" mb={2}>
              <HStack>
                <TimeIcon color="gray.500" />
                <Text fontWeight="bold" fontSize="sm">
                  Checkpoints
                </Text>
                {loadingCheckpoints && <Spinner size="xs" />}
              </HStack>
              <Button
                size="xs"
                colorScheme="blue"
                variant="outline"
                onClick={() => handleCreateCheckpoint()}
              >
                + Checkpoint
              </Button>
            </HStack>
            {state.checkpoints.length === 0 ? (
              <Text fontSize="xs" color="gray.500">
                No checkpoints yet. Checkpoints are created automatically before refine.
              </Text>
            ) : (
              <VStack align="stretch" spacing={1} maxH="150px" overflowY="auto">
                {state.checkpoints.map((cp) => (
                  <HStack
                    key={cp.id}
                    p={2}
                    bg="gray.800"
                    borderRadius="sm"
                    fontSize="xs"
                    justify="space-between"
                  >
                    <VStack align="start" spacing={0}>
                      <Text>{cp.label || 'Checkpoint'}</Text>
                      <Text color="gray.500">
                        {new Date(cp.created_at).toLocaleString()}
                      </Text>
                    </VStack>
                    <Button
                      size="xs"
                      variant="ghost"
                      colorScheme="blue"
                      leftIcon={<RepeatIcon />}
                      onClick={() => handleRestoreCheckpoint(cp)}
                    >
                      Restore
                    </Button>
                  </HStack>
                ))}
              </VStack>
            )}
          </Box>
        )}
      </VStack>
      </Box>
    </Box>
  );
}

