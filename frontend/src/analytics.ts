/**
 * Analytics helper for PostHog events.
 * 
 * Event naming convention:
 * - snake_case for event names
 * - Low-cardinality properties only (no raw text, user IDs in properties)
 * - All events automatically include `environment` via posthog.register()
 * 
 * See POSTHOG_README.md for the full event contract.
 */

import posthog from 'posthog-js';

// ============================================================================
// Types
// ============================================================================

export type AuthState = 'guest' | 'spotify';
export type Page = 'new_song' | 'song_view';
export type Flow = 'generate' | 'refine' | 'library' | 'auth';
export type ChangeSource = 'manual' | 'ai_generate' | 'ai_refine';
export type CopyContentType = 'style_prompt' | 'exclude' | 'lyrics' | 'title' | 'suno_link';
export type CopyContext =
  | 'song_view_style_prompt'
  | 'song_view_exclude'
  | 'song_view_lyrics'
  | 'song_view_title'
  | 'advanced_style_prompt'
  | 'advanced_exclude'
  | 'advanced_lyrics'
  | 'advanced_title'
  | 'advanced_suno_link';
export type OriginMode = 'generated' | 'loaded' | 'new';
export type InstrumentalIntentSignal = 'empty' | 'keyword' | 'unknown';

export type OutputUsedMethod =
  | 'open_suno'
  | 'copy_style_prompt'
  | 'copy_exclude'
  | 'copy_lyrics'
  | 'copy_title'
  | 'copy_suno_link';

export type RandomizeLyricsContext = 'new_song_view' | 'draft_composer';

export type OriginAction =
  | 'generate'
  | 'style_refine'
  | 'lyrics_ai_edit'
  | 'manual_edit'
  | 'new_lyrics_in_style'
  | 'loaded'
  | 'unknown';

export type TagBucket =
  | 'indie rock'
  | 'electronic'
  | 'synth-pop'
  | 'dreamy'
  | 'lo-fi'
  | 'acoustic'
  | 'ambient'
  | 'jazzy'
  | 'upbeat'
  | 'melancholic'
  | 'funk'
  | 'r&b'
  | 'hip-hop'
  | 'folk'
  | 'cinematic'
  | 'other';

export function tagsToBuckets(tags: string[] | null | undefined): TagBucket[] {
  const allowed = new Set<TagBucket>([
    'indie rock',
    'electronic',
    'synth-pop',
    'dreamy',
    'lo-fi',
    'acoustic',
    'ambient',
    'jazzy',
    'upbeat',
    'melancholic',
    'funk',
    'r&b',
    'hip-hop',
    'folk',
    'cinematic',
  ]);
  const buckets: TagBucket[] = [];
  const seen = new Set<string>();
  for (const raw of tags || []) {
    const t = String(raw || '').trim().toLowerCase();
    if (!t) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    if (allowed.has(t as TagBucket)) buckets.push(t as TagBucket);
  }
  return buckets.length ? buckets : ['other'];
}

export function primaryTagBucket(tags: string[] | null | undefined): TagBucket {
  const buckets = tagsToBuckets(tags);
  return buckets[0] ?? 'other';
}

function bucketCount(count: number): '0' | '1' | '2' | '3' | '4+' {
  if (count <= 0) return '0';
  if (count === 1) return '1';
  if (count === 2) return '2';
  if (count === 3) return '3';
  return '4+';
}

