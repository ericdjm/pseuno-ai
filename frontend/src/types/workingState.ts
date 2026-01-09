/**
 * WorkingState - single source of truth for the current prompt/song being edited.
 * 
 * This follows the plan's specification for the two-panel UX.
 */

import type { SavedSunoPrompt, LyricsThread, LyricsCheckpoint } from '../api';

// Mode indicates how the current state was reached
export type WorkingMode = 'new' | 'loaded' | 'generated' | 'refining';

// Fields for the style prompt (the template)
export interface StyleFields {
  suno_prompt: string;
  exclude: string;
  title: string;
  weirdness: number;
  style_influence: number;
  auto_tags: string[];
}

// Fields for the lyrics (the song)
export interface LyricsFields {
  lyrics_text: string;
  lyrics_title: string;
}

// The main state shape
export interface WorkingState {
  // IDs
  stylePromptId: number | null;      // The loaded StylePrompt (SunoPrompt) ID
  lyricsThreadId: number | null;     // The loaded LyricsThread (song) ID

  // Field values
  styleFields: StyleFields;
  lyricsFields: LyricsFields;

  // Track which fields have been modified since last save
  dirty: {
    style: boolean;
    lyrics: boolean;
  };

  // Current mode
  mode: WorkingMode;

  // Checkpoints for the current thread
  checkpoints: LyricsCheckpoint[];

  // Is a refine in progress?
  isRefining: boolean;
}

// Action types for the reducer
export type WorkingAction =
  | { type: 'RESET' }
  | { type: 'LOAD_STYLE_PROMPT'; prompt: SavedSunoPrompt }
  | { type: 'SELECT_THREAD'; thread: LyricsThread }
  | { type: 'SET_GENERATED'; prompt: SavedSunoPrompt; threadId: number | null; threadTitle?: string | null; lyricsText?: string }
  | { type: 'EDIT_STYLE_FIELD'; field: keyof StyleFields; value: string | number | string[] }
  | { type: 'EDIT_LYRICS_TEXT'; value: string }
  | { type: 'EDIT_LYRICS_TITLE'; value: string }
  | { type: 'SAVE_THREAD_SUCCESS'; thread: LyricsThread }
  | { type: 'SET_CHECKPOINTS'; checkpoints: LyricsCheckpoint[] }
  | { type: 'ADD_CHECKPOINT'; checkpoint: LyricsCheckpoint }
  | { type: 'RESTORE_CHECKPOINT'; lyrics_text: string }
  | { type: 'REFINE_START' }
  | { type: 'REFINE_END'; newPromptId?: number; newThreadId?: number; updatedFields: Partial<StyleFields & LyricsFields> }
  | { type: 'MARK_CLEAN'; which: 'style' | 'lyrics' | 'both' };

// Initial state factory
export function createInitialWorkingState(): WorkingState {
  return {
    stylePromptId: null,
    lyricsThreadId: null,
    styleFields: {
      suno_prompt: '',
      exclude: '',
      title: '',
      weirdness: 50,
      style_influence: 50,
      auto_tags: [],
    },
    lyricsFields: {
      lyrics_text: '',
      lyrics_title: '',
    },
    dirty: {
      style: false,
      lyrics: false,
    },
    mode: 'new',
    checkpoints: [],
    isRefining: false,
  };
}

