/**
 * WorkingState - single source of truth for the current prompt/song being edited.
 * 
 * This follows the plan's specification for the two-panel UX.
 */

import type { SavedSunoPrompt, LyricsThread } from '../api';

// Mode indicates how the current state was reached
export type WorkingMode = 'new' | 'loaded' | 'generated';

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
}

// Refine snapshot for in-place updates (when style didn't change)
export interface RefineSnapshot {
  suno_prompt?: string;
  lyrics_text?: string;
  lyrics_title?: string;
  exclude?: string;
  weirdness?: number;
}

// Action types for the reducer
export type WorkingAction =
  | { type: 'RESET' }
  | { type: 'LOAD_STYLE_PROMPT'; prompt: SavedSunoPrompt }
  | { type: 'SELECT_THREAD'; thread: LyricsThread }
  | { type: 'CLEAR_THREAD' }
  | { type: 'SET_GENERATED'; prompt: SavedSunoPrompt; threadId: number | null; threadTitle?: string | null; lyricsText?: string }
  | { type: 'EDIT_STYLE_FIELD'; field: keyof StyleFields; value: string | number | string[] }
  | { type: 'EDIT_LYRICS_TEXT'; value: string }
  | { type: 'EDIT_LYRICS_TITLE'; value: string }
  | { type: 'SAVE_THREAD_SUCCESS'; thread: LyricsThread }
  | { type: 'MARK_CLEAN'; which: 'style' | 'lyrics' | 'both' }
  | { type: 'APPLY_REFINE_SNAPSHOT'; snapshot: RefineSnapshot };

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

    case 'CLEAR_THREAD':
      return {
        ...state,
        lyricsThreadId: null,
        lyricsFields: {
          lyrics_text: '',
          lyrics_title: '',
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

    case 'MARK_CLEAN':
      if (action.which === 'both') {
        return { ...state, dirty: { style: false, lyrics: false } };
      }
      return {
        ...state,
        dirty: { ...state.dirty, [action.which]: false },
      };

    case 'APPLY_REFINE_SNAPSHOT': {
      // Apply in-place updates from a refine that didn't change suno_prompt
      const { snapshot } = action;
      const newState = { ...state };

      // Update style fields if provided
      if (snapshot.suno_prompt !== undefined) {
        newState.styleFields = { ...newState.styleFields, suno_prompt: snapshot.suno_prompt };
      }
      if (snapshot.exclude !== undefined) {
        newState.styleFields = { ...newState.styleFields, exclude: snapshot.exclude };
      }
      if (snapshot.weirdness !== undefined) {
        newState.styleFields = { ...newState.styleFields, weirdness: snapshot.weirdness };
      }

      // Update lyrics fields if provided
      if (snapshot.lyrics_text !== undefined) {
        newState.lyricsFields = { ...newState.lyricsFields, lyrics_text: snapshot.lyrics_text };
      }
      if (snapshot.lyrics_title !== undefined) {
        newState.lyricsFields = { ...newState.lyricsFields, lyrics_title: snapshot.lyrics_title };
      }

      // Clear dirty flags since server is now source of truth
      newState.dirty = { style: false, lyrics: false };

      return newState;
    }

    default:
      return state;
  }
}
