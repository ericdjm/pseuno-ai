/**
 * API Layer for Pseuno AI
 * Handles all communication with the FastAPI backend
 */

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

// === Types ===

export interface SpotifyArtist {
  name: string;
  genres: string[];
  popularity: number;
  image_url: string | null;
  spotify_url: string | null;
}

export interface SpotifyTrack {
  name: string;
  artists: string[];
  album_name: string;
  album_image_url: string | null;
  popularity: number;
  spotify_url: string | null;
}

export interface TasteProfile {
  top_genres: string[];
  mood_tags: string[];
  summary_sentence: string;
  banned_references: string[];
}

export interface SpotifyProfileResponse {
  top_artists: SpotifyArtist[];
  top_tracks: SpotifyTrack[];
  taste_profile: TasteProfile;
  time_range: string;
}

export interface AuthStatus {
  authenticated: boolean;
  user_name?: string;
  user_image?: string;
}

// === Generation Types ===

export type PromptVariant =
  | 'v1'
  | 'v2_reddit_tricks'
  | 'v3_two_step'
  | 'v4_lyric_profile'
  | 'v5_hybrid'
  | 'v6_genre_disambiguation'
  | 'v7_genre_term_disambiguation'
  | 'v8_channel_split'
  | 'v9_comprehensive_exclude'
  | 'v10_suno_friendly';

// Lyric control types
export type LyricAudience = 'auto' | 'kids' | 'general' | 'adult';
export type LyricDirectness = 'auto' | 'direct' | 'balanced' | 'metaphor_heavy';
export type LyricHumor = 'auto' | 'none' | 'light' | 'comedic' | 'crude';
export type LyricExplicitness = 'auto' | 'clean' | 'innuendo' | 'explicit';
export type LyricPersona = 'auto' | 'earnest' | 'playful' | 'aggressive' | 'romantic' | 'melancholic';
// Lines per section control
// Controls number of lines per section, NOT line length
export type LyricLinesPerSection = 'auto' | '2_lines' | '4_lines' | '6_lines' | '8_lines';
// Line length control (syllables per line)
export type LyricLineLength = 'auto' | 'sparse' | 'short' | 'default' | 'long';
// Point of view / person control
export type LyricPOV = 'auto' | 'first' | 'second' | 'third' | 'none';
export type LyricRhymeScheme = 'auto' | 'aabb' | 'abab' | 'abcb' | 'aaaa' | 'internal';

export interface LyricControls {
  audience?: LyricAudience;
  directness?: LyricDirectness;
  humor?: LyricHumor;
  explicitness?: LyricExplicitness;
  persona?: LyricPersona;
  lines_per_section?: LyricLinesPerSection;
  line_length?: LyricLineLength;
  pov?: LyricPOV;
  rhyme_scheme?: LyricRhymeScheme;
}

export interface AdvancedGenerateRequest {
  user_prompt: string;
  lyrics_about: string;
  selected_artists?: string[];
  tags?: string[];
  prompt_variant?: PromptVariant;
  model?: string;
  style_model?: string;
  lyrics_model?: string;
  lyric_controls?: LyricControls;
}

export interface PromptLengthsBreakdown {
  combined?: number;  // Single-step only
  style?: number;     // Two-step only
  lyrics?: number;    // Two-step only
  repair: number;
  total: number;
}

export interface PromptVariantInfo {
  id: string;
  description: string;
  is_default: boolean;
  prompt_length: number;
  prompt_lengths: number[];  // Individual lengths per LLM call
  prompt_lengths_breakdown: PromptLengthsBreakdown;
}

export interface PromptVariantsResponse {
  variants: PromptVariantInfo[];
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
  is_style_default: boolean;
  is_lyrics_default: boolean;
}

export interface ModelsResponse {
  models: ModelInfo[];
  default_model: string;
  default_style_model: string;
  default_lyrics_model: string;
}

export interface LyricProfile {
  audience: 'kids' | 'general' | 'adult';
  directness: 'direct' | 'balanced' | 'metaphor_heavy';
  humor: 'none' | 'light' | 'comedic' | 'crude';
  explicitness: 'clean' | 'innuendo' | 'explicit';
  persona: 'earnest' | 'playful' | 'aggressive' | 'romantic' | 'melancholic';
  lines_per_section: '2_lines' | '4_lines' | '6_lines' | '8_lines';
  line_length: 'sparse' | 'short' | 'default' | 'long';
  pov: 'first' | 'second' | 'third' | 'none';
  rhyme_scheme: 'aabb' | 'abab' | 'abcb' | 'aaaa' | 'internal';
  devices?: string[];
  avoid?: string[];
}

// === Debug Trace Types (v1 schema) ===

export type SpanKind = 
  | 'llm_call'
  | 'validate'
  | 'parse'
  | 'format_context'
  | 'repair'
  | 'profile_infer'
  | 'branch'
  | 'other';

