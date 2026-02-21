/**
 * NewSongView - Minimalist composer for generating a new song (style + lyrics).
 * 
 * Features:
 * - Style prompt (multiline, required)
 * - Lyrics topic (single line, hidden if Instrumental)
 * - Instrumental toggle
 * - Primary CTA: Generate
 * - Advanced disclosure for extra knobs
 * - Spotify taste section (collapsed by default)
 */

import { useState, useRef, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Collapse,
  useToast,
  Tag,
  TagLabel,
  TagCloseButton,
  Tooltip,
  IconButton,
} from '@chakra-ui/react';
import { ChevronDownIcon, ChevronRightIcon, AddIcon } from '@chakra-ui/icons';
import { LuDices, LuMusic, LuUser } from 'react-icons/lu';
// TasteDisplay removed - taste is now used for tag recommendations only
import AutoGrowTextarea from './AutoGrowTextarea';
import {
  generateAdvanced,
  generateStyleSplit,
  generateLyricsSplit,
  saveGenerationResult,
  generateInputConcept,
  generateLyricsTopic,
  classifyStyle,
  getPromptVariants,
  getModels,
  getProfile,
  AdvancedGenerateRequest,
  AdvancedGenerateResponse,
  GenerateStyleRequest,
  GenerateLyricsRequest,
  SpotifyProfileResponse,
  PromptVariantInfo,
  PromptVariant,
  ModelInfo,
  LyricControls,
  LyricDirectness,
  LyricHumor,
  LyricExplicitness,
  LyricPOV,
  TimeRange,
  LyricsTopicDebugInfo,
} from '../api';
import { LyricsTopicDebugPanel } from './LyricsTopicDebugPanel';
import { useSessionStorageState } from '../hooks';
import {
  trackGenerateClicked,
  trackGenerateSucceeded,
  trackGenerateFailed,
  trackGenerateWaitNoticeShown,
  trackRandomizeStyleClicked,
  trackRandomizeStyleSucceeded,
  trackRandomizeLyricsClicked,
  trackRandomizeLyricsSucceeded,
  trackPersonalizeToggled,
  trackTagAdded,
  trackTagRemoved,
  trackRandomizeStyleFailed,
  trackRandomizeLyricsFailed,
  createFlowId,
  primaryTagBucket,
  tagsToBuckets,
} from '../analytics';

// Two-step variants that support instrumental mode
const TWO_STEP_VARIANTS: PromptVariant[] = [
  'v3_two_step',
  'v4_lyric_profile',
  'v5_hybrid',
  'v6_genre_disambiguation',
  'v7_genre_term_disambiguation',
  'v8_channel_split',
  'v9_comprehensive_exclude',
  'v10_suno_friendly',
];

// Lyric power-user controls are expressed as quick chips + an optional "More…" panel.

interface NewSongViewProps {
  onGenerate: (result: AdvancedGenerateResponse, meta?: { flow_id: string }) => void;
  onCancel: () => void;
  profile: SpotifyProfileResponse | null;
  profileLoading: boolean;
  isAuthenticated: boolean;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  /** Increment to reset inputs (style prompt, lyrics topic) */
  resetKey?: number;
}

