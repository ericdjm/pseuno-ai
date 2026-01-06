/**
 * Custom hooks for Pseuno AI
 */

import { useState, useEffect, useCallback } from 'react';
import { UserSettings, DEFAULT_SETTINGS } from './types';

const STORAGE_KEY = 'pseuno-ai-settings';

/**
 * Hook for persisting user settings in localStorage
 */
export function usePersistedSettings() {
  const [settings, setSettings] = useState<UserSettings>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
      }
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
    return DEFAULT_SETTINGS;
  });

  // Persist to localStorage whenever settings change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.error('Failed to save settings:', e);
    }
  }, [settings]);

  const updateSettings = useCallback((updates: Partial<UserSettings>) => {
    setSettings(prev => ({ ...prev, ...updates }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
  }, []);

  return { settings, updateSettings, resetSettings };
}

/**
 * Hook for clipboard functionality
 */
export function useClipboard(timeout = 2000) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), timeout);
      return true;
    } catch (e) {
      console.error('Failed to copy:', e);
      return false;
    }
  }, [timeout]);

  return { copied, copy };
}

// Storage key prefix for versioning
const SESSION_STORAGE_PREFIX = 'pseuno:v1:';

/**
 * Hook for persisting state in sessionStorage (tab-lifetime).
 * Survives back/forward navigation and refresh within the same tab,
 * but clears when the tab is closed.
 *
 * @param key - Unique key for this piece of state (will be prefixed with version)
 * @param initialValue - Default value if nothing is stored
 * @returns [value, setValue] tuple like useState
 */
export function useSessionStorageState<T>(
  key: string,
  initialValue: T
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const prefixedKey = SESSION_STORAGE_PREFIX + key;

  // Initialize state from sessionStorage or fallback to initialValue
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(prefixedKey);
      if (stored !== null) {
        return JSON.parse(stored) as T;
      }
    } catch (e) {
      // Safari private mode, quota exceeded, or JSON parse error
      console.warn(`Failed to load sessionStorage key "${prefixedKey}":`, e);
    }
    return initialValue;
  });

  // Persist to sessionStorage whenever value changes
  useEffect(() => {
    try {
      sessionStorage.setItem(prefixedKey, JSON.stringify(value));
    } catch (e) {
      console.warn(`Failed to save sessionStorage key "${prefixedKey}":`, e);
    }
  }, [prefixedKey, value]);

  return [value, setValue];
}
