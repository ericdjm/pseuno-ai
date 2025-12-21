/**
 * Type definitions for Pseuno AI
 */

export interface UserSettings {
  timeRange: 'short_term' | 'medium_term' | 'long_term';
}

export const DEFAULT_SETTINGS: UserSettings = {
  timeRange: 'medium_term',
};

export const TIME_RANGE_LABELS: Record<string, string> = {
  short_term: 'Last 4 Weeks',
  medium_term: 'Last 6 Months',
  long_term: 'All Time',
};