export interface DebugSpan {
  id: string;
  parent_id: string | null;
  name: string;
  kind: SpanKind;
  start_ms: number;
  end_ms: number;
  elapsed_ms: number;
  meta: Record<string, unknown>;
  artifacts: Record<string, string>;
}

export interface DebugTraceSummary {
  variant: string;
  model: string;
  fast_model: string | null;
  total_elapsed_ms: number;
  llm_calls: number;
  repairs: number;
  architecture: 'single_step' | 'two_step';
  success: boolean;
  error: string | null;
}

export interface DebugTrace {
  version: number;
  summary: DebugTraceSummary;
  spans: DebugSpan[];
}

export interface AdvancedGenerateResponse {
  generation_id: string;
  concept_title: string;
  suno_prompt: string;
  lyrics: string;
  exclude: string;
  weirdness: number;
  style_influence: number;
  prompt_id: number | null;
  is_favorite: boolean;
  auto_tags: string[];
  debug_info?: DebugTrace;
}

export interface LyricsOnlyRequest {
  suno_prompt: string;
  lyrics_about: string;
}

export interface LyricsOnlyResponse {
  song_title: string;
  lyrics: string;
}

// === Input Concept Types ===

export interface InputConceptRequest {
  genres?: string[];
  artists?: string[];
  mood?: string;
}

export interface InputConceptResponse {
  concept: string;
  chosen_genres: string[];
  genres: string[];
  artists: string[];
  mood: string | null;
}

export interface RefinementRequest {
  current_prompt: string;
  change_request: string;
}

export interface RefinementResponse {
  refined_prompt: string;
}

export interface LyricsRefinementRequest {
  current_lyrics: string;
  change_request: string;
}

export interface LyricsRefinementResponse {
  refined_lyrics: string;
}

// === Lyrics Topic Types ===

export interface LyricsTopicRequest {
  genres?: string[];
  moods?: string[];
  style_prompt?: string;
}

export interface LyricsTopicResponse {
  topic: string;
  chosen_moods: string[];
  reasoning: string | null;
}

export type TimeRange = 'short_term' | 'medium_term' | 'long_term';

// === Saved Prompts Types ===

export interface SavedSunoPrompt {
  id: number;
  suno_prompt: string;
  exclude: string;
  weirdness: number;
  style_influence: number;
  title: string | null;
  notes: string | null;
  is_favorite: boolean;
  auto_tags: string[];
  generation_id: string | null;
  visibility: 'private' | 'unlisted' | 'public';
  share_id: string;
  created_at: string;
  updated_at: string;
}

export interface SavedPromptsListResponse {
  prompts: SavedSunoPrompt[];
  total: number;
}

export interface CreateSunoPromptRequest {
  suno_prompt: string;
  exclude: string;
  weirdness: number;
  style_influence: number;
  title?: string;
  notes?: string;
  is_favorite?: boolean;
}

export interface UpdateSunoPromptRequest {
  title?: string;
  notes?: string;
  is_favorite?: boolean;
  visibility?: 'private' | 'unlisted' | 'public';
}

// === API Error Handling ===

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '';
    try {
      const data = await response.json();
      detail = data.detail || '';
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(
      `API Error: ${response.status}`,
      response.status,
      detail
    );
  }
  return response.json();
}

// === Auth Functions ===

/**
 * Get the Spotify OAuth login URL
 * Opens in a new window/redirects to Spotify
 */
