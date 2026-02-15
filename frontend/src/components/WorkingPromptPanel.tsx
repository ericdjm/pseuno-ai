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
import { CopyIcon, ChevronRightIcon, ChevronDownIcon, ExternalLinkIcon, AddIcon, DeleteIcon } from '@chakra-ui/icons';
import { LuSparkles } from 'react-icons/lu';
import type { WorkingState, WorkingAction } from '../types/workingState';
import { LuDices } from 'react-icons/lu';
import { 
  updateLyricsThread, 
  refineAll, 
  UnifiedRefineResponse, 
  getPromptThreads, 
  LyricsThreadSummary,
  getLyricsThread,
  deleteLyricsThread,
  updateSavedPrompt,
  generateLyricsOnly,
  generateLyricsTopic,
  createLyricsThread,
  reorderThreads,
  classifyStyle,
  updatePromptClassifier,
  sha256,
} from '../api';
import {
  trackStyleRefineStarted,
  trackStyleRefineSucceeded,
  trackStyleRefineFailed,
  trackLyricsAiEditStarted,
  trackLyricsAiEditSucceeded,
  trackLyricsAiEditFailed,
  trackCopiedToClipboard,
  trackSunoLinkClicked,
  trackDraftLyricsGenerated,
  trackNewLyricsInStyleStarted,
  trackNewLyricsInStyleSucceeded,
  trackNewLyricsInStyleFailed,
  trackRandomizeLyricsClicked,
  trackRandomizeLyricsSucceeded,
  trackRandomizeLyricsFailed,
  trackNewLyricsVariationClicked,
  trackSongTitleChanged,
  trackStyleTitleChanged,
  trackLyricsManualEditSaved,
  trackSongDeleted,
  trackSongsReordered,
  trackCopiedToClipboardFailed,
  trackLyricsManualEditSaveFailed,
  trackSongDeleteFailed,
  trackSongsReorderFailed,
  trackSongTitleChangeFailed,
  trackStyleTitleChangeFailed,
  trackOutputUsed,
  changedFieldsToProps,
  createFlowId,
} from '../analytics';
import type { CopyContentType, CopyContext, OutputUsedMethod } from '../analytics';
import type { OriginAction } from '../analytics';

interface WorkingPromptPanelProps {
  state: WorkingState;
  dispatch: React.Dispatch<WorkingAction>;
  onRefineApplied?: (response: UnifiedRefineResponse) => Promise<void>;
  onThreadUpdated?: () => void;
  refreshKey?: number;
  isAuthenticated?: boolean;
}