export default function NewSongView({
  onGenerate,
  onCancel: _onCancel,
  profile,
  profileLoading: _profileLoading,
  isAuthenticated,
  timeRange: _timeRange,
  onTimeRangeChange: _onTimeRangeChange,
  resetKey,
}: NewSongViewProps) {
  // Note: unused props prefixed with _ are kept for potential future use
  const toast = useToast();

  // Core inputs (persisted)
  const [songPrompt, setSongPrompt] = useSessionStorageState('draft:songPrompt', '');
  const [lyricsAbout, setLyricsAbout] = useSessionStorageState('draft:lyricsAbout', '');

  // Debug info for lyrics topic (dev only)
  const [lyricsTopicDebug, setLyricsTopicDebug] = useState<{
    debug: LyricsTopicDebugInfo | null;
    bankId: string | null;
    basedOn: string;
  } | null>(null);

  // Cached style classifier result (for improved lyrics topic generation)
  const [cachedStyleTraits, setCachedStyleTraits] = useState<Record<string, number> | null>(null);
  const [cachedBankSimilarities, setCachedBankSimilarities] = useState<Record<string, number> | null>(null);
  const lastClassifiedPrompt = useRef<string>('');

  // Correlation: one flow_id per draft cycle (randomize → generate → output_used).
  const draftFlowIdRef = useRef<string>(createFlowId());
  const draftUsedRandomizeStyleRef = useRef<boolean>(false);
  const draftUsedRandomizeLyricsRef = useRef<boolean>(false);
  useEffect(() => {
    // Reset correlation id when the parent requests a reset.
    draftFlowIdRef.current = createFlowId();
    draftUsedRandomizeStyleRef.current = false;
    draftUsedRandomizeLyricsRef.current = false;
  }, [resetKey]);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [showLongWaitMessage, setShowLongWaitMessage] = useState(false);
  const [isGeneratingConcept, setIsGeneratingConcept] = useState(false);
  const [isGeneratingLyricsTopic, setIsGeneratingLyricsTopic] = useState(false);

  // Show "can take up to a minute" message after 10 seconds of loading
  useEffect(() => {
    if (!isLoading) {
      setShowLongWaitMessage(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowLongWaitMessage(true);
      trackGenerateWaitNoticeShown({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        wait_seconds: 10,
      });
    }, 10000);
    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated]);
  
  // Suno-like collapsible sections
  const [stylesExpanded, setStylesExpanded] = useState(true);
  const [lyricsExpanded, setLyricsExpanded] = useState(false);
  
  // Style tags (not persisted - clears on refresh)
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  // Track the source of each tag (key = lowercase tag, value = source)
  const [tagSources, setTagSources] = useState<Map<string, 'recommended' | 'auto_picked'>>(new Map());
  
  // Auto-picked tags from last "Surprise me" (shown as subtle chips)
  const [lastAutoPickedTags, setLastAutoPickedTags] = useState<string[]>([]);

  // Reset inputs when resetKey changes (e.g., user clicks "New Song")
  useEffect(() => {
    if (resetKey !== undefined && resetKey > 0) {
      setSongPrompt('');
      setLyricsAbout('');
      setSelectedTags([]);
      setTagSources(new Map());
      setLastAutoPickedTags([]);
    }
  }, [resetKey, setSongPrompt, setLyricsAbout]);
  
  // Max tags constant
  const MAX_TAGS = 5;
  
  // Personalize toggle for tag recommendations (defaults to ON when authenticated)
  const [personalize, setPersonalize] = useState(isAuthenticated);

  // Auto-enable personalization when user logs in
  useEffect(() => {
    if (isAuthenticated) {
      setPersonalize(true);
    }
  }, [isAuthenticated]);

  // Debounced async style classifier - runs when songPrompt changes
  // Caches results for use in lyrics topic generation
  useEffect(() => {
    const trimmedPrompt = songPrompt.trim();

    // If the user has changed the prompt since the last completed classification,
    // immediately invalidate cached async routing signals to avoid misleading debug
    // and stale routing influence.
    if (lastClassifiedPrompt.current && trimmedPrompt !== lastClassifiedPrompt.current) {
      setCachedStyleTraits(null);
      setCachedBankSimilarities(null);
    }
    
    // Skip if prompt is too short or unchanged
    if (trimmedPrompt.length < 10 || trimmedPrompt === lastClassifiedPrompt.current) {
      return;
    }

    // Debounce: wait 800ms after user stops typing
    const timeoutId = setTimeout(async () => {
      // Don't re-classify if prompt hasn't changed
      if (trimmedPrompt !== songPrompt.trim()) return;
      
      try {
        const result = await classifyStyle(trimmedPrompt);
        if (!result.success) return;

        const hasTraits = Object.keys(result.traits || {}).length > 0;
        const hasBankSims =
          Object.keys(result.bank_similarities || {}).length > 0;

        // Cache whatever signal we got. Many artist-only prompts produce few/no explicit traits,
        // but embeddings still provide strong bank routing signal.
        if (hasTraits) setCachedStyleTraits(result.traits);
        if (hasBankSims) setCachedBankSimilarities(result.bank_similarities || null);

        if (hasTraits || hasBankSims) {
          lastClassifiedPrompt.current = trimmedPrompt;
          console.log('[StyleClassifier] Cached:', {
            traits: result.traits,
            bankSims: result.bank_similarities,
            latency: `${result.latency_ms}ms`,
          });
        }
      } catch (error) {
        // Silent fail - classifier is optional enhancement
        console.warn('[StyleClassifier] Failed:', error);
      }
    }, 800);

    return () => clearTimeout(timeoutId);
  }, [songPrompt]);

  // Clear cached traits when prompt changes significantly
  useEffect(() => {
    if (songPrompt.trim().length < 5) {
      setCachedStyleTraits(null);
      setCachedBankSimilarities(null);
      lastClassifiedPrompt.current = '';
    }
  }, [songPrompt]);

  // When personalized, we merge multiple Spotify time ranges to build a larger, more robust tag pool.
  const [spotifyProfilesByRange, setSpotifyProfilesByRange] = useState<Partial<Record<TimeRange, SpotifyProfileResponse>>>({});

  // Slight variance for the selectable recommended tags (stable for a bit; not constantly jumping).
  // We reshuffle when "New Song" is clicked (resetKey changes) or personalization is toggled.
  const [recommendedTagsSeed, setRecommendedTagsSeed] = useState(() => Math.floor(Math.random() * 1_000_000_000));
  const [recommendedTags, setRecommendedTags] = useState<string[]>([]);

  useEffect(() => {
    setRecommendedTagsSeed(Math.floor(Math.random() * 1_000_000_000));
  }, [personalize]);

  useEffect(() => {
    if (resetKey !== undefined && resetKey > 0) {
      setRecommendedTagsSeed(Math.floor(Math.random() * 1_000_000_000));
    }
  }, [resetKey]);

  // Keep a local cache of Spotify profiles by time range for richer personalization.
  // We always include the currently provided `profile` (whatever time_range it was fetched with),
  // then opportunistically fetch the other ranges when Personalize is enabled.
  useEffect(() => {
    if (profile?.time_range) {
      const tr = profile.time_range as TimeRange;
      setSpotifyProfilesByRange((prev) => (prev[tr] ? prev : { ...prev, [tr]: profile }));
    }
  }, [profile]);

  // Use a ref to track which ranges have been fetched to avoid infinite loops.
  // The useEffect had spotifyProfilesByRange in deps, which caused a loop when setSpotifyProfilesByRange was called.
  const fetchedRangesRef = useRef<Set<TimeRange>>(new Set());
  
  useEffect(() => {
    if (!personalize || !isAuthenticated) return;

    let cancelled = false;
    const ranges: TimeRange[] = ['short_term', 'medium_term', 'long_term'];

    (async () => {
      try {
        // Check against ref to avoid re-fetching already attempted ranges
        const missing = ranges.filter((r) => !spotifyProfilesByRange[r] && !fetchedRangesRef.current.has(r));
        if (missing.length === 0) return;

        // Mark as in-flight to prevent duplicate concurrent requests
        missing.forEach((r) => fetchedRangesRef.current.add(r));

        const results = await Promise.allSettled(missing.map((r) => getProfile(r)));
        if (cancelled) return;

        const next: Partial<Record<TimeRange, SpotifyProfileResponse>> = { ...spotifyProfilesByRange };
        let hasNewData = false;
        results.forEach((res, idx) => {
          const r = missing[idx];
          if (res.status === 'fulfilled') {
            next[r] = res.value;
            hasNewData = true;
            // Range stays marked - successfully fetched
          } else {
            // Failed: remove from ref so it can be retried on next effect run
            fetchedRangesRef.current.delete(r);
          }
        });
        if (hasNewData) {
          setSpotifyProfilesByRange(next);
        }
      } catch {
        // Non-fatal: personalization still works with whatever profile we have.
      }
    })();

    return () => {
      cancelled = true;
    };
    // Note: spotifyProfilesByRange intentionally omitted to prevent infinite loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personalize, isAuthenticated]);
  
  // Categorized genre/mood recommendations - ensures diversity across categories
  // Each category contributes some items so suggestions never feel repetitive
  const GENRE_CATEGORIES: Record<string, string[]> = {
    // Core genres (always include at least 1-2)
    core: [
      'pop', 'rock', 'hip-hop', 'r&b', 'electronic', 'country', 'jazz', 'folk',
      'metal', 'punk', 'soul', 'blues', 'classical', 'reggae', 'funk',
    ],
    // Electronic subgenres
    electronic: [
      'house', 'techno', 'ambient', 'synthwave', 'lo-fi', 'chillout', 'trance',
      'drum and bass', 'dubstep', 'deep house', 'electropop', 'idm', 'vaporwave',
      'future bass', 'downtempo', 'trip-hop', 'acid house', 'progressive house',
      'breakbeat', 'garage', 'hyperpop', 'minimal techno', 'psytrance',
    ],
    // Rock subgenres
    rock: [
      'indie rock', 'alternative', 'grunge', 'post-punk', 'shoegaze', 'dream pop',
      'psychedelic rock', 'prog rock', 'art rock', 'garage rock', 'post-rock',
      'stoner rock', 'surf rock', 'new wave', 'britpop', 'glam rock', 'noise rock',
      'math rock', 'space rock', 'blues rock', 'southern rock', 'hard rock',
    ],
    // Hip-hop subgenres
    hiphop: [
      'trap', 'boom bap', 'conscious rap', 'drill', 'lo-fi hip-hop', 'cloud rap',
      'emo rap', 'melodic rap', 'g-funk', 'crunk', 'grime', 'southern rap',
      'underground hip-hop', 'gangsta rap', 'lyrical rap', 'mumble rap',
    ],
    // Metal subgenres
    metal: [
      'heavy metal', 'death metal', 'black metal', 'doom metal', 'thrash metal',
      'progressive metal', 'metalcore', 'nu metal', 'power metal', 'groove metal',
      'sludge metal', 'industrial metal', 'symphonic metal', 'djent', 'deathcore',
    ],
    // Pop subgenres
    pop: [
      'synth-pop', 'indie pop', 'art pop', 'dream pop', 'bedroom pop', 'dark pop',
      'chamber pop', 'baroque pop', 'city pop', 'dance pop', 'teen pop', 'k-pop',
      'j-pop', 'electropop', 'sophisti-pop',
    ],
    // Folk/Country/Acoustic
    acoustic: [
      'acoustic', 'folk pop', 'americana', 'bluegrass', 'alt-country', 'indie folk',
      'chamber folk', 'neo-folk', 'celtic', 'freak folk', 'outlaw country',
      'bro-country', 'country rock', 'honky-tonk', 'texas country',
    ],
    // Soul/R&B
    soul: [
      'neo-soul', 'contemporary r&b', 'quiet storm', 'new jack swing', 'gospel',
      'alt r&b', 'pbr&b', 'motown', 'disco', 'boogie',
    ],
    // Jazz
    jazz: [
      'jazz fusion', 'smooth jazz', 'bebop', 'free jazz', 'acid jazz', 'bossa nova',
      'cool jazz', 'modal jazz', 'big band', 'swing',
    ],
    // Latin/World
    world: [
      'reggaeton', 'latin pop', 'salsa', 'cumbia', 'afrobeat', 'afrobeats',
      'dancehall', 'soca', 'zouk', 'flamenco', 'fado', 'bossa nova', 'samba',
      'mariachi', 'corrido', 'bachata', 'banda', 'norteño', 'klezmer',
    ],
    // Moods/Vibes (always include some)
    moods: [
      'dreamy', 'melancholic', 'upbeat', 'dark', 'ethereal', 'nostalgic',
      'introspective', 'energetic', 'romantic', 'aggressive', 'chill', 'cinematic',
      'epic', 'haunting', 'playful', 'intense', 'atmospheric', 'raw', 'lush',
      'gritty', 'anthemic', 'intimate', 'euphoric', 'brooding', 'triumphant',
    ],
  };

  // Flatten all genres for the full pool
  const ALL_GENRES = Object.values(GENRE_CATEGORIES).flat();
  
  // Compute recommended tags using category-aware diversity sampling.
  // Ensures recommendations span multiple categories so they never feel repetitive.
  const computeRecommendedTags = (seed: number): string[] => {
    // Seeded RNG so the recs feel varied without changing every render.
    const mulberry32 = (a: number) => {
      return () => {
        let t = (a += 0x6D2B79F5);
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    };

    const rng = mulberry32(seed);

    const shuffleWithRng = <T,>(arr: T[]): T[] => {
      const copy = [...arr];
      for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy;
    };

    // Step 1: Build the candidate pool
    let candidatePool: string[] = [];

    if (personalize && isAuthenticated) {
      // Merge multiple time ranges for a richer pool
      const profiles: SpotifyProfileResponse[] = Object.values(spotifyProfilesByRange).filter(
        (p): p is SpotifyProfileResponse => Boolean(p)
      );

      const tasteGenres: string[] = [];
      const tasteMoods: string[] = [];
      const tasteArtists: string[] = [];
      const artistGenres: string[] = [];

      for (const p of profiles) {
        tasteGenres.push(...p.taste_profile.top_genres.slice(0, 20));
        tasteMoods.push(...p.taste_profile.mood_tags.slice(0, 10));
        tasteArtists.push(...p.top_artists.slice(0, 20).map((a) => a.name));
        artistGenres.push(...p.top_artists.flatMap((a) => a.genres || []).slice(0, 50));
      }

      // Priority order: user taste first, then expand with our taxonomy
      candidatePool = [...tasteGenres, ...artistGenres, ...tasteMoods, ...tasteArtists];
    }

    // Step 2: Category-aware sampling from our taxonomy
    // Sample 2-4 items from each category to ensure diversity
    const categoryOrder = shuffleWithRng(Object.keys(GENRE_CATEGORIES));
    for (const category of categoryOrder) {
      const categoryItems = shuffleWithRng(GENRE_CATEGORIES[category]);
      // Take 2-4 items per category (biased towards 3)
      const count = Math.floor(rng() * 3) + 2; // 2, 3, or 4
      candidatePool.push(...categoryItems.slice(0, count));
    }

    // Step 3: Dedupe case-insensitively but preserve original casing
    const uniqueByLower = new Map<string, string>();
    for (const raw of candidatePool) {
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const key = trimmed.toLowerCase();
      if (!uniqueByLower.has(key)) uniqueByLower.set(key, trimmed);
    }

    // Step 4: Filter out already selected and recently auto-picked
    const selectedLower = new Set(selectedTags.map((s) => s.toLowerCase()));
    const available = Array.from(uniqueByLower.entries())
      .filter(([key]) => !selectedLower.has(key))
      .map(([, value]) => value)
      .filter((t) => !lastAutoPickedTags.some((a) => a.toLowerCase() === t.toLowerCase()));

    // Step 5: Final shuffle and take top N
    return shuffleWithRng(available).slice(0, 32);
  };

  // Recompute recommendations when seed changes OR when Spotify profiles are updated.
  // This ensures artist tags appear once personalization data is fetched.
  useEffect(() => {
    setRecommendedTags(computeRecommendedTags(recommendedTagsSeed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommendedTagsSeed, spotifyProfilesByRange, personalize]);
  
  const addTag = (tag: string, source: 'recommended' | 'auto_picked' = 'recommended') => {
    // Preserve casing for display (e.g., Spotify artist names), but dedupe case-insensitively
    const trimmed = tag.trim();
    if (!trimmed) return;
    const key = trimmed.toLowerCase();
    const exists = selectedTags.some((t) => t.toLowerCase() === key);
    if (!exists) {
      setSelectedTags([...selectedTags, trimmed]);
      setTagSources((prev) => new Map(prev).set(key, source));
      trackTagAdded({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        source,
      });
    }
    // Remove from suggestions without reshuffling
    setRecommendedTags((prev) => prev.filter((t) => t.toLowerCase() !== key));
  };
  
  const removeTag = (tagToRemove: string) => {
    const key = tagToRemove.toLowerCase();
    setSelectedTags(selectedTags.filter((t) => t.toLowerCase() !== key));
    setTagSources((prev) => {
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
    trackTagRemoved({
      auth_state: isAuthenticated ? 'spotify' : 'guest',
    });
  };
  
  // Promote an auto-picked tag to selected
  const promoteAutoTag = (tag: string) => {
    if (selectedTags.length >= MAX_TAGS) return; // Already at max
    addTag(tag, 'auto_picked');
    setLastAutoPickedTags(lastAutoPickedTags.filter((t) => t.toLowerCase() !== tag.toLowerCase()));
  };
  

  // Prompt variant and model selection
  const [, setPromptVariants] = useState<PromptVariantInfo[]>([]); // Variants fetched for defaults
  const [selectedVariant, setSelectedVariant] = useSessionStorageState<PromptVariant | ''>('draft:selectedVariant', '');
  const [, setAvailableModels] = useState<ModelInfo[]>([]); // Models fetched for defaults
  const [selectedModel, setSelectedModel] = useSessionStorageState<string>('draft:selectedModel', '');
  const [selectedStyleModel, setSelectedStyleModel] = useSessionStorageState<string>('draft:selectedStyleModel', '');
  const [selectedLyricsModel, setSelectedLyricsModel] = useSessionStorageState<string>('draft:selectedLyricsModel', '');
  const initializedFromApi = useRef(false);

  // Lyric controls (power-user chips + optional More… panel)
  // Audience/persona controls removed from UI; keep values fixed at 'auto' for now
  const lyricAudience: 'auto' = 'auto';
  const [lyricDirectness, setLyricDirectness] = useSessionStorageState<LyricDirectness>('draft:lyricDirectness', 'auto');
  const [lyricHumor, setLyricHumor] = useSessionStorageState<LyricHumor>('draft:lyricHumor', 'auto');
  const [lyricExplicitness, setLyricExplicitness] = useSessionStorageState<LyricExplicitness>('draft:lyricExplicitness', 'auto');
  const lyricPersona: 'auto' = 'auto';
  const [lyricPOV, setLyricPOV] = useSessionStorageState<LyricPOV>('draft:lyricPOV', 'auto');

  // Lyrics controls (power user) panel
  const [lyricsControlsExpanded, setLyricsControlsExpanded] = useState(false);

  const MAX_STYLE_PROMPT_LEN = 500;
  const MAX_LYRICS_ABOUT_LEN = 500;

  // Load variants and models on mount (dev only)
  useEffect(() => {
    if (!import.meta.env.DEV) return;

    const fetchVariants = async () => {
      try {
        const response = await getPromptVariants();
        setPromptVariants(response.variants);
        if (!selectedVariant) {
          const defaultVariant = response.variants.find((v: PromptVariantInfo) => v.is_default);
          if (defaultVariant) {
            setSelectedVariant(defaultVariant.id as PromptVariant);
          }
        }
      } catch (error) {
        console.error('Failed to fetch prompt variants:', error);
      }
    };

    const fetchModels = async () => {
      try {
        const response = await getModels();
        setAvailableModels(response.models);
        if (!initializedFromApi.current) {
          if (!selectedModel) setSelectedModel(response.default_model);
          if (!selectedStyleModel) setSelectedStyleModel(response.default_style_model);
          if (!selectedLyricsModel) setSelectedLyricsModel(response.default_lyrics_model);
          initializedFromApi.current = true;
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }
    };

    fetchVariants();
    fetchModels();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Instrumental is implied when lyrics is empty
  const isInstrumental = !lyricsAbout.trim();
  const getInstrumentalIntent = () => {
    const text = (lyricsAbout || '').trim().toLowerCase();
    if (!text) return { instrumental_intended: true as const, instrumental_intent_signal: 'empty' as const };
    const phrases = ['instrumental', 'no lyrics', 'no vocal', 'no vocals', 'without lyrics', 'without vocals'];
    if (phrases.some((p) => text.includes(p))) {
      return { instrumental_intended: true as const, instrumental_intent_signal: 'keyword' as const };
    }
    return { instrumental_intended: false as const, instrumental_intent_signal: 'unknown' as const };
  };

  const handleGenerateConcept = async () => {
    const flowId = draftFlowIdRef.current;
    const tag_buckets = tagsToBuckets(selectedTags);
    trackRandomizeStyleClicked({
      auth_state: isAuthenticated ? 'spotify' : 'guest',
      personalize_enabled: personalize,
      manual_tags_count: selectedTags.length,
      flow_id: flowId,
      primary_tag_bucket: primaryTagBucket(selectedTags),
      tag_buckets,
    });
    const startTime = Date.now();
    setIsGeneratingConcept(true);
    try {
      // Send only user-selected tags; backend will decide how many extras to add (weighted toward fewer).
      // If personalized, also provide a candidate pool so Spotify-aided tags can be sampled (without forcing inclusion).
      let candidatePool: string[] | undefined;
      if (personalize && isAuthenticated) {
        // Big Spotify-aided pool merged across time ranges.
        const profiles: SpotifyProfileResponse[] = Object.values(spotifyProfilesByRange).filter(
          (p): p is SpotifyProfileResponse => Boolean(p)
        );

        const tasteGenres: string[] = [];
        const tasteMoods: string[] = [];
        const tasteArtists: string[] = [];
        const artistGenres: string[] = [];

        for (const p of profiles) {
          tasteGenres.push(...p.taste_profile.top_genres.slice(0, 30));
          tasteMoods.push(...p.taste_profile.mood_tags.slice(0, 12));
          tasteArtists.push(...p.top_artists.slice(0, 30).map((a) => a.name));
          artistGenres.push(...p.top_artists.flatMap((a) => a.genres || []).slice(0, 80));
        }

        const pool = [
          ...tasteGenres,
          ...artistGenres,
          ...tasteMoods,
          ...tasteArtists,
          ...ALL_GENRES,
        ];
        const seen = new Set<string>();
        candidatePool = [];
        for (const raw of pool) {
          const trimmed = raw.trim();
          if (!trimmed) continue;
          const key = trimmed.toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          candidatePool.push(trimmed);
        }
        // Backend schema limits candidate_genres to max 200 items
        if (candidatePool.length > 200) {
          candidatePool = candidatePool.slice(0, 200);
        }
      }

      const result = await generateInputConcept({
        genres: selectedTags,
        artists: [],
        candidate_genres: candidatePool,
      });
      setSongPrompt(result.concept);
      
      // Track auto-picked tags (chosen_genres that weren't in selectedTags)
      const selectedLower = selectedTags.map(t => t.toLowerCase());
      const autoPicked = result.chosen_genres.filter(
        g => !selectedLower.includes(g.toLowerCase())
      );
      setLastAutoPickedTags(autoPicked);
      draftUsedRandomizeStyleRef.current = true;
      
      // Reshuffle recommended tags after "Surprise me" so suggestions feel fresh
      setRecommendedTagsSeed(Math.floor(Math.random() * 1_000_000_000));
      trackRandomizeStyleSucceeded({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        duration_ms: Date.now() - startTime,
        personalize_enabled: personalize,
        manual_tags_count: selectedTags.length,
        auto_picked_count: autoPicked.length,
        flow_id: flowId,
        primary_tag_bucket: primaryTagBucket(selectedTags),
        tag_buckets,
      });
    } catch (error) {
      trackRandomizeStyleFailed({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        error_type: error instanceof Error ? error.name : 'unknown',
        flow_id: flowId,
        primary_tag_bucket: primaryTagBucket(selectedTags),
        tag_buckets,
      });
      toast({
        title: 'Failed to generate concept',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGeneratingConcept(false);
    }
  };

  const handleGenerateLyricsTopic = async () => {
    const flowId = draftFlowIdRef.current;
    const tag_buckets = tagsToBuckets(selectedTags);
    trackRandomizeLyricsClicked({
      auth_state: isAuthenticated ? 'spotify' : 'guest',
      has_style_input: songPrompt.trim().length > 0,
      flow_id: flowId,
      primary_tag_bucket: primaryTagBucket(selectedTags),
      tag_buckets,
    });
    const startTime = Date.now();
    setIsGeneratingLyricsTopic(true);
    try {
      const trimmedPrompt = songPrompt.trim();
      const traitOverrides = cachedStyleTraits || undefined;
      const bankSimilarities = cachedBankSimilarities || undefined;

      // Only show "Based on" if we actually used async routing signals for THIS prompt.
      const usedAsyncSignals =
        (traitOverrides && Object.keys(traitOverrides).length > 0) ||
        (bankSimilarities && Object.keys(bankSimilarities).length > 0);
      const asyncBasis =
        usedAsyncSignals && lastClassifiedPrompt.current === trimmedPrompt
          ? lastClassifiedPrompt.current
          : '';

      const result = await generateLyricsTopic({
        genres: selectedTags,
        style_prompt: trimmedPrompt || undefined,
        // Pass cached classifier results (if available)
        trait_overrides: traitOverrides,
        bank_similarities: bankSimilarities,
      });
      setLyricsAbout(result.topic);
      draftUsedRandomizeLyricsRef.current = true;
      // Capture debug info for dev panel
      setLyricsTopicDebug({
        debug: result.debug || null,
        bankId: result.bank_id,
        basedOn: asyncBasis,
      });
      trackRandomizeLyricsSucceeded({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        duration_ms: Date.now() - startTime,
        has_style_input: trimmedPrompt.length > 0,
        flow_id: flowId,
        primary_tag_bucket: primaryTagBucket(selectedTags),
        tag_buckets,
        bank_id: result.bank_id,
      });
    } catch (error) {
      trackRandomizeLyricsFailed({
        auth_state: isAuthenticated ? 'spotify' : 'guest',
        error_type: error instanceof Error ? error.name : 'unknown',
        flow_id: flowId,
        primary_tag_bucket: primaryTagBucket(selectedTags),
        tag_buckets,
      });
      toast({
        title: 'Failed to generate topic',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGeneratingLyricsTopic(false);
    }
  };

  const handleGenerate = async () => {
    if (!songPrompt.trim()) {
      toast({
        title: 'Missing style prompt',
        description: 'Please describe the style you want',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    const flowId = draftFlowIdRef.current;
    const tag_buckets = tagsToBuckets(selectedTags);
    const authState = isAuthenticated ? 'spotify' : 'guest';
    const hasLyricsInput = lyricsAbout.trim().length > 0;
    const hasStyleInput = songPrompt.trim().length > 0;
    const { instrumental_intended, instrumental_intent_signal } = getInstrumentalIntent();

    // Compute tag source counts
    let tags_recommended_count = 0;
    let tags_auto_picked_count = 0;
    for (const src of tagSources.values()) {
      if (src === 'recommended') tags_recommended_count++;
      else if (src === 'auto_picked') tags_auto_picked_count++;
    }

    // Track generate clicked
    trackGenerateClicked({
      auth_state: authState,
      has_lyrics_input: hasLyricsInput,
      has_style_input: hasStyleInput,
      personalize_enabled: personalize,
      instrumental_intended,
      instrumental_intent_signal,
      flow_id: flowId,
      used_randomize_style: draftUsedRandomizeStyleRef.current,
      used_randomize_lyrics: draftUsedRandomizeLyricsRef.current,
      primary_tag_bucket: primaryTagBucket(selectedTags),
      tag_buckets,
      tags_selected: selectedTags,
      tags_count: selectedTags.length,
      tags_recommended_count,
      tags_auto_picked_count,
    });

    const startTime = Date.now();

    // Lyrics are optional - empty means instrumental
    setIsLoading(true);
    try {
      // Build lyric controls
      const lyricControls: LyricControls = {};
      if (lyricAudience !== 'auto') lyricControls.audience = lyricAudience;
      if (lyricDirectness !== 'auto') lyricControls.directness = lyricDirectness;
      if (lyricHumor !== 'auto') lyricControls.humor = lyricHumor;
      if (lyricExplicitness !== 'auto') lyricControls.explicitness = lyricExplicitness;
      if (lyricPersona !== 'auto') lyricControls.persona = lyricPersona;
      if (lyricPOV !== 'auto') lyricControls.pov = lyricPOV;
      const hasLyricControls = Object.keys(lyricControls).length > 0;

      const isTwoStep = selectedVariant && TWO_STEP_VARIANTS.includes(selectedVariant as PromptVariant);

      // Common fields shared by both split endpoints
      const commonFields = {
        user_prompt: songPrompt.trim(),
        lyrics_about: lyricsAbout.trim(),
        tags: selectedTags.length > 0 ? selectedTags.slice(0, 25) : undefined,
        prompt_variant: selectedVariant || undefined,
      };

      let result: AdvancedGenerateResponse;

      if (isTwoStep) {
        // Split flow: call style + lyrics in parallel, then save
        const styleRequest: GenerateStyleRequest = {
          ...commonFields,
          style_model: selectedStyleModel || undefined,
        };

        // Detect instrumental (mirror backend logic)
        const lyricsText = lyricsAbout.trim().toLowerCase();
        const instrumentalPhrases = ['instrumental', 'no lyrics', 'no vocal', 'no vocals', 'without lyrics', 'without vocals'];
        const isInstrumentalRequest = !lyricsText
          || instrumentalPhrases.some(p => lyricsText.includes(p))
          || selectedTags.some(t => t.trim().toLowerCase() === 'instrumental');

        if (isInstrumentalRequest) {
          // Instrumental: only call style endpoint
          const styleResult = await generateStyleSplit(styleRequest);
          const saveResult = await saveGenerationResult({
            suno_prompt: styleResult.suno_prompt,
            exclude: styleResult.exclude,
            weirdness: styleResult.weirdness,
            style_influence: styleResult.style_influence,
            auto_tags: styleResult.auto_tags,
            style_name: styleResult.style_name,
            song_title: styleResult.instrumental_title || '',
            lyrics: '',
          });
          result = {
            concept_title: styleResult.instrumental_title || styleResult.style_name || 'Untitled',
            lyrics: '',
            suno_prompt: styleResult.suno_prompt,
            exclude: styleResult.exclude,
            weirdness: styleResult.weirdness,
            style_influence: styleResult.style_influence,
            generation_id: saveResult.generation_id,
            prompt_id: saveResult.prompt_id,
            is_favorite: saveResult.is_favorite,
            auto_tags: styleResult.auto_tags,
          };
        } else {
          // Standard: call both in parallel
          const lyricsRequest: GenerateLyricsRequest = {
            ...commonFields,
            lyrics_model: selectedLyricsModel || undefined,
            lyric_controls: hasLyricControls ? lyricControls : undefined,
          };

          const [styleResult, lyricsResult] = await Promise.all([
            generateStyleSplit(styleRequest),
            generateLyricsSplit(lyricsRequest),
          ]);

          const saveResult = await saveGenerationResult({
            suno_prompt: styleResult.suno_prompt,
            exclude: styleResult.exclude,
            weirdness: styleResult.weirdness,
            style_influence: styleResult.style_influence,
            auto_tags: styleResult.auto_tags,
            style_name: styleResult.style_name,
            song_title: lyricsResult.song_title,
            lyrics: lyricsResult.lyrics,
          });

          result = {
            concept_title: lyricsResult.song_title,
            lyrics: lyricsResult.lyrics,
            suno_prompt: styleResult.suno_prompt,
            exclude: styleResult.exclude,
            weirdness: styleResult.weirdness,
            style_influence: styleResult.style_influence,
            generation_id: saveResult.generation_id,
            prompt_id: saveResult.prompt_id,
            is_favorite: saveResult.is_favorite,
            auto_tags: styleResult.auto_tags,
          };
        }
      } else {
        // Single-step: use the original monolithic endpoint
        const request: AdvancedGenerateRequest = {
          ...commonFields,
          model: selectedModel || undefined,
          lyric_controls: hasLyricControls ? lyricControls : undefined,
        };
        result = await generateAdvanced(request);
      }

      // Track success
      trackGenerateSucceeded({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        has_lyrics: !!result.lyrics,
        instrumental_intended,
        instrumental_intent_signal,
        flow_id: flowId,
        used_randomize_style: draftUsedRandomizeStyleRef.current,
        used_randomize_lyrics: draftUsedRandomizeLyricsRef.current,
        primary_tag_bucket: primaryTagBucket(selectedTags),
        tag_buckets,
        tags_selected: selectedTags,
        tags_count: selectedTags.length,
        tags_recommended_count,
        tags_auto_picked_count,
      });

      onGenerate(result, { flow_id: flowId });
      // Next draft should start a new flow id.
      draftFlowIdRef.current = createFlowId();
    } catch (error) {
      // Track failure
      trackGenerateFailed({
        auth_state: authState,
        duration_ms: Date.now() - startTime,
        error_type: error instanceof Error ? error.name : 'unknown',
        flow_id: flowId,
      });

      toast({
        title: 'Generation failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Keyboard shortcut: Cmd/Ctrl + Enter to generate (ChatGPT-like)
  // Must NOT have altKey or shiftKey (those are used for other shortcuts like New Song)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const isMetaOrCtrl = e.metaKey || e.ctrlKey;
      if (!isMetaOrCtrl) return;
      if (e.altKey || e.shiftKey) return; // Don't fire on ⌥⌘Enter or ⇧⌘Enter
      if (e.key !== 'Enter') return;
      if (isLoading) return;

      e.preventDefault();
      handleGenerate();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isLoading, songPrompt, lyricsAbout, selectedVariant, selectedModel, selectedStyleModel, selectedLyricsModel, selectedTags, lyricAudience, lyricDirectness, lyricHumor, lyricExplicitness, lyricPersona, lyricPOV]);

  // Get recommended tags based on personalize toggle
  // Recommended tags are stored in state so they don't reorder when a tag is added.

  return (
    <Box flex={1} overflow="auto" bg="gray.900" py={3} pt={14} px={4} minW={0} display="flex" alignItems="center" justifyContent="center">
      <Box maxW="560px" w="100%">
        <VStack spacing={0} align="stretch">
          
          {/* View title */}
          <Text fontSize="xl" fontWeight="semibold" mb={4}>
            New Song
          </Text>

          {/* ═══════════════════════════════════════════════════════════════
              STYLES SECTION (collapsible)
              ═══════════════════════════════════════════════════════════════ */}
          <Box
            borderWidth="1px"
            borderColor="gray.700"
            borderRadius="lg"
            overflow="hidden"
            mb={3}
          >
            {/* Section header */}
            <HStack
              px={4}
              py={3}
              cursor="pointer"
              onClick={() => setStylesExpanded(!stylesExpanded)}
              justify="space-between"
            >
              <HStack spacing={2}>
                {stylesExpanded ? <ChevronDownIcon /> : <ChevronRightIcon />}
                <Text fontWeight="medium">Styles</Text>
              </HStack>
              {stylesExpanded && (
                <HStack spacing={1}>
                  <Tooltip 
                    label="Personalize with Spotify" 
                    placement="top" 
                    hasArrow
                    bg="gray.700"
                    color="white"
                    fontSize="xs"
                    px={2}
                    py={1}
                    borderRadius="md"
                  >
                    <IconButton
                      aria-label="Personalize with Spotify taste"
                      icon={<LuUser size={14} />}
                      size="xs"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        const newValue = !personalize;
                        setPersonalize(newValue);
                        trackPersonalizeToggled({
                          auth_state: isAuthenticated ? 'spotify' : 'guest',
                          is_enabled: newValue,
                        });
                      }}
                      color={personalize ? 'purple.400' : 'gray.500'}
                      _hover={{ color: personalize ? 'purple.300' : 'gray.300' }}
                      isDisabled={!isAuthenticated}
                    />
                  </Tooltip>
                  <IconButton
                    aria-label="Surprise me"
                    icon={<LuDices size={14} />}
                    size="xs"
                    variant="ghost"
                    isLoading={isGeneratingConcept}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleGenerateConcept();
                    }}
                    color="gray.400"
                    _hover={{ color: 'white' }}
                  />
                </HStack>
              )}
            </HStack>

            {/* Section content */}
            <Collapse in={stylesExpanded} animateOpacity>
              <Box px={4} pb={4}>
                {/* Style prompt text area */}
                <AutoGrowTextarea
                  placeholder="Describe the style or sound you want..."
                  value={songPrompt}
                  maxLength={MAX_STYLE_PROMPT_LEN}
                  onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setSongPrompt(e.target.value)}
                  minRows={2}
                  maxRows={4}
                  bg="transparent"
                  border="none"
                  _focus={{ boxShadow: 'none' }}
                  p={0}
                  fontSize="sm"
                  mb={3}
                />

                {/* Selected tags + Auto-picked tags (from Surprise me) */}
                {(() => {
                  // Filter auto-picked: exclude tags now in selectedTags, hide all if at max
                  const selectedLower = selectedTags.map(t => t.toLowerCase());
                  const visibleAutoTags = selectedTags.length >= MAX_TAGS 
                    ? [] 
                    : lastAutoPickedTags.filter(t => !selectedLower.includes(t.toLowerCase()));
                  
                  return (selectedTags.length > 0 || visibleAutoTags.length > 0) && (
                    <Box overflowX="auto" pb={2}>
                      <HStack spacing={2} minW="max-content">
                        {/* User-selected tags (purple, solid) */}
                        {selectedTags.map((tag) => (
                          <Tag
                            key={`selected-${tag}`}
                            size="md"
                            borderRadius="full"
                            variant="solid"
                            colorScheme="purple"
                          >
                            <TagLabel>{tag}</TagLabel>
                            <TagCloseButton onClick={() => removeTag(tag)} />
                          </Tag>
                        ))}
                        {/* Auto-picked tags (subtle, with + to add) - only if room */}
                        {visibleAutoTags.map((tag) => (
                          <Tag
                            key={`auto-${tag}`}
                            size="md"
                            borderRadius="full"
                            variant="outline"
                            colorScheme="blue"
                            opacity={0.7}
                            cursor="pointer"
                            _hover={{ opacity: 1, bg: 'whiteAlpha.100' }}
                            onClick={() => promoteAutoTag(tag)}
                          >
                            <AddIcon boxSize={2} mr={1} />
                            <TagLabel>{tag}</TagLabel>
                          </Tag>
                        ))}
                      </HStack>
                    </Box>
                  );
                })()}

                {/* Recommended tags (Suno-like) - hide when at max */}
                {selectedTags.length < MAX_TAGS ? (
                  <Box overflowX="auto" pb={2}>
                    <HStack spacing={2} minW="max-content">
                      {recommendedTags.map((tag) => (
                        <Tag
                          key={tag}
                          size="md"
                          borderRadius="full"
                          variant="outline"
                          colorScheme="gray"
                          cursor="pointer"
                          _hover={{ bg: 'whiteAlpha.100' }}
                          onClick={() => addTag(tag)}
                        >
                          <AddIcon boxSize={2} mr={1} />
                          <TagLabel>{tag}</TagLabel>
                        </Tag>
                      ))}
                    </HStack>
                  </Box>
                ) : (
                  <Text fontSize="xs" color="gray.500" pb={2}>
                    Max 5 tags
                  </Text>
                )}
              </Box>
            </Collapse>
          </Box>

          {/* ═══════════════════════════════════════════════════════════════
              LYRICS SECTION (collapsible)
              ═══════════════════════════════════════════════════════════════ */}
          <Box
            borderWidth="1px"
            borderColor="gray.700"
            borderRadius="lg"
            overflow="hidden"
            mb={3}
          >
            {/* Section header */}
            <HStack
              px={4}
              py={3}
              cursor="pointer"
              onClick={() => setLyricsExpanded(!lyricsExpanded)}
              justify="space-between"
            >
              <HStack spacing={2}>
                {lyricsExpanded ? <ChevronDownIcon /> : <ChevronRightIcon />}
                <Text fontWeight="medium">Lyrics</Text>
              </HStack>
              {lyricsExpanded && (
                <IconButton
                  aria-label="Surprise me"
                  icon={<LuDices size={14} />}
                  size="xs"
                  variant="ghost"
                  isLoading={isGeneratingLyricsTopic}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleGenerateLyricsTopic();
                  }}
                  color="gray.400"
                  _hover={{ color: 'white' }}
                />
              )}
            </HStack>

            {/* Section content */}
            <Collapse in={lyricsExpanded} animateOpacity>
              <VStack spacing={3} px={4} pb={4} align="stretch">
                <AutoGrowTextarea
                  placeholder="Write some lyrics or a prompt — or leave blank for instrumental"
                  value={lyricsAbout}
                  maxLength={MAX_LYRICS_ABOUT_LEN}
                  onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setLyricsAbout(e.target.value)}
                  minRows={2}
                  maxRows={6}
                  bg="transparent"
                  border="none"
                  _focus={{ boxShadow: 'none' }}
                  p={0}
                  fontSize="sm"
                />

                {/* Debug panel for lyrics topic (dev only) */}
                {lyricsTopicDebug && (
                  <LyricsTopicDebugPanel
                    debug={lyricsTopicDebug.debug}
                    bankId={lyricsTopicDebug.bankId}
                    topic={lyricsAbout}
                    basedOn={lyricsTopicDebug.basedOn}
                  />
                )}

                {/* Lyric controls (power user) - hidden by default */}
                {!isInstrumental && (
                  <Box>
                    <HStack
                      justify="space-between"
                      align="center"
                      cursor="pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        setLyricsControlsExpanded((v) => !v);
                      }}
                      py={1}
                    >
                      <HStack spacing={2}>
                        {lyricsControlsExpanded ? (
                          <ChevronDownIcon boxSize={4} color="gray.500" />
                        ) : (
                          <ChevronRightIcon boxSize={4} color="gray.500" />
                        )}
                        <Text fontSize="xs" color="gray.500">
                          Lyric controls
                        </Text>
                      </HStack>
                    </HStack>

                    <Collapse in={lyricsControlsExpanded} animateOpacity>
                      <VStack spacing={2} align="stretch" pt={2}>
                        <HStack justify="space-between" align="center">
                          <Text fontSize="sm" color="gray.300">
                            POV
                          </Text>
                          <HStack spacing={1}>
                            {(['auto', 'first', 'second', 'third'] as const).map((opt) => (
                              <Button
                                key={opt}
                                size="xs"
                                variant="ghost"
                                bg={lyricPOV === opt ? 'whiteAlpha.200' : 'transparent'}
                                _hover={{ bg: 'whiteAlpha.150' }}
                                color={lyricPOV === opt ? 'white' : 'gray.400'}
                                fontWeight={lyricPOV === opt ? 'medium' : 'normal'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setLyricPOV(opt);
                                }}
                                px={2}
                                h={6}
                              >
                                {opt === 'auto' ? 'Auto' : opt === 'first' ? '1st' : opt === 'second' ? '2nd' : '3rd'}
                              </Button>
                            ))}
                          </HStack>
                        </HStack>

                        <HStack justify="space-between" align="center">
                          <Text fontSize="sm" color="gray.300">
                            Directness
                          </Text>
                          <HStack spacing={1}>
                            {(['auto', 'direct', 'balanced', 'metaphor_heavy'] as const).map((opt) => (
                              <Button
                                key={opt}
                                size="xs"
                                variant="ghost"
                                bg={lyricDirectness === opt ? 'whiteAlpha.200' : 'transparent'}
                                _hover={{ bg: 'whiteAlpha.150' }}
                                color={lyricDirectness === opt ? 'white' : 'gray.400'}
                                fontWeight={lyricDirectness === opt ? 'medium' : 'normal'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setLyricDirectness(opt);
                                }}
                                px={2}
                                h={6}
                              >
                                {opt === 'auto' ? 'Auto' : opt === 'metaphor_heavy' ? 'Metaphorical' : opt.charAt(0).toUpperCase() + opt.slice(1)}
                              </Button>
                            ))}
                          </HStack>
                        </HStack>

                        <HStack justify="space-between" align="center">
                          <Text fontSize="sm" color="gray.300">
                            Explicitness
                          </Text>
                          <HStack spacing={1}>
                            {(['auto', 'clean', 'innuendo', 'explicit'] as const).map((opt) => (
                              <Button
                                key={opt}
                                size="xs"
                                variant="ghost"
                                bg={lyricExplicitness === opt ? 'whiteAlpha.200' : 'transparent'}
                                _hover={{ bg: 'whiteAlpha.150' }}
                                color={lyricExplicitness === opt ? 'white' : 'gray.400'}
                                fontWeight={lyricExplicitness === opt ? 'medium' : 'normal'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setLyricExplicitness(opt);
                                }}
                                px={2}
                                h={6}
                              >
                                {opt === 'auto' ? 'Auto' : opt === 'innuendo' ? 'Suggestive' : opt.charAt(0).toUpperCase() + opt.slice(1)}
                              </Button>
                            ))}
                          </HStack>
                        </HStack>

                        <HStack justify="space-between" align="center">
                          <Text fontSize="sm" color="gray.300">
                            Humor
                          </Text>
                          <HStack spacing={1}>
                            {(['auto', 'none', 'light', 'comedic'] as const).map((opt) => (
                              <Button
                                key={opt}
                                size="xs"
                                variant="ghost"
                                bg={lyricHumor === opt ? 'whiteAlpha.200' : 'transparent'}
                                _hover={{ bg: 'whiteAlpha.150' }}
                                color={lyricHumor === opt ? 'white' : 'gray.400'}
                                fontWeight={lyricHumor === opt ? 'medium' : 'normal'}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setLyricHumor(opt);
                                }}
                                px={2}
                                h={6}
                              >
                                {opt === 'auto' ? 'Auto' : opt.charAt(0).toUpperCase() + opt.slice(1)}
                              </Button>
                            ))}
                          </HStack>
                        </HStack>
                      </VStack>
                    </Collapse>
                  </Box>
                )}
              </VStack>
            </Collapse>
          </Box>

          {/* ═══════════════════════════════════════════════════════════════
              CREATE BUTTON (always at very bottom)
              ═══════════════════════════════════════════════════════════════ */}
          <Button
            colorScheme="gray"
            bg="gray.800"
            _hover={{ bg: 'gray.700' }}
            size="lg"
            w="100%"
            onClick={handleGenerate}
            isLoading={isLoading}
            loadingText="Creating..."
            leftIcon={<LuMusic size={18} />}
          >
            Create
          </Button>

          {/* Keyboard shortcut hint */}
          <Text fontSize="xs" color="gray.600" textAlign="center" mt={2}>
            {isLoading && showLongWaitMessage
              ? 'Generations can take up to a minute...'
              : '⌘ Enter to create'}
          </Text>
        </VStack>
      </Box>
    </Box>
  );
}

