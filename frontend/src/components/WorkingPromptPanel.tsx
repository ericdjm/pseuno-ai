/**
 * WorkingPromptPanel - Right panel showing the current StylePrompt + Song.
 * 
 * Features:
 * - Inline refine input
 * - Style prompt editor (read-only or editable)
 * - Lyrics editor with checkpoints
 * - Copy buttons
 * - Favorite toggle
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
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
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
  StarIcon,
  TimeIcon,
  RepeatIcon,
} from '@chakra-ui/icons';
import type { WorkingState, WorkingAction } from '../types/workingState';
import type { LyricsCheckpoint, UnifiedRefineRequest, UnifiedRefineResponse } from '../api';
import {
  updateLyricsThread,
  createCheckpoint,
  listCheckpoints,
  restoreCheckpoint,
  refineAll,
  getSavedPrompt,
  updateSavedPrompt,
} from '../api';

interface WorkingPromptPanelProps {
  state: WorkingState;
  dispatch: React.Dispatch<WorkingAction>;
  onPromptSaved: () => void;
  onFavoriteToggled: () => void;
}

export default function WorkingPromptPanel({
  state,
  dispatch,
  onPromptSaved,
  onFavoriteToggled,
}: WorkingPromptPanelProps) {
  const toast = useToast();

  // Refine input state
  const [refineRequest, setRefineRequest] = useState('');
  const refineInputRef = useRef<HTMLTextAreaElement>(null);

  // Lyrics save debounce
  const [savingLyrics, setSavingLyrics] = useState(false);
  const lyricsSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Checkpoints loading
  const [loadingCheckpoints, setLoadingCheckpoints] = useState(false);

  // Favorite toggling
  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);

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

  // Sync favorite state from backend whenever the loaded prompt changes.
  // Otherwise the star can get "stuck" showing the previous prompt's favorite status.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (!state.stylePromptId) {
        setIsFavorite(false);
        return;
      }

      try {
        const prompt = await getSavedPrompt(state.stylePromptId);
        if (!cancelled) setIsFavorite(prompt.is_favorite);
      } catch (err) {
        // Non-fatal; keep current UI state if fetch fails (e.g., not authenticated).
        console.error('Failed to load favorite state:', err);
      }
    })();

    return () => {
      cancelled = true;
    };
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

  // Apply refine
  const handleRefine = async () => {
    if (!refineRequest.trim() || state.isRefining) return;

    const request = refineRequest;
    setRefineRequest('');
    dispatch({ type: 'REFINE_START' });

    // Create auto-checkpoint before refine
    if (state.lyricsThreadId) {
      try {
        await createCheckpoint(state.lyricsThreadId, { label: 'Before refine' });
      } catch (err) {
        console.warn('Failed to create pre-refine checkpoint:', err);
      }
    }

    toast({
      id: 'refine-progress',
      title: 'Refining...',
      status: 'loading',
      duration: null,
    });

    try {
      const payload: UnifiedRefineRequest = {
        suno_prompt: state.styleFields.suno_prompt,
        lyrics: state.lyricsFields.lyrics_text,
        exclude: state.styleFields.exclude,
        title: state.styleFields.title,
        weirdness: state.styleFields.weirdness,
        style_influence: state.styleFields.style_influence,
        auto_tags: state.styleFields.auto_tags,
        base_prompt_id: state.stylePromptId || undefined,
        base_thread_id: state.lyricsThreadId || undefined,
        change_request: request,
      };

      const response: UnifiedRefineResponse = await refineAll(payload);

      // Check if style was changed (new StylePrompt created)
      const styleChanged = response.changed_fields.includes('suno_prompt');
      const lyricsChanged = response.changed_fields.includes('lyrics');

      // Dispatch refine end with updated fields
      dispatch({
        type: 'REFINE_END',
        newPromptId: response.saved_prompt_id,
        newThreadId: response.saved_thread_id,
        updatedFields: {
          suno_prompt: response.suno_prompt,
          exclude: response.exclude,
          title: response.title,
          weirdness: response.weirdness,
          lyrics_text: response.lyrics,
        },
      });

      toast.close('refine-progress');

      // Show appropriate feedback based on what changed
      if (styleChanged) {
        // Style changed - show banner and specific toast
        setShowStyleForkedBanner(true);
        toast({
          title: 'New style version created',
          description: response.assistant_message || 'Your prompt style was updated. A new version has been saved.',
          status: 'info',
          duration: 5000,
        });
      } else if (lyricsChanged) {
        toast({
          title: 'Lyrics updated',
          description: response.assistant_message || 'Your lyrics have been updated.',
          status: 'success',
          duration: 3000,
        });
      } else {
        toast({
          title: 'Refinement complete',
          description: response.assistant_message || (response.changed_fields.length > 0 
            ? `Changed: ${response.changed_fields.join(', ')}`
            : 'No changes were needed.'),
          status: response.changed_fields.length > 0 ? 'success' : 'info',
          duration: 4000,
        });
      }

      // Refresh prompts if new one was created
      if (response.saved_prompt_id) {
        onPromptSaved();
      }

      // Reload checkpoints for new thread
      if (response.saved_thread_id) {
        loadCheckpoints();
      }
    } catch (err) {
      console.error('Refine failed:', err);
      toast.close('refine-progress');
      toast({
        title: 'Refine failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error',
        duration: 4000,
      });
      dispatch({
        type: 'REFINE_END',
        updatedFields: {},
      });
    }
  };

  // Toggle favorite
  const handleToggleFavorite = async () => {
    if (!state.stylePromptId) return;
    setTogglingFavorite(true);
    try {
      const updated = await updateSavedPrompt(state.stylePromptId, { is_favorite: !isFavorite });
      setIsFavorite(updated.is_favorite);
      onFavoriteToggled();
    } catch (err) {
      console.error('Failed to toggle favorite:', err);
    } finally {
      setTogglingFavorite(false);
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
    <Box flex={1} overflow="auto" bg="gray.900" py={4} pt={14} px={4} minW={0}>
      <Box maxW="800px" mx="auto">
      <VStack spacing={4} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1}>
            <HStack>
              <Text fontWeight="bold" fontSize="xl">
                {state.styleFields.title || 'Working Prompt'}
              </Text>
              {state.mode === 'loaded' && (
                <Badge colorScheme="blue">Loaded</Badge>
              )}
              {state.mode === 'generated' && (
                <Badge colorScheme="green">Generated</Badge>
              )}
              {state.mode === 'refining' && (
                <Badge colorScheme="purple">Refining...</Badge>
              )}
            </HStack>
            {state.stylePromptId && (
              <Text fontSize="xs" color="gray.500">
                StylePrompt ID: {state.stylePromptId}
                {state.lyricsThreadId && ` • Thread ID: ${state.lyricsThreadId}`}
              </Text>
            )}
          </VStack>
          <HStack>
            <IconButton
              aria-label={isFavorite ? 'Unfavorite' : 'Favorite'}
              icon={<StarIcon />}
              colorScheme="yellow"
              variant={isFavorite ? 'solid' : 'outline'}
              size="sm"
              isLoading={togglingFavorite}
              onClick={handleToggleFavorite}
              isDisabled={!state.stylePromptId}
            />
          </HStack>
        </HStack>

        {/* Tags */}
        {state.styleFields.auto_tags.length > 0 && (
          <HStack flexWrap="wrap" spacing={1}>
            {state.styleFields.auto_tags.map((tag, idx) => (
              <Badge key={idx} colorScheme="teal" fontSize="xs">
                {tag}
              </Badge>
            ))}
          </HStack>
        )}

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

        {/* Inline Refine */}
        <Box bg="purple.900" borderRadius="md" p={3} border="1px solid" borderColor="purple.700">
          <Text fontSize="sm" color="purple.200" mb={2}>
            Refine: Describe what you want to change
          </Text>
          <HStack>
            <Textarea
              ref={refineInputRef}
              value={refineRequest}
              onChange={(e) => setRefineRequest(e.target.value)}
              placeholder='e.g. "make it more aggressive", "change the chorus to be about rain"'
              bg="gray.800"
              borderColor="purple.600"
              rows={2}
              resize="none"
              flex={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && refineRequest.trim()) {
                  e.preventDefault();
                  handleRefine();
                }
              }}
              isDisabled={state.isRefining}
            />
            <Button
              colorScheme="purple"
              onClick={handleRefine}
              isLoading={state.isRefining}
              isDisabled={!refineRequest.trim()}
            >
              Apply
            </Button>
          </HStack>
        </Box>

        <Divider borderColor="gray.700" />

        {/* Suno Prompt */}
        <Box>
          <HStack justify="space-between" mb={2}>
            <Text fontWeight="bold">Suno Prompt</Text>
            <HStack>
              <Text fontSize="xs" color="gray.500">
                {state.styleFields.suno_prompt.length} chars
              </Text>
              <IconButton
                aria-label="Copy prompt"
                icon={<CopyIcon />}
                size="xs"
                onClick={() => copyToClipboard(state.styleFields.suno_prompt, 'Prompt')}
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

        {/* Weirdness & Style Influence */}
        <HStack spacing={8}>
          <Box flex={1}>
            <Text fontSize="sm" mb={1}>
              Weirdness: {state.styleFields.weirdness}%
            </Text>
            <Slider
              value={state.styleFields.weirdness}
              min={0}
              max={100}
              isReadOnly
            >
              <SliderTrack bg="gray.700">
                <SliderFilledTrack bg="orange.400" />
              </SliderTrack>
              <SliderThumb />
            </Slider>
          </Box>
          <Box flex={1}>
            <Text fontSize="sm" mb={1}>
              Style Influence: {state.styleFields.style_influence}%
            </Text>
            <Slider
              value={state.styleFields.style_influence}
              min={0}
              max={100}
              isReadOnly
            >
              <SliderTrack bg="gray.700">
                <SliderFilledTrack bg="blue.400" />
              </SliderTrack>
              <SliderThumb />
            </Slider>
          </Box>
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

