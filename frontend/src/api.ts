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

export interface GenerateRequest {
  time_range: 'short_term' | 'medium_term' | 'long_term';
  theme?: string;
  energy: number;
  rhythm_complexity: number;
  darkness: number;
  extra_notes?: string;
  preset?: string;
}

export interface GenerateResponse {
  concept_title: string;
  suno_prompt: string;
  lyrics: string;
  debug_profile?: TasteProfile;
}

// === Advanced Generation Types ===

export interface VibeIntent {
  primary_feeling: string;
  sensory_goals?: string[];
  context?: string;
}

export interface VocalControls {
  intensity?: string;
  range?: string;
  experimental?: string[];
}

export interface RhythmControls {
  complexity?: string;
  drops?: string;
  accents?: string[];
}

export interface TextureControls {
  organic_vs_synthetic?: number;
  atmosphere?: string[];
}

export interface StructureControls {
  fake_drops?: boolean;
  unresolved?: boolean;
  intentional_chaos?: boolean;
}

export interface RuleBreaking {
  break_melody?: boolean;
  break_rhythm?: boolean;
  permission_to_violate?: string[];
}

export interface ContentTheme {
  theme_type?: string;
  specific_topic?: string;
  repetition_style?: string;
}

export interface ContrastIteration {
  reference_id?: string;
  less_of?: string[];
  more_of?: string[];
  push_direction?: string;
}

export interface AdvancedGenerateRequest {
  vibe_intent?: VibeIntent;
  mode?: string;
  vocals?: VocalControls;
  rhythm?: RhythmControls;
  texture?: TextureControls;
  structure?: StructureControls;
  rule_breaking?: RuleBreaking;
  content_theme?: ContentTheme;
  contrast?: ContrastIteration;
  lyric_density?: string;
  separate_artifacts?: boolean;
  time_range?: TimeRange;
  extra_notes?: string;
  user_prompt?: string;
  selected_artists?: string[];
  excluded_artists?: string[];
  selected_genres?: string[];
  custom_vibes?: string[];
}

export interface AdvancedGenerateResponse {
  generation_id: string;
  concept_title: string;
  suno_prompt: string;
  lyrics: string;
  vibe_signature: {
    primary_feeling: string;
    sensory_goals: string[];
    mode: string;
    intensity_vector: {
      vocal: number;
      rhythmic: number;
      textural: number;
    };
    rule_breaking_active: boolean;
    iteration_mode: boolean;
  };
  control_layers_used: {
    vocals: boolean;
    rhythm: boolean;
    texture: boolean;
    structure: boolean;
    rule_breaking: boolean;
    content_theme: boolean;
    contrast_iteration: boolean;
    taste_profile: boolean;
  };
  debug_info?: {
    mode: string;
    lyric_density: string;
    taste_influence?: string;
    agent_model?: string;
    context_hash?: string;
  };
}

export type TimeRange = 'short_term' | 'medium_term' | 'long_term';

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
 * Generate Suno AI prompt and lyrics
 */
export async function generate(
  payload: GenerateRequest
): Promise<GenerateResponse> {
  const response = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<GenerateResponse>(response);
}

/**
 * Get available mode presets for advanced generation
 */
export async function getAvailableModes(): Promise<string[]> {
  const response = await fetch(`${API_BASE}/generate/modes`, {
    credentials: 'include',
  });
  const data = await handleResponse<{
    modes: Record<string, { description: string; vibe_keywords: string[] }>;
  }>(response);
  return Object.keys(data.modes || {});
}

/**
 * Generate with advanced vibe-first controls
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

// === Utility Functions ===

/**
 * Generate a shareable URL with encoded result
 */
export function createShareUrl(result: GenerateResponse): string {
  const data = {
    t: result.concept_title,
    p: result.suno_prompt,
    l: result.lyrics,
  };
  const encoded = btoa(encodeURIComponent(JSON.stringify(data)));
  return `${window.location.origin}${window.location.pathname}#share=${encoded}`;
}

/**
 * Parse a shared result from URL hash
 */
export function parseShareUrl(): GenerateResponse | null {
  const hash = window.location.hash;
  if (!hash.startsWith('#share=')) return null;
  
  try {
    const encoded = hash.slice(7);
    const decoded = JSON.parse(decodeURIComponent(atob(encoded)));
    return {
      concept_title: decoded.t || '',
      suno_prompt: decoded.p || '',
      lyrics: decoded.l || '',
    };
  } catch {
    return null;
  }
}

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