function safeUuid(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return (crypto as any).randomUUID();
    }
  } catch {
    // ignore
  }
  return `sid_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

export function createFlowId(): string {
  return safeUuid();
}

function getClientSessionId(): string {
  const key = 'pseuno:client_session_id';
  try {
    const existing = window.sessionStorage.getItem(key);
    if (existing) return existing;
    const next = safeUuid();
    window.sessionStorage.setItem(key, next);
    return next;
  } catch {
    return 'unknown';
  }
}

function capture(event: string, props: Record<string, unknown>) {
  posthog.capture(event, {
    client_session_id: getClientSessionId(),
    client_time_ms: Date.now(),
    ...props,
  });
}

// ============================================================================
// Auth Events
// ============================================================================

export function trackAuthLoginClicked() {
  capture('auth_login_clicked', { flow: 'auth' });
}

export function trackAuthLoginSucceeded() {
  capture('auth_login_succeeded', { flow: 'auth' });
}

export function trackAuthLoginFailed(errorType?: string) {
  capture('auth_login_failed', { 
    flow: 'auth',
    error_type: errorType || 'unknown',
  });
}

export function trackAuthStatusLoaded(authenticated: boolean) {
  capture('auth_status_loaded', { 
    flow: 'auth',
    authenticated,
    auth_state: authenticated ? 'spotify' : 'guest',
  });
}

export function trackAuthLogout() {
  capture('auth_logout', { flow: 'auth' });
}

// ============================================================================
// Generate Events (NewSongView)
// ============================================================================

export function trackGenerateClicked(props: {
  auth_state: AuthState;
  has_lyrics_input: boolean;
  has_style_input: boolean;
  personalize_enabled: boolean;
  instrumental_intended: boolean;
  instrumental_intent_signal: InstrumentalIntentSignal;
  flow_id?: string;
  used_randomize_style?: boolean;
  used_randomize_lyrics?: boolean;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
  // Tag analytics
  tags_selected?: string[];
  tags_count?: number;
  tags_recommended_count?: number;
  tags_auto_picked_count?: number;
}) {
  capture('generate_clicked', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

export function trackGenerateSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  has_lyrics: boolean;
  instrumental_intended: boolean;
  instrumental_intent_signal: InstrumentalIntentSignal;
  flow_id?: string;
  used_randomize_style?: boolean;
  used_randomize_lyrics?: boolean;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
  // Tag analytics
  tags_selected?: string[];
  tags_count?: number;
  tags_recommended_count?: number;
  tags_auto_picked_count?: number;
}) {
  capture('generate_succeeded', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

export function trackGenerateFailed(props: {
  auth_state: AuthState;
  duration_ms: number;
  error_type: string;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('generate_failed', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

export function trackGenerateWaitNoticeShown(props: {
  auth_state: AuthState;
  wait_seconds: number;
}) {
  capture('generate_wait_notice_shown', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

// ============================================================================
// Style refine (AI) + Lyrics AI edits (WorkingPromptPanel)
// ============================================================================

// NOTE: We keep emitting legacy `refine_*` events (with `refine_type`) for
// backwards-compatible dashboards, but new dashboards should use:
// - `style_refine_*` for style changes (forks a new style)
// - `lyrics_ai_edit_*` for in-place lyrics edits

function captureStyleRefineCompat(
  event: 'style_refine_started' | 'style_refine_succeeded' | 'style_refine_failed',
  props: Record<string, unknown>
) {
  capture(event, {
    flow: 'style_refine',
    page: 'song_view',
    ...props,
  });
}

function captureLyricsAiEditCompat(
  event:
    | 'lyrics_ai_edit_started'
    | 'lyrics_ai_edit_succeeded'
    | 'lyrics_ai_edit_failed',
  props: Record<string, unknown>
) {
  capture(event, {
    flow: 'lyrics_ai_edit',
    page: 'song_view',
    ...props,
  });
}

function captureLegacyRefineCompat(
  event: 'refine_started' | 'refine_succeeded' | 'refine_failed',
  refine_type: 'style' | 'lyrics',
  props: Record<string, unknown>
) {
  capture(event, {
    flow: 'refine',
    page: 'song_view',
    refine_type,
    ...props,
  });
}

export function trackStyleRefineStarted(props: { auth_state: AuthState }) {
  captureStyleRefineCompat('style_refine_started', props);
  captureLegacyRefineCompat('refine_started', 'style', props);
}

export function trackStyleRefineSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  created_new_style: boolean;
  updates_persisted?: boolean;
  changed_suno_prompt?: boolean;
  changed_exclude?: boolean;
  changed_weirdness?: boolean;
  changed_style_influence?: boolean;
  changed_lyrics?: boolean;
  changed_title?: boolean;
  changed_fields_count_bucket?: '0' | '1' | '2' | '3' | '4+';
  flow_id?: string;
}) {
  captureStyleRefineCompat('style_refine_succeeded', props);
  captureLegacyRefineCompat('refine_succeeded', 'style', props);
}

export function trackStyleRefineFailed(props: {
  auth_state: AuthState;
  duration_ms: number;
  error_type: string;
  flow_id?: string;
}) {
  captureStyleRefineCompat('style_refine_failed', props);
  captureLegacyRefineCompat('refine_failed', 'style', props);
}

export function trackLyricsAiEditStarted(props: { auth_state: AuthState }) {
  captureLyricsAiEditCompat('lyrics_ai_edit_started', props);
  captureLegacyRefineCompat('refine_started', 'lyrics', props);
}

export function trackLyricsAiEditSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  updates_persisted?: boolean;
  changed_suno_prompt?: boolean;
  changed_exclude?: boolean;
  changed_weirdness?: boolean;
  changed_style_influence?: boolean;
  changed_lyrics?: boolean;
  changed_title?: boolean;
  changed_fields_count_bucket?: '0' | '1' | '2' | '3' | '4+';
  flow_id?: string;
}) {
  captureLyricsAiEditCompat('lyrics_ai_edit_succeeded', props);
  captureLegacyRefineCompat('refine_succeeded', 'lyrics', props);
}

export function trackLyricsAiEditFailed(props: {
  auth_state: AuthState;
  duration_ms: number;
  error_type: string;
  flow_id?: string;
}) {
  captureLyricsAiEditCompat('lyrics_ai_edit_failed', props);
  captureLegacyRefineCompat('refine_failed', 'lyrics', props);
}

// ----------------------------------------------------------------------------
// Legacy wrappers (keep old call sites working if any remain)
// ----------------------------------------------------------------------------

export function trackRefineStarted(props: {
  auth_state: AuthState;
  refine_type: 'style' | 'lyrics';
}) {
  captureLegacyRefineCompat('refine_started', props.refine_type, props);
}

export function trackRefineSucceeded(props: {
  auth_state: AuthState;
  refine_type: 'style' | 'lyrics';
  duration_ms: number;
  created_new_style: boolean;
  updates_persisted?: boolean;
  changed_suno_prompt?: boolean;
  changed_exclude?: boolean;
  changed_weirdness?: boolean;
  changed_style_influence?: boolean;
  changed_lyrics?: boolean;
  changed_title?: boolean;
  changed_fields_count_bucket?: '0' | '1' | '2' | '3' | '4+';
}) {
  captureLegacyRefineCompat('refine_succeeded', props.refine_type, props);
}

export function trackRefineFailed(props: {
  auth_state: AuthState;
  refine_type: 'style' | 'lyrics';
  duration_ms: number;
  error_type: string;
}) {
  captureLegacyRefineCompat('refine_failed', props.refine_type, props);
}

// ============================================================================
// Library Events (Sidebar + WorkingPromptPanel)
// ============================================================================

export function trackStyleSelected(props: {
  auth_state: AuthState;
}) {
  capture('style_selected', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackThreadSelected(props: {
  auth_state: AuthState;
}) {
  capture('thread_selected', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackFavoriteToggled(props: {
  auth_state: AuthState;
  is_favorite: boolean;
}) {
  capture('favorite_toggled', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Style Creation Events (NewSongView)
// ============================================================================

/** User clicked "Surprise me" to randomize style prompt */
export function trackRandomizeStyleClicked(props: {
  auth_state: AuthState;
  personalize_enabled: boolean;
  manual_tags_count: number;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_style_clicked', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

export function trackRandomizeStyleFailed(props: {
  auth_state: AuthState;
  error_type: string;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_style_failed', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

export function trackRandomizeStyleSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  personalize_enabled: boolean;
  manual_tags_count: number;
  auto_picked_count: number;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_style_succeeded', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

/** User clicked dice button to randomize lyrics topic */
export function trackRandomizeLyricsClicked(props: {
  auth_state: AuthState;
  has_style_input: boolean;
  page?: Page;
  randomize_context?: RandomizeLyricsContext;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_lyrics_clicked', {
    flow: 'generate',
    page: props.page || 'new_song',
    randomize_context: props.randomize_context || 'new_song_view',
    ...props,
  });
}

export function trackRandomizeLyricsFailed(props: {
  auth_state: AuthState;
  error_type: string;
  duration_ms?: number;
  page?: Page;
  randomize_context?: RandomizeLyricsContext;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_lyrics_failed', {
    flow: 'generate',
    page: props.page || 'new_song',
    randomize_context: props.randomize_context || 'new_song_view',
    ...props,
  });
}

export function trackRandomizeLyricsSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  has_style_input: boolean;
  page?: Page;
  randomize_context?: RandomizeLyricsContext;
  flow_id?: string;
  primary_tag_bucket?: TagBucket;
  tag_buckets?: TagBucket[];
}) {
  capture('randomize_lyrics_succeeded', {
    flow: 'generate',
    page: props.page || 'new_song',
    randomize_context: props.randomize_context || 'new_song_view',
    ...props,
  });
}

/** User toggled "Personalize with Spotify" */
export function trackPersonalizeToggled(props: {
  auth_state: AuthState;
  is_enabled: boolean;
}) {
  capture('personalize_toggled', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

/** User added a tag to style */
export function trackTagAdded(props: {
  auth_state: AuthState;
  source: 'manual' | 'recommended' | 'auto_picked';
}) {
  capture('tag_added', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

/** User removed a tag from style */
export function trackTagRemoved(props: {
  auth_state: AuthState;
}) {
  capture('tag_removed', {
    flow: 'generate',
    page: 'new_song',
    ...props,
  });
}

// ============================================================================
// Library Workflow Events
// ============================================================================

/** User clicked to create new lyrics variation for existing style */
export function trackNewLyricsVariationClicked(props: {
  auth_state: AuthState;
  flow_id?: string;
}) {
  capture('new_lyrics_variation_clicked', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

/** User generated lyrics for a new song draft (not initial generate) */
export function trackDraftLyricsGenerated(props: {
  auth_state: AuthState;
  duration_ms: number;
  has_lyrics_about_input: boolean;
  flow_id?: string;
}) {
  capture('draft_lyrics_generated', {
    flow: 'generate',
    page: 'song_view',
    ...props,
  });
}

export function trackDraftLyricsFailed(props: {
  auth_state: AuthState;
  duration_ms: number;
  error_type: string;
  has_lyrics_about_input: boolean;
  flow_id?: string;
}) {
  capture('draft_lyrics_failed', {
    flow: 'generate',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// "New lyrics in existing style" end-to-end generation (draft composer)
// ============================================================================

export function trackNewLyricsInStyleStarted(props: {
  auth_state: AuthState;
  has_lyrics_about_input: boolean;
  flow_id?: string;
}) {
  capture('new_lyrics_in_style_started', {
    flow: 'generate',
    page: 'song_view',
    ...props,
  });
}

export function trackNewLyricsInStyleSucceeded(props: {
  auth_state: AuthState;
  duration_ms: number;
  has_lyrics_about_input: boolean;
  flow_id?: string;
}) {
  capture('new_lyrics_in_style_succeeded', {
    flow: 'generate',
    page: 'song_view',
    ...props,
  });
}

export function trackNewLyricsInStyleFailed(props: {
  auth_state: AuthState;
  duration_ms: number;
  error_type: string;
  has_lyrics_about_input: boolean;
  flow_id?: string;
}) {
  capture('new_lyrics_in_style_failed', {
    flow: 'generate',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Helpers (exported for event constructors in components)
// ============================================================================

export function changedFieldsToProps(changed_fields: string[] | null | undefined): {
  changed_suno_prompt: boolean;
  changed_exclude: boolean;
  changed_weirdness: boolean;
  changed_style_influence: boolean;
  changed_lyrics: boolean;
  changed_title: boolean;
  changed_fields_count_bucket: '0' | '1' | '2' | '3' | '4+';
} {
  const fields = new Set((changed_fields || []).map(f => String(f)));
  const count = fields.size;
  return {
    changed_suno_prompt: fields.has('suno_prompt'),
    changed_exclude: fields.has('exclude'),
    changed_weirdness: fields.has('weirdness'),
    changed_style_influence: fields.has('style_influence'),
    changed_lyrics: fields.has('lyrics'),
    changed_title: fields.has('title'),
    changed_fields_count_bucket: bucketCount(count),
  };
}

/** User copied text (style prompt, lyrics, etc.) to clipboard */
export function trackCopiedToClipboard(props: {
  auth_state: AuthState;
  content_type: CopyContentType;
  copy_context: CopyContext;
  exclude_present?: boolean;
  exclude_count_bucket?: '0' | '1-2' | '3-5' | '6+';
  flow_id?: string;
  origin_action?: OriginAction;
  prompt_generation_id?: string | null;
}) {
  capture('copied_to_clipboard', {
    flow: 'library',
    ...props,
  });
}

export function trackCopiedToClipboardFailed(props: {
  auth_state: AuthState;
  content_type: CopyContentType;
  copy_context: CopyContext;
  exclude_present?: boolean;
  exclude_count_bucket?: '0' | '1-2' | '3-5' | '6+';
  error_type: string;
  flow_id?: string;
  origin_action?: OriginAction;
  prompt_generation_id?: string | null;
}) {
  capture('copied_to_clipboard_failed', {
    flow: 'library',
    ...props,
  });
}

/** User clicked the Suno link to open in Suno */
export function trackSunoLinkClicked(props: {
  auth_state: AuthState;
  exclude_present?: boolean;
  exclude_count_bucket?: '0' | '1-2' | '3-5' | '6+';
  origin_mode?: OriginMode;
  flow_id?: string;
  origin_action?: OriginAction;
  prompt_generation_id?: string | null;
}) {
  capture('suno_link_clicked', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Canonical "user used output" event (for OR funnels + consistent export metrics)
// ============================================================================

export function trackOutputUsed(props: {
  auth_state: AuthState;
  method: OutputUsedMethod;
  style_prompt_id?: number | null;
  lyrics_thread_id?: number | null;
  // optional context for debugging/analysis
  copy_context?: CopyContext;
  exclude_present?: boolean;
  exclude_count_bucket?: '0' | '1-2' | '3-5' | '6+';
  origin_mode?: OriginMode;
  origin_action?: OriginAction;
  flow_id?: string;
  prompt_generation_id?: string | null;
}) {
  capture('output_used', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Manual vs AI edits (titles + lyrics)
// ============================================================================

export function trackStyleTitleChanged(props: {
  auth_state: AuthState;
  source: ChangeSource;
  flow_id?: string;
}) {
  capture('style_title_changed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackStyleTitleChangeFailed(props: {
  auth_state: AuthState;
  error_type: string;
  flow_id?: string;
}) {
  capture('style_title_change_failed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackSongTitleChanged(props: {
  auth_state: AuthState;
  source: ChangeSource;
  flow_id?: string;
}) {
  capture('song_title_changed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackSongTitleChangeFailed(props: {
  auth_state: AuthState;
  error_type: string;
  flow_id?: string;
}) {
  capture('song_title_change_failed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackLyricsManualEditSaved(props: {
  auth_state: AuthState;
  edit_size: 'small' | 'medium' | 'large';
  was_empty_before: boolean;
  flow_id?: string;
}) {
  capture('lyrics_manual_edit_saved', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackLyricsManualEditSaveFailed(props: {
  auth_state: AuthState;
  error_type: string;
  flow_id?: string;
}) {
  capture('lyrics_manual_edit_save_failed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Delete + reorder events
// ============================================================================

export function trackSongDeleted(props: {
  auth_state: AuthState;
  source: 'song_view' | 'sidebar';
  remaining_songs_bucket: '0' | '1-2' | '3-5' | '6+';
  flow_id?: string;
}) {
  capture('song_deleted', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackSongDeleteFailed(props: {
  auth_state: AuthState;
  source: 'song_view' | 'sidebar';
  error_type: string;
  flow_id?: string;
}) {
  capture('song_delete_failed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackStyleDeleted(props: {
  auth_state: AuthState;
  source: 'sidebar';
  flow_id?: string;
}) {
  capture('style_deleted', {
    flow: 'library',
    ...props,
  });
}

export function trackStyleDeleteFailed(props: {
  auth_state: AuthState;
  source: 'sidebar';
  error_type: string;
  flow_id?: string;
}) {
  capture('style_delete_failed', {
    flow: 'library',
    ...props,
  });
}

export function trackSongsReordered(props: {
  auth_state: AuthState;
  songs_count_bucket: '1-2' | '3-5' | '6+';
  move_direction: 'up' | 'down';
  flow_id?: string;
}) {
  capture('songs_reordered', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

export function trackSongsReorderFailed(props: {
  auth_state: AuthState;
  error_type: string;
  flow_id?: string;
}) {
  capture('songs_reorder_failed', {
    flow: 'library',
    page: 'song_view',
    ...props,
  });
}

// ============================================================================
// Identity Management
// ============================================================================

/**
 * Call when user successfully authenticates with Spotify.
 * This links the anonymous session to the Spotify user ID.
 */
export function identifyUser(spotifyUserId: string) {
  posthog.identify(spotifyUserId);
}

/**
 * Call on logout to reset the PostHog identity.
 */
export function resetIdentity() {
  posthog.reset();
}