export default function WorkingPromptPanel({
  state,
  dispatch,
  onRefineApplied,
  onThreadUpdated,
  refreshKey,
  isAuthenticated = false,
}: WorkingPromptPanelProps) {
  const toast = useToast();
  const authState = isAuthenticated ? 'spotify' : 'guest';

  // Track the most recent “origin action” for this view so output_used can be attributed.
  const lastOriginRef = useRef<{ flow_id: string; origin_action: OriginAction; at_ms: number } | null>(null);

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

  // Style Refine composer state (always creates new StylePrompt with all songs copied)
  const [styleRefineOpen, setStyleRefineOpen] = useState(false);
  const [styleRefineText, setStyleRefineText] = useState('');
  const [isRefiningStyle, setIsRefiningStyle] = useState(false);
  const [showRefineWaitMessage, setShowRefineWaitMessage] = useState(false);
  const styleRefineInputRef = useRef<HTMLInputElement>(null);

  // Lyrics Edit composer state (updates in-place)
  const [lyricsEditOpen, setLyricsEditOpen] = useState(false);
  const [lyricsEditText, setLyricsEditText] = useState('');
  const [isEditingLyrics, setIsEditingLyrics] = useState(false);
  const [showEditWaitMessage, setShowEditWaitMessage] = useState(false);
  const lyricsEditInputRef = useRef<HTMLInputElement>(null);

  // Lyrics save debounce
  const [savingLyrics, setSavingLyrics] = useState(false);
  const lyricsSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedLyricsLenRef = useRef<number>(0);
  const baselineLyricsThreadIdRef = useRef<number | null>(null);
  const baselineInitializedRef = useRef(false);

  // Song renaming state
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  // Style renaming state
  const [isRenamingStyle, setIsRenamingStyle] = useState(false);
  const [styleRenameValue, setStyleRenameValue] = useState('');
  const styleRenameInputRef = useRef<HTMLInputElement>(null);

  // Establish a baseline for "manual edit size" per selected thread.
  useEffect(() => {
    if (state.lyricsThreadId !== baselineLyricsThreadIdRef.current) {
      baselineLyricsThreadIdRef.current = state.lyricsThreadId;
      baselineInitializedRef.current = false;
    }
    if (!baselineInitializedRef.current) {
      lastSavedLyricsLenRef.current = (state.lyricsFields.lyrics_text || '').length;
      // Mark initialized immediately; empty lyrics is a valid baseline (instrumental / not generated yet).
      baselineInitializedRef.current = true;
    }
  }, [state.lyricsThreadId, state.lyricsFields.lyrics_text]);

  // Draft tab state (inline new song composer)
  const [draftOpen, setDraftOpen] = useState(false);
  const [draftLyricsAbout, setDraftLyricsAbout] = useState('');
  const [isCreatingSong, setIsCreatingSong] = useState(false);
  const [isGeneratingTopic, setIsGeneratingTopic] = useState(false);
  const [showLongWaitMessage, setShowLongWaitMessage] = useState(false);

  // Drag-and-drop state for reordering tabs
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  // Show "can take up to a minute" message after 10 seconds of loading
  useEffect(() => {
    if (!isCreatingSong) {
      setShowLongWaitMessage(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowLongWaitMessage(true);
    }, 10000);
    return () => clearTimeout(timer);
  }, [isCreatingSong]);

  // Keyboard shortcut: Cmd/Ctrl + Enter to create (only when draft is open)
  useEffect(() => {
    if (!draftOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      const isMetaOrCtrl = e.metaKey || e.ctrlKey;
      if (!isMetaOrCtrl) return;
      if (e.altKey || e.shiftKey) return;
      if (e.key !== 'Enter') return;
      if (isCreatingSong) return;

      e.preventDefault();
      handleCreateSong();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [draftOpen, isCreatingSong, state.stylePromptId, state.styleFields.suno_prompt, draftLyricsAbout]);

  // Track previous state to detect explicit "New song" clicks (same style, thread cleared)
  const prevStateRef = useRef({ stylePromptId: state.stylePromptId, lyricsThreadId: state.lyricsThreadId });

  // Fetch all threads when stylePromptId or refreshKey changes
  useEffect(() => {
    if (!state.stylePromptId) {
      setThreads([]);
      setDraftOpen(false);
      return;
    }

    const fetchThreads = async () => {
      setLoadingThreads(true);
      try {
        const fetchedThreads = await getPromptThreads(state.stylePromptId!);
        setThreads(fetchedThreads);
        // Auto-open draft only when style has NO threads and no thread is selected
        if (fetchedThreads.length === 0 && !state.lyricsThreadId) {
          setDraftOpen(true);
        }
      } catch (err) {
        console.error('Failed to fetch threads:', err);
        setThreads([]);
      } finally {
        setLoadingThreads(false);
      }
    };

    fetchThreads();
    // Note: state.lyricsThreadId intentionally excluded to prevent refetch when switching tabs
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.stylePromptId, refreshKey]);

  // Close draft when a thread is selected (e.g., after refine or clicking a tab)
  useEffect(() => {
    if (state.lyricsThreadId) {
      setDraftOpen(false);
    }
  }, [state.lyricsThreadId]);

  // Open draft when user clicks "New song" (same style, thread explicitly cleared)
  useEffect(() => {
    const prev = prevStateRef.current;
    // If same style but thread was cleared → user clicked "New song"
    if (
      state.stylePromptId === prev.stylePromptId &&
      prev.lyricsThreadId !== null &&
      state.lyricsThreadId === null
    ) {
      setDraftOpen(true);
    }
    prevStateRef.current = { stylePromptId: state.stylePromptId, lyricsThreadId: state.lyricsThreadId };
  }, [state.stylePromptId, state.lyricsThreadId]);

  // Track if we should preserve edit state on next navigation (set when refine starts)
  const preserveEditOnNavigationRef = useRef(false);

  // Reset refine/edit/draft state when navigating to a different prompt
  // But preserve edit state if we just completed a refine (user may want to continue editing)
  useEffect(() => {
    setStyleRefineOpen(false);
    setStyleRefineText('');
    setDraftLyricsAbout('');
    
    // Only clear edit state if this wasn't from a refine navigation
    // This lets the user keep their edit text when refine creates a new style
    if (!preserveEditOnNavigationRef.current) {
      setLyricsEditOpen(false);
      setLyricsEditText('');
    }
    // Clear the flag after using it
    preserveEditOnNavigationRef.current = false;
    
    // Close draft when a thread is selected (e.g., after refine creates new style + thread)
    if (state.lyricsThreadId) {
      setDraftOpen(false);
    }
  }, [state.stylePromptId, state.lyricsThreadId]);

  // Show "can take up to a minute" message after 5 seconds of refining
  useEffect(() => {
    if (!isRefiningStyle) {
      setShowRefineWaitMessage(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowRefineWaitMessage(true);
    }, 5000);
    return () => clearTimeout(timer);
  }, [isRefiningStyle]);

  // Show "can take up to a minute" message after 5 seconds of editing
  useEffect(() => {
    if (!isEditingLyrics) {
      setShowEditWaitMessage(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowEditWaitMessage(true);
    }, 5000);
    return () => clearTimeout(timer);
  }, [isEditingLyrics]);

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
    // If clicking "+" button, open the draft tab
    if (index === threads.length) {
      setDraftOpen(true);
      trackNewLyricsVariationClicked({ auth_state: authState });
      return;
    }

    // Clicking any existing tab closes the draft
    const wasDraftOpen = draftOpen;
    setDraftOpen(false);
    setDraftLyricsAbout('');

    const selectedThread = threads[index];
    if (!selectedThread) return;
    
    // Skip if already selected (unless we were in draft mode - need to re-display the thread)
    if (selectedThread.id === state.lyricsThreadId && !wasDraftOpen) return;

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

  // Drag-and-drop handlers for reordering tabs
  const handleDragStart = (e: React.DragEvent, idx: number) => {
    setDraggedIdx(idx);
    setDragOverIdx(null);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedIdx !== null && idx !== draggedIdx) {
      setDragOverIdx(idx);
    }
  };

  const handleDragLeave = () => {
    // Don't clear immediately - let dragOver on next tab set the new target
  };

  const handleDrop = async (e: React.DragEvent, targetIdx: number) => {
    e.preventDefault();
    if (draggedIdx !== null && draggedIdx !== targetIdx) {
      const newThreads = [...threads];
      const [draggedThread] = newThreads.splice(draggedIdx, 1);
      // When dragging forward, indices shift down after removal, so subtract 1
      const insertIdx = targetIdx > draggedIdx ? targetIdx - 1 : targetIdx;
      newThreads.splice(insertIdx, 0, draggedThread);
      setThreads(newThreads);

      // Persist to backend
      if (state.stylePromptId) {
        try {
          await reorderThreads(state.stylePromptId, newThreads.map(t => t.id));
          onThreadUpdated?.();
          const songs_count_bucket: '1-2' | '3-5' | '6+' =
            newThreads.length <= 2 ? '1-2' : newThreads.length <= 5 ? '3-5' : '6+';
          trackSongsReordered({
            auth_state: authState,
            songs_count_bucket,
            move_direction: insertIdx < draggedIdx ? 'up' : 'down',
          });
        } catch (err) {
          trackSongsReorderFailed({ auth_state: authState, error_type: err instanceof Error ? err.name : 'unknown' });
          console.error('Failed to reorder threads:', err);
        }
      }
    }
    setDraggedIdx(null);
    setDragOverIdx(null);
  };

  const handleDragEnd = () => {
    setDraggedIdx(null);
    setDragOverIdx(null);
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

      const remaining_songs_bucket: '0' | '1-2' | '3-5' | '6+' =
        nextThreads.length === 0
          ? '0'
          : nextThreads.length <= 2
            ? '1-2'
            : nextThreads.length <= 5
              ? '3-5'
              : '6+';
      trackSongDeleted({
        auth_state: authState,
        source: 'song_view',
        remaining_songs_bucket,
      });

      // If we deleted the selected thread, pick a neighbor; if none, open the draft tab.
      if (wasSelected) {
        if (nextThreads.length === 0) {
          dispatch({ type: 'CLEAR_THREAD' });
          setDraftOpen(true);
        } else {
          const candidateIndex = Math.max(0, Math.min(deletedIndex - 1, nextThreads.length - 1));
          const candidate = nextThreads[candidateIndex];
          const fullThread = await getLyricsThread(candidate.id);
          dispatch({ type: 'SELECT_THREAD', thread: fullThread });
        }
      }

      // Notify parent to refresh sidebar
      onThreadUpdated?.();
    } catch (err) {
      trackSongDeleteFailed({
        auth_state: authState,
        source: 'song_view',
        error_type: err instanceof Error ? err.name : 'unknown',
      });
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
      trackSongTitleChanged({ auth_state: authState, source: 'manual' });
    } catch (err) {
      trackSongTitleChangeFailed({ auth_state: authState, error_type: err instanceof Error ? err.name : 'unknown' });
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
      trackStyleTitleChanged({ auth_state: authState, source: 'manual' });
    } catch (err) {
      trackStyleTitleChangeFailed({ auth_state: authState, error_type: err instanceof Error ? err.name : 'unknown' });
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
      const prevLen = lastSavedLyricsLenRef.current;
      const newLen = (lyrics_text || '').length;
      const updated = await updateLyricsThread(state.lyricsThreadId, { lyrics_text });
      dispatch({ type: 'SAVE_THREAD_SUCCESS', thread: updated });
      
      // Update threads list with new title
      setThreads(prev => prev.map(t => 
        t.id === updated.id ? { ...t, title: updated.title } : t
      ));

      // Track manual lyric edits (vs AI refine). Keep properties low-cardinality.
      const delta = newLen - prevLen;
      if (delta !== 0) {
        const abs = Math.abs(delta);
        const edit_size: 'small' | 'medium' | 'large' =
          abs <= 20 ? 'small' : abs <= 200 ? 'medium' : 'large';
        trackLyricsManualEditSaved({
          auth_state: authState,
          edit_size,
          was_empty_before: prevLen === 0,
        });
        lastSavedLyricsLenRef.current = newLen;
      }
    } catch (err) {
      trackLyricsManualEditSaveFailed({ auth_state: authState, error_type: err instanceof Error ? err.name : 'unknown' });
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

  // Handle "Surprise me" topic generation for draft composer
  // Implements Option B: use cached classifier weights if fresh, else keyword fallback + async re-classify
  const handleGenerateTopic = async () => {
    if (!state.styleFields.suno_prompt) return;
    
    setIsGeneratingTopic(true);
    const startTime = Date.now();
    trackRandomizeLyricsClicked({
      auth_state: authState,
      has_style_input: true,
      page: 'song_view',
      randomize_context: 'draft_composer',
    });

    try {
      // Check if cached classifier weights are fresh
      const currentPromptHash = await sha256(state.styleFields.suno_prompt);
      const cachedHash = state.styleFields.classifier_prompt_hash;
      const isFresh = cachedHash === currentPromptHash;

      let traitOverrides: Record<string, number> | undefined;
      let bankSimilarities: Record<string, number> | undefined;

      if (isFresh && state.styleFields.classifier_traits) {
        // Use cached weights
        traitOverrides = state.styleFields.classifier_traits;
        bankSimilarities = state.styleFields.classifier_bank_sims || undefined;
        console.log('[StyleView] Using cached classifier weights');
      } else {
        // Stale or missing - fire async re-classify (don't block this request)
        console.log('[StyleView] Classifier weights stale/missing, using keyword fallback');
        
        // Fire async re-classify in background
        if (state.stylePromptId) {
          const promptId = state.stylePromptId;
          const sunoPrompt = state.styleFields.suno_prompt;
          
          // Don't await - let this run in background
          (async () => {
            try {
              const classifyResult = await classifyStyle(sunoPrompt);
              if (classifyResult.success) {
                const newHash = await sha256(sunoPrompt);
                // Update local state
                dispatch({
                  type: 'UPDATE_CLASSIFIER_WEIGHTS',
                  traits: classifyResult.traits,
                  bankSims: classifyResult.bank_similarities,
                  promptHash: newHash,
                });
                // Persist to backend
                await updatePromptClassifier(promptId, {
                  classifier_traits: classifyResult.traits,
                  classifier_bank_sims: classifyResult.bank_similarities,
                  classifier_prompt_hash: newHash,
                });
                console.log('[StyleView] Classifier weights refreshed and saved');
              }
            } catch (err) {
              console.warn('[StyleView] Background re-classify failed:', err);
            }
          })();
        }
      }

      const result = await generateLyricsTopic({
        style_prompt: state.styleFields.suno_prompt,
        trait_overrides: traitOverrides,
        bank_similarities: bankSimilarities,
      });
      setDraftLyricsAbout(result.topic);
      trackRandomizeLyricsSucceeded({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        has_style_input: true,
        page: 'song_view',
        randomize_context: 'draft_composer',
        bank_id: result.bank_id,
      });
      // No toast - the topic appearing in the box is enough feedback
    } catch (error) {
      trackRandomizeLyricsFailed({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        error_type: error instanceof Error ? error.name : 'unknown',
        page: 'song_view',
        randomize_context: 'draft_composer',
      });
      toast({
        title: 'Failed to generate topic',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGeneratingTopic(false);
    }
  };

  // Handle creating a new song from the draft composer
  const handleCreateSong = async () => {
    if (!state.stylePromptId) {
      toast({
        title: 'No style loaded',
        status: 'error',
        duration: 2000,
      });
      return;
    }

    setIsCreatingSong(true);
    const startTime = Date.now();
    const hasLyricsAboutInput = draftLyricsAbout.trim().length > 0;
    const flowId = createFlowId();
    trackNewLyricsInStyleStarted({
      auth_state: authState,
      has_lyrics_about_input: hasLyricsAboutInput,
      flow_id: flowId,
    });
    try {
      // Generate lyrics + title (or just title for instrumental)
      const lyricsResult = await generateLyricsOnly({
        suno_prompt: state.styleFields.suno_prompt,
        lyrics_about: draftLyricsAbout.trim(),
      });

      const songTitle = lyricsResult.song_title || 'New Song';
      const lyricsText = lyricsResult.lyrics || '';

      // Create a new thread
      const newThread = await createLyricsThread({
        style_prompt_id: state.stylePromptId,
        title: songTitle,
      });

      // Update the thread with lyrics (if any)
      await updateLyricsThread(newThread.id, { 
        title: songTitle,
        lyrics_text: lyricsText,
      });

      // Fetch the full thread and select it
      const fullThread = await getLyricsThread(newThread.id);
      dispatch({ type: 'SELECT_THREAD', thread: fullThread });

      // Close draft and clear input
      setDraftOpen(false);
      setDraftLyricsAbout('');

      // Add to threads list
      setThreads(prev => [...prev, { 
        id: fullThread.id, 
        title: fullThread.title,
        source_action: fullThread.source_action,
        created_at: fullThread.created_at,
        updated_at: fullThread.updated_at,
      }]);

      // Notify parent to refresh sidebar
      onThreadUpdated?.();

      // Track "draft lyrics generated" only once the end-to-end flow has succeeded
      // (avoids recording partial success when persistence/fetch fails).
      trackDraftLyricsGenerated({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        has_lyrics_about_input: hasLyricsAboutInput,
        flow_id: flowId,
      });

      trackNewLyricsInStyleSucceeded({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        has_lyrics_about_input: hasLyricsAboutInput,
        flow_id: flowId,
      });
    } catch (error) {
      // Only emit the end-to-end failure here. The error may come from thread create/update/fetch,
      // so emitting draft_lyrics_failed as well would be misleading and double-count failures.
      trackNewLyricsInStyleFailed({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        error_type: error instanceof Error ? error.name : 'unknown',
        has_lyrics_about_input: hasLyricsAboutInput,
        flow_id: flowId,
      });
      console.error('Failed to create song:', error);
      toast({
        title: 'Failed to create song',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsCreatingSong(false);
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

    // If edit popup is open, preserve it when navigating to the new style
    if (lyricsEditOpen) {
      preserveEditOnNavigationRef.current = true;
    }

    const flowId = createFlowId();
    lastOriginRef.current = { flow_id: flowId, origin_action: 'style_refine', at_ms: Date.now() };
    trackStyleRefineStarted({ auth_state: authState });
    const startTime = Date.now();

    setIsRefiningStyle(true);

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

      if (!response.updates_persisted) {
        trackStyleRefineFailed({
          auth_state: authState,
          duration_ms: Date.now() - startTime,
          error_type: 'updates_not_persisted',
          flow_id: flowId,
        });
        toast({
          title: 'Style refinement failed',
          description: 'The server generated an update but could not save it. Please try again.',
          status: 'error',
          duration: 4000,
        });
        return;
      }

      trackStyleRefineSucceeded({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        created_new_style: !!response.saved_prompt_id,
        updates_persisted: response.updates_persisted,
        ...changedFieldsToProps(response.changed_fields),
        flow_id: flowId,
      });

      setStyleRefineOpen(false);
      setStyleRefineText('');

      // Always fork: navigate to new style with same song selected
      if (onRefineApplied) {
        await onRefineApplied(response);
      }
    } catch (err) {
      trackStyleRefineFailed({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        error_type: err instanceof Error ? err.name : 'unknown',
        flow_id: flowId,
      });

      console.error('Style refine failed:', err);
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

    const flowId = createFlowId();
    lastOriginRef.current = { flow_id: flowId, origin_action: 'lyrics_ai_edit', at_ms: Date.now() };
    trackLyricsAiEditStarted({ auth_state: authState });
    const startTime = Date.now();

    setIsEditingLyrics(true);

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

      if (!response.updates_persisted) {
        trackLyricsAiEditFailed({
          auth_state: authState,
          duration_ms: Date.now() - startTime,
          error_type: 'updates_not_persisted',
          flow_id: flowId,
        });
        toast({
          title: 'Lyrics edit failed',
          description: 'The server generated an update but could not save it. Please try again.',
          status: 'error',
          duration: 4000,
        });
        return;
      }

      trackLyricsAiEditSucceeded({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        updates_persisted: response.updates_persisted,
        ...changedFieldsToProps(response.changed_fields),
        flow_id: flowId,
      });

      setLyricsEditOpen(false);
      setLyricsEditText('');

      if (onRefineApplied) {
        await onRefineApplied(response);
      }
      
      // Refresh sidebar to show updated song title
      onThreadUpdated?.();
    } catch (err) {
      trackLyricsAiEditFailed({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        error_type: err instanceof Error ? err.name : 'unknown',
        flow_id: flowId,
      });

      console.error('Lyrics edit failed:', err);
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
  const copyToClipboard = async (
    text: string,
    contentType: CopyContentType,
    copyContext: CopyContext
  ) => {
    const excludeText = state.styleFields.exclude || '';
    const excludePresent = excludeText.trim().length > 0;
    const excludeCount = excludePresent ? excludeText.split(',').filter(Boolean).length : 0;
    const exclude_count_bucket: '0' | '1-2' | '3-5' | '6+' =
      excludeCount === 0 ? '0' : excludeCount <= 2 ? '1-2' : excludeCount <= 5 ? '3-5' : '6+';
    try {
      await navigator.clipboard.writeText(text);

      const origin_action: OriginAction =
        state.mode === 'generated' && state.generatedFlowId
          ? 'generate'
          : (lastOriginRef.current?.origin_action ?? 'unknown');
      const flow_id: string | undefined =
        state.mode === 'generated' && state.generatedFlowId
          ? state.generatedFlowId
          : lastOriginRef.current?.flow_id;

      trackCopiedToClipboard({
        auth_state: authState,
        content_type: contentType,
        copy_context: copyContext,
        exclude_present: excludePresent,
        exclude_count_bucket,
        origin_action,
        flow_id,
        prompt_generation_id: state.promptGenerationId,
      });

      const methodByType: Record<CopyContentType, OutputUsedMethod> = {
        style_prompt: 'copy_style_prompt',
        exclude: 'copy_exclude',
        lyrics: 'copy_lyrics',
        title: 'copy_title',
        suno_link: 'copy_suno_link',
      };
      trackOutputUsed({
        auth_state: authState,
        method: methodByType[contentType],
        style_prompt_id: state.stylePromptId,
        lyrics_thread_id: state.lyricsThreadId,
        copy_context: copyContext,
        exclude_present: excludePresent,
        exclude_count_bucket,
        origin_mode: state.mode,
        origin_action,
        flow_id,
        prompt_generation_id: state.promptGenerationId,
      });
    } catch (err) {
      trackCopiedToClipboardFailed({
        auth_state: authState,
        content_type: contentType,
        copy_context: copyContext,
        exclude_present: excludePresent,
        exclude_count_bucket,
        error_type: err instanceof Error ? err.name : 'unknown',
        origin_action: lastOriginRef.current?.origin_action ?? 'unknown',
        flow_id: lastOriginRef.current?.flow_id,
        prompt_generation_id: state.promptGenerationId,
      });
    }
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
          <HStack justify="space-between" align="flex-start" spacing={4}>
            <Box flex="1" minW={0}>
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
                  w="100%"
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
                    noOfLines={2}
                  >
                    {state.styleFields.title || 'Untitled Style'}
                  </Text>
                </Tooltip>
              )}
            </Box>
            <Link
              href={buildSunoUrl()}
              isExternal
              color="gray.400"
              fontSize="sm"
              _hover={{ color: 'purple.300' }}
              whiteSpace="nowrap"
              flexShrink={0}
              pt={1}
              onClick={() => {
                const excludeText = state.styleFields.exclude || '';
                const excludePresent = excludeText.trim().length > 0;
                const excludeCount = excludePresent ? excludeText.split(',').filter(Boolean).length : 0;
                const exclude_count_bucket: '0' | '1-2' | '3-5' | '6+' =
                  excludeCount === 0 ? '0' : excludeCount <= 2 ? '1-2' : excludeCount <= 5 ? '3-5' : '6+';
                const origin_action: OriginAction =
                  state.mode === 'generated' && state.generatedFlowId
                    ? 'generate'
                    : (lastOriginRef.current?.origin_action ?? 'unknown');
                const flow_id: string | undefined =
                  state.mode === 'generated' && state.generatedFlowId
                    ? state.generatedFlowId
                    : lastOriginRef.current?.flow_id;
                trackSunoLinkClicked({
                  auth_state: authState,
                  exclude_present: excludePresent,
                  exclude_count_bucket,
                  origin_mode: state.mode,
                  origin_action,
                  flow_id,
                  prompt_generation_id: state.promptGenerationId,
                });
                trackOutputUsed({
                  auth_state: authState,
                  method: 'open_suno',
                  style_prompt_id: state.stylePromptId,
                  lyrics_thread_id: state.lyricsThreadId,
                  exclude_present: excludePresent,
                  exclude_count_bucket,
                  origin_mode: state.mode,
                  origin_action,
                  flow_id,
                  prompt_generation_id: state.promptGenerationId,
                });
              }}
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
                <Text fontSize="xs" color="gray.500">
                  Weird {state.styleFields.weirdness}% · Influence {state.styleFields.style_influence}%
                </Text>
              </HStack>
              <HStack spacing={3} onClick={(e) => e.stopPropagation()}>
                {/* Refine Style button */}
                <Tooltip label="Refine style with AI (creates new version)" placement="top" hasArrow>
                  <HStack
                    spacing={1}
                    cursor="pointer"
                    onClick={(e) => {
                      e.stopPropagation();
                      const opening = !styleRefineOpen;
                      setStyleRefineOpen(opening);
                      if (opening) {
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
                  onClick={() =>
                    copyToClipboard(state.styleFields.suno_prompt, 'style_prompt', 'song_view_style_prompt')
                  }
                />
              </HStack>
            </HStack>

            <Collapse in={styleExpanded} animateOpacity>
              <VStack spacing={3} align="stretch" mt={2}>
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
                  <Text fontSize="xs" color="gray.500">
                    {state.styleFields.exclude.split(',').length} items
                  </Text>
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
                    copyToClipboard(state.styleFields.exclude, 'exclude', 'song_view_exclude');
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

          {/* Style Refine Input - accent line style, positioned after Exclude */}
          <Collapse in={styleRefineOpen} animateOpacity>
            <Box
              mt={2}
              mb={2}
              pl={3}
              py={2}
              borderLeft="2px solid"
              borderColor="purple.500"
              bg="linear-gradient(90deg, rgba(128, 90, 213, 0.1) 0%, transparent 100%)"
            >
              <VStack spacing={1} align="stretch">
                <HStack spacing={2}>
                  <Input
                    ref={styleRefineInputRef}
                    value={styleRefineText}
                    onChange={(e) => setStyleRefineText(e.target.value)}
                    placeholder='e.g. "add more synths", "make it darker", "less electronic"'
                    variant="unstyled"
                    fontSize="sm"
                    color="gray.100"
                    _placeholder={{ color: 'gray.500' }}
                    flex={1}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && styleRefineText.trim() && !isEditingLyrics) {
                        e.preventDefault();
                        handleStyleRefineSubmit();
                      }
                      if (e.key === 'Escape') {
                        setStyleRefineOpen(false);
                        setStyleRefineText('');
                      }
                    }}
                  />
                  <Text
                    fontSize="xs"
                    color="gray.600"
                    cursor="pointer"
                    _hover={{ color: 'gray.400' }}
                    onClick={() => {
                      setStyleRefineOpen(false);
                      setStyleRefineText('');
                    }}
                  >
                    cancel
                  </Text>
                  <Tooltip 
                    label="Wait for edit to finish" 
                    isDisabled={!isEditingLyrics}
                    placement="top"
                    hasArrow
                  >
                    <Text
                      fontSize="xs"
                      color={isEditingLyrics ? 'gray.600' : (styleRefineText.trim() ? 'purple.400' : 'gray.600')}
                      cursor={isEditingLyrics ? 'not-allowed' : (styleRefineText.trim() ? 'pointer' : 'default')}
                      fontWeight="medium"
                      opacity={isEditingLyrics ? 0.5 : 1}
                      _hover={isEditingLyrics ? {} : (styleRefineText.trim() ? { color: 'purple.300' } : {})}
                      onClick={() => !isEditingLyrics && styleRefineText.trim() && handleStyleRefineSubmit()}
                    >
                      {isRefiningStyle ? 'refining…' : 'refine →'}
                    </Text>
                  </Tooltip>
                </HStack>
                {/* Second line: wait message (reserve space) */}
                <Text 
                  fontSize="xs" 
                  color={showRefineWaitMessage && isRefiningStyle ? 'gray.500' : 'transparent'}
                >
                  Generations can take up to a minute...
                </Text>
              </VStack>
            </Box>
          </Collapse>

          <Divider borderColor="gray.700" />

          {/* === SONG TABS === */}
          <Box>
            {loadingThreads ? (
              <HStack spacing={2} py={2}>
                <Spinner size="sm" color="gray.500" />
                <Text fontSize="sm" color="gray.500">Loading songs...</Text>
              </HStack>
            ) : (
              <HStack 
                spacing={0}
                overflowX="auto" 
                overflowY="hidden"
                borderBottom="1px solid"
                borderColor="gray.700"
                css={{
                  '&::-webkit-scrollbar': { 
                    height: '0px',
                    transition: 'height 0.2s ease',
                  },
                  '&::-webkit-scrollbar-thumb': { 
                    background: '#4A5568', 
                    borderRadius: '2px',
                  },
                  '&:hover::-webkit-scrollbar': { height: '4px' },
                }}
              >
                {threads.map((thread, idx) => {
                  const isSelected = thread.id === state.lyricsThreadId && !draftOpen;
                  const isDragging = draggedIdx === idx;
                  const isDropTarget = dragOverIdx === idx && draggedIdx !== null && draggedIdx !== idx;
                  return (
                    <HStack
                      key={thread.id}
                      px={3}
                      py={2}
                      spacing={1}
                      cursor="grab"
                      fontSize="sm"
                      whiteSpace="nowrap"
                      color={isSelected ? 'white' : 'gray.500'}
                      bg={isSelected ? 'gray.800' : 'transparent'}
                      borderTopRadius="md"
                      borderBottom="2px solid"
                      borderColor={isSelected ? 'purple.500' : 'transparent'}
                      mb="-1px"
                      opacity={isDragging ? 0.4 : 1}
                      borderLeft={isDropTarget ? '3px solid' : 'none'}
                      borderLeftColor="purple.400"
                      ml={isDropTarget ? '-3px' : 0}
                      _hover={{ 
                        color: isSelected ? 'white' : 'gray.300',
                        bg: isSelected ? 'gray.800' : 'whiteAlpha.50',
                      }}
                      transition="opacity 0.1s"
                      onClick={() => handleTabChange(idx)}
                      draggable
                      onDragStart={(e) => handleDragStart(e, idx)}
                      onDragOver={(e) => handleDragOver(e, idx)}
                      onDrop={(e) => handleDrop(e, idx)}
                      onDragEnd={handleDragEnd}
                      onDragLeave={handleDragLeave}
                    >
                      <Text>{thread.title || `Song ${idx + 1}`}</Text>
                    </HStack>
                  );
                })}
                {/* "New Song" draft tab - shown when draftOpen or no threads */}
                {(draftOpen || threads.length === 0) && (
                  <HStack
                    px={3}
                    py={2}
                    spacing={1}
                    cursor="pointer"
                    fontSize="sm"
                    whiteSpace="nowrap"
                    color="white"
                    bg="gray.800"
                    borderTopRadius="md"
                    borderBottom="2px solid"
                    borderColor="purple.500"
                    mb="-1px"
                    transition="all 0.15s"
                    onClick={() => {
                      setDraftOpen(true);
                      trackNewLyricsVariationClicked({ auth_state: authState });
                    }}
                  >
                    <Text>New Song</Text>
                  </HStack>
                )}
                {/* "+ New" button - only show when draft is not open and we have threads */}
                {!draftOpen && threads.length > 0 && (
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
                )}
              </HStack>
            )}
          </Box>

          {/* === DRAFT COMPOSER (New Song) === */}
          {draftOpen && (
            <Box px={3} pt={3}>
              <VStack spacing={3} align="stretch">
                {/* Lyrics section - styled like NewSongView */}
                <Box
                  borderWidth="1px"
                  borderColor="gray.700"
                  borderRadius="lg"
                  overflow="hidden"
                >
                  {/* Section header */}
                  <HStack px={4} py={3} justify="space-between">
                    <Text fontWeight="medium">Lyrics</Text>
                    <Tooltip label="Generate random topic" placement="top" hasArrow>
                      <IconButton
                        aria-label="Surprise me"
                        icon={<LuDices size={14} />}
                        size="xs"
                        variant="ghost"
                        isLoading={isGeneratingTopic}
                        onClick={handleGenerateTopic}
                        color="gray.400"
                        _hover={{ color: 'white' }}
                      />
                    </Tooltip>
                  </HStack>

                  {/* Section content */}
                  <Box px={4} pb={4}>
                    <Textarea
                      value={draftLyricsAbout}
                      onChange={(e) => setDraftLyricsAbout(e.target.value)}
                      placeholder="Write some lyrics or a prompt — or leave blank for instrumental"
                      bg="transparent"
                      border="none"
                      fontSize="sm"
                      minH="60px"
                      resize="none"
                      maxLength={500}
                      p={0}
                      _focus={{ boxShadow: 'none' }}
                    />
                  </Box>
                </Box>

                {/* Create button - styled like NewSongView */}
                <Button
                  colorScheme="gray"
                  bg="gray.800"
                  _hover={{ bg: 'gray.700' }}
                  size="lg"
                  w="100%"
                  onClick={handleCreateSong}
                  isLoading={isCreatingSong}
                  loadingText="Creating..."
                  leftIcon={<LuSparkles size={18} />}
                >
                  Create
                </Button>

                {/* Keyboard shortcut hint */}
                <Text fontSize="xs" color="gray.600" textAlign="center">
                  {isCreatingSong && showLongWaitMessage
                    ? 'Generations can take up to a minute...'
                    : '⌘ Enter to create'}
                </Text>
              </VStack>
            </Box>
          )}

          {/* === SONG CONTENT === */}
          {!draftOpen && state.lyricsThreadId && (
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
                    onClick={() =>
                      copyToClipboard(
                        state.lyricsFields.lyrics_title || 'Untitled Song',
                        'title',
                        'song_view_title'
                      )
                    }
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
                  {/* Edit Lyrics button with sparkle icon (AI indicator) */}
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
                      <Box as={LuSparkles} boxSize={3.5} color={lyricsEditOpen ? 'blue.200' : 'gray.500'} />
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

              {/* Lyrics Edit Input - inline accent line style */}
              <Collapse in={lyricsEditOpen} animateOpacity>
                <Box
                  mb={3}
                  pl={3}
                  py={2}
                  borderLeft="2px solid"
                  borderColor="blue.500"
                  bg="linear-gradient(90deg, rgba(66, 153, 225, 0.1) 0%, transparent 100%)"
                >
                  <VStack spacing={1} align="stretch">
                    <HStack spacing={2}>
                      <Input
                        ref={lyricsEditInputRef}
                        value={lyricsEditText}
                        onChange={(e) => setLyricsEditText(e.target.value)}
                        placeholder='e.g. "make it sadder", "add a bridge", "shorter verses"'
                        variant="unstyled"
                        fontSize="sm"
                        color="gray.100"
                        _placeholder={{ color: 'gray.500' }}
                        flex={1}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && lyricsEditText.trim() && !isRefiningStyle) {
                            e.preventDefault();
                            handleLyricsEditSubmit();
                          }
                          if (e.key === 'Escape') {
                            setLyricsEditOpen(false);
                            setLyricsEditText('');
                          }
                        }}
                      />
                      <Text
                        fontSize="xs"
                        color="gray.600"
                        cursor="pointer"
                        _hover={{ color: 'gray.400' }}
                        onClick={() => {
                          setLyricsEditOpen(false);
                          setLyricsEditText('');
                        }}
                      >
                        cancel
                      </Text>
                      <Tooltip 
                        label="Wait for refine to finish" 
                        isDisabled={!isRefiningStyle}
                        placement="top"
                        hasArrow
                      >
                        <Text
                          fontSize="xs"
                          color={isRefiningStyle ? 'gray.600' : (lyricsEditText.trim() ? 'blue.400' : 'gray.600')}
                          cursor={isRefiningStyle ? 'not-allowed' : (lyricsEditText.trim() ? 'pointer' : 'default')}
                          fontWeight="medium"
                          opacity={isRefiningStyle ? 0.5 : 1}
                          _hover={isRefiningStyle ? {} : (lyricsEditText.trim() ? { color: 'blue.300' } : {})}
                          onClick={() => !isRefiningStyle && lyricsEditText.trim() && handleLyricsEditSubmit()}
                        >
                          {isEditingLyrics ? 'editing…' : 'edit →'}
                        </Text>
                      </Tooltip>
                    </HStack>
                    {showEditWaitMessage && isEditingLyrics && (
                      <Text fontSize="xs" color="gray.500">
                        Generations can take up to a minute...
                      </Text>
                    )}
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
                {/* Copy lyrics button - top right of textarea (hidden for instrumental) */}
                {state.lyricsFields.lyrics_text && (
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
                      onClick={() =>
                        copyToClipboard(state.lyricsFields.lyrics_text, 'lyrics', 'song_view_lyrics')
                      }
                    />
                  </Tooltip>
                )}
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