// Reducer
export function workingReducer(state: WorkingState, action: WorkingAction): WorkingState {
  switch (action.type) {
    case 'RESET':
      return createInitialWorkingState();

    case 'LOAD_STYLE_PROMPT':
      return {
        ...state,
        stylePromptId: action.prompt.id,
        lyricsThreadId: null, // Will be set by SELECT_THREAD
        styleFields: {
          suno_prompt: action.prompt.suno_prompt,
          exclude: action.prompt.exclude,
          title: action.prompt.title || '',
          weirdness: action.prompt.weirdness,
          style_influence: action.prompt.style_influence,
          auto_tags: action.prompt.auto_tags,
        },
        lyricsFields: {
          lyrics_text: '',
          lyrics_title: '',
        },
        dirty: { style: false, lyrics: false },
        mode: 'loaded',
        checkpoints: [],
        isRefining: false,
      };

    case 'SELECT_THREAD':
      return {
        ...state,
        // Sync stylePromptId from the thread to prevent inconsistency
        stylePromptId: action.thread.style_prompt_id,
        lyricsThreadId: action.thread.id,
        lyricsFields: {
          lyrics_text: action.thread.lyrics_text,
          lyrics_title: action.thread.title || '',
        },
        dirty: { ...state.dirty, lyrics: false },
      };

    case 'SET_GENERATED':
      return {
        ...state,
        stylePromptId: action.prompt.id,
        lyricsThreadId: action.threadId,
        styleFields: {
          suno_prompt: action.prompt.suno_prompt,
          exclude: action.prompt.exclude,
          title: action.prompt.title || '',
          weirdness: action.prompt.weirdness,
          style_influence: action.prompt.style_influence,
          auto_tags: action.prompt.auto_tags,
        },
        lyricsFields: {
          // Use thread-specific lyrics if provided, fallback to prompt.lyrics
          lyrics_text: action.lyricsText ?? action.prompt.lyrics,
          // Use thread title if provided, fallback to prompt title
          lyrics_title: action.threadTitle ?? action.prompt.title ?? '',
        },
        dirty: { style: false, lyrics: false },
        mode: 'generated',
        checkpoints: [],
        isRefining: false,
      };

    case 'EDIT_STYLE_FIELD':
      return {
        ...state,
        styleFields: {
          ...state.styleFields,
          [action.field]: action.value,
        },
        dirty: { ...state.dirty, style: true },
      };

    case 'EDIT_LYRICS_TEXT':
      return {
        ...state,
        lyricsFields: { ...state.lyricsFields, lyrics_text: action.value },
        dirty: { ...state.dirty, lyrics: true },
      };

    case 'EDIT_LYRICS_TITLE':
      return {
        ...state,
        lyricsFields: { ...state.lyricsFields, lyrics_title: action.value },
        dirty: { ...state.dirty, lyrics: true },
      };

    case 'SAVE_THREAD_SUCCESS':
      return {
        ...state,
        lyricsThreadId: action.thread.id,
        lyricsFields: {
          lyrics_text: action.thread.lyrics_text,
          lyrics_title: action.thread.title || '',
        },
        dirty: { ...state.dirty, lyrics: false },
      };

    case 'SET_CHECKPOINTS':
      return {
        ...state,
        checkpoints: action.checkpoints,
      };

    case 'ADD_CHECKPOINT':
      return {
        ...state,
        checkpoints: [action.checkpoint, ...state.checkpoints],
      };

    case 'RESTORE_CHECKPOINT':
      return {
        ...state,
        lyricsFields: { ...state.lyricsFields, lyrics_text: action.lyrics_text },
        dirty: { ...state.dirty, lyrics: true },
      };

    case 'REFINE_START':
      return {
        ...state,
        isRefining: true,
      };

    case 'REFINE_END': {
      const newState = { ...state, isRefining: false };

      // Update IDs if new ones were created (prompt changed)
      if (action.newPromptId) {
        newState.stylePromptId = action.newPromptId;
      }
      if (action.newThreadId) {
        newState.lyricsThreadId = action.newThreadId;
      }

      // Apply updated fields
      if (action.updatedFields.suno_prompt !== undefined) {
        newState.styleFields = { ...newState.styleFields, suno_prompt: action.updatedFields.suno_prompt };
      }
      if (action.updatedFields.exclude !== undefined) {
        newState.styleFields = { ...newState.styleFields, exclude: action.updatedFields.exclude };
      }
      if (action.updatedFields.title !== undefined) {
        newState.styleFields = { ...newState.styleFields, title: action.updatedFields.title };
      }
      if (action.updatedFields.weirdness !== undefined) {
        newState.styleFields = { ...newState.styleFields, weirdness: action.updatedFields.weirdness };
      }
      if (action.updatedFields.lyrics_text !== undefined) {
        newState.lyricsFields = { ...newState.lyricsFields, lyrics_text: action.updatedFields.lyrics_text };
      }

      return newState;
    }

    case 'MARK_CLEAN':
      if (action.which === 'both') {
        return { ...state, dirty: { style: false, lyrics: false } };
      }
      return {
        ...state,
        dirty: { ...state.dirty, [action.which]: false },
      };

    default:
      return state;
  }
}