export async function login(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/auth/spotify/login`, {
      credentials: 'include',
    });
    const data = await handleResponse<{ auth_url: string }>(response);
    
    // Redirect to Spotify auth
    window.location.href = data.auth_url;
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
}

/**
 * Check if user is authenticated
 */
export async function checkAuthStatus(): Promise<AuthStatus> {
  try {
    const response = await fetch(`${API_BASE}/auth/status`, {
      credentials: 'include',
    });
    return handleResponse<AuthStatus>(response);
  } catch (error) {
    console.error('Auth check failed:', error);
    return { authenticated: false };
  }
}

/**
 * Log out and clear session
 */
export async function logout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch (error) {
    console.error('Logout failed:', error);
  }
  // Always clear local state regardless of API response
}

// === Spotify Data Functions ===

/**
 * Get user's Spotify profile with taste analysis
 */
export async function getProfile(
  timeRange: TimeRange = 'medium_term'
): Promise<SpotifyProfileResponse> {
  const response = await fetch(
    `${API_BASE}/spotify/profile?time_range=${timeRange}`,
    {
      credentials: 'include',
    }
  );
  return handleResponse<SpotifyProfileResponse>(response);
}

// === Generation Functions ===

/**
 * Generate with the Suno formatter agent
 */
export async function generateAdvanced(
  payload: AdvancedGenerateRequest
): Promise<AdvancedGenerateResponse> {
  const response = await fetch(`${API_BASE}/generate/advanced`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<AdvancedGenerateResponse>(response);
}

/**
 * Get available prompt variants for A/B testing
 */
export async function getPromptVariants(): Promise<PromptVariantsResponse> {
  const response = await fetch(`${API_BASE}/generate/prompt-variants`, {
    credentials: 'include',
  });
  return handleResponse<PromptVariantsResponse>(response);
}

/**
 * Get available LLM models
 */
export async function getModels(): Promise<ModelsResponse> {
  const response = await fetch(`${API_BASE}/generate/models`, {
    credentials: 'include',
  });
  return handleResponse<ModelsResponse>(response);
}

/**
 * Generate lyrics only using a saved Suno prompt as style context
 */
export async function generateLyricsOnly(
  payload: LyricsOnlyRequest
): Promise<LyricsOnlyResponse> {
  const response = await fetch(`${API_BASE}/generate/lyrics-only`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<LyricsOnlyResponse>(response);
}

/**
 * Generate a short 2-3 sentence Suno concept from artist influences.
 * 
 * This is the "input side" of generation - the returned concept can be
 * passed to generateAdvanced() as the user_prompt field.
 * 
 * v1: No login required. Artists come from request body only.
 * If artists array is empty, uses internal seed artists.
 */
export async function generateInputConcept(
  payload: InputConceptRequest = {}
): Promise<InputConceptResponse> {
  const response = await fetch(`${API_BASE}/generate/input-concept`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<InputConceptResponse>(response);
}

/**
 * Generate a short lyrics topic/theme from mood/genre influences.
 * 
 * This is the "lyrics input side" of generation - the returned topic can be
 * passed to generateAdvanced() or generateLyricsOnly() as the lyrics_about field.
 * 
 * v1: No login required. Template-based generation.
 * If moods/genres are empty, uses random seed moods.
 */
export async function generateLyricsTopic(
  payload: LyricsTopicRequest = {}
): Promise<LyricsTopicResponse> {
  const response = await fetch(`${API_BASE}/generate/lyrics-topic`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<LyricsTopicResponse>(response);
}

/**
 * Refine an existing prompt based on user feedback.
 * 
 * Uses an LLM to make targeted edits to the prompt while preserving
 * the original intent.
 */
export async function refineInputConcept(
  payload: RefinementRequest
): Promise<RefinementResponse> {
  const response = await fetch(`${API_BASE}/generate/refine-concept`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<RefinementResponse>(response);
}

/**
 * Refine existing lyrics based on user feedback.
 * 
 * Uses an LLM to make targeted edits to the lyrics while preserving
 * structure markers like [Verse], [Chorus], [Bridge], etc.
 */
export async function refineLyrics(
  payload: LyricsRefinementRequest
): Promise<LyricsRefinementResponse> {
  const response = await fetch(`${API_BASE}/generate/refine-lyrics`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<LyricsRefinementResponse>(response);
}

// === Saved Prompts Functions ===

/**
 * Save a Suno prompt as a favorite
 */
export async function createSavedPrompt(
  payload: CreateSunoPromptRequest
): Promise<SavedSunoPrompt> {
  const response = await fetch(`${API_BASE}/prompts`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<SavedSunoPrompt>(response);
}

export interface ListPromptsOptions {
  limit?: number;
  offset?: number;
  favoritesOnly?: boolean;
}

/**
 * List the current user's prompts (history or favorites only)
 */
export async function listSavedPrompts(
  options: ListPromptsOptions = {}
): Promise<SavedPromptsListResponse> {
  const { limit = 50, offset = 0, favoritesOnly = false } = options;
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    favorites_only: String(favoritesOnly),
  });
  const response = await fetch(
    `${API_BASE}/prompts?${params}`,
    {
      credentials: 'include',
    }
  );
  return handleResponse<SavedPromptsListResponse>(response);
}

/**
 * Get a single saved prompt by ID
 */
export async function getSavedPrompt(promptId: number): Promise<SavedSunoPrompt> {
  const response = await fetch(`${API_BASE}/prompts/${promptId}`, {
    credentials: 'include',
  });
  return handleResponse<SavedSunoPrompt>(response);
}

/**
 * Update a saved prompt's metadata
 */
export async function updateSavedPrompt(
  promptId: number,
  payload: UpdateSunoPromptRequest
): Promise<SavedSunoPrompt> {
  const response = await fetch(`${API_BASE}/prompts/${promptId}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<SavedSunoPrompt>(response);
}

/**
 * Delete a saved prompt
 */
export async function deleteSavedPrompt(promptId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/prompts/${promptId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new ApiError(`Delete failed: ${response.status}`, response.status);
  }
}

// === Utility Functions ===

/**
 * Check if there's an error in the URL (from OAuth callback)
 */
export function checkUrlError(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('error');
}

/**
 * Check if there's a success flag in the URL (from OAuth callback)
 */
export function checkUrlSuccess(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get('success') === 'true';
}

/**
 * Clear URL parameters after reading them
 */
export function clearUrlParams(): void {
  window.history.replaceState({}, '', window.location.pathname);
}
