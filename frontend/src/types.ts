/**
 * Type definitions for Pseuno AI
 */

export interface UserSettings {
  timeRange: 'short_term' | 'medium_term' | 'long_term';
  energy: number;
  rhythmComplexity: number;
  darkness: number;
  preset: string | null;
}

export const DEFAULT_SETTINGS: UserSettings = {
  timeRange: 'medium_term',
  energy: 50,
  rhythmComplexity: 50,
  darkness: 50,
  preset: null,
};

export const TIME_RANGE_LABELS: Record<string, string> = {
  short_term: 'Last 4 Weeks',
  medium_term: 'Last 6 Months',
  long_term: 'All Time',
};

export const PRESET_OPTIONS = [
  { value: '', label: 'Auto (from taste)' },
  { value: 'indie_rock', label: 'Indie Rock' },
  { value: 'electronic', label: 'Electronic' },
  { value: 'hip_hop', label: 'Hip-Hop' },
  { value: 'cinematic', label: 'Cinematic' },
  { value: 'folk', label: 'Folk / Acoustic' },
  { value: 'synth_pop', label: 'Synth Pop' },
  { value: 'dream_pop', label: 'Dream Pop' },
  { value: 'r_and_b', label: 'R&B / Soul' },
];
