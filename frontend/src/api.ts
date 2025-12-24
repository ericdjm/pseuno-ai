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

export interface AdvancedGenerateRequest {
  user_prompt: string;
  lyrics_about: string;
  selected_artists?: string[];
  tags?: string[];
}

export interface AdvancedGenerateResponse {
  generation_id: string;
  concept_title: string;
  suno_prompt: string;
  lyrics: string;
  exclude: string;
  weirdness: number;
  style_influence: number;
  debug_info?: {
    agent_model?: string;
    context_hash?: string;
  };
}

export interface LyricsOnlyRequest {
  suno_prompt: string;
  lyrics_about: string;
}

export interface LyricsOnlyResponse {
  song_title: string;
  lyrics: string;
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
}

export interface UpdateSunoPromptRequest {
  title?: string;
  notes?: string;
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

/**
 * List the current user's saved prompts
 */
export async function listSavedPrompts(
  limit: number = 50,
  offset: number = 0
): Promise<SavedPromptsListResponse> {
  const response = await fetch(
    `${API_BASE}/prompts?limit=${limit}&offset=${offset}`,
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
