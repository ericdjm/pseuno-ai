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
  generateInputConcept,
  generateLyricsTopic,
  getPromptVariants,
  getModels,
  getProfile,
  AdvancedGenerateRequest,
  AdvancedGenerateResponse,
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
} from '../api';
import { useSessionStorageState } from '../hooks';

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
  onGenerate: (result: AdvancedGenerateResponse) => void;
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

  // Reset inputs when resetKey changes (e.g., user clicks "New Song")
  useEffect(() => {
    if (resetKey !== undefined && resetKey > 0) {
      setSongPrompt('');
      setLyricsAbout('');
    }
  }, [resetKey, setSongPrompt, setLyricsAbout]);

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
    }, 10000);
    return () => clearTimeout(timer);
  }, [isLoading]);
  
  // Suno-like collapsible sections
  const [stylesExpanded, setStylesExpanded] = useState(true);
  const [lyricsExpanded, setLyricsExpanded] = useState(false);
  
  // Style tags (selected tags stored as array)
  const [selectedTags, setSelectedTags] = useSessionStorageState<string[]>('draft:selectedTags', []);
  
  // Auto-picked tags from last "Surprise me" (shown as subtle chips)
  const [lastAutoPickedTags, setLastAutoPickedTags] = useState<string[]>([]);
  
  // Max tags constant
  const MAX_TAGS = 5;
  
  // Personalize toggle for tag recommendations
  const [personalize, setPersonalize] = useState(false);

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

  useEffect(() => {
    if (!personalize || !isAuthenticated) return;

    let cancelled = false;
    const ranges: TimeRange[] = ['short_term', 'medium_term', 'long_term'];

    (async () => {
      try {
        const missing = ranges.filter((r) => !spotifyProfilesByRange[r]);
        if (missing.length === 0) return;

        const results = await Promise.allSettled(missing.map((r) => getProfile(r)));
        if (cancelled) return;

        const next: Partial<Record<TimeRange, SpotifyProfileResponse>> = { ...spotifyProfilesByRange };
        results.forEach((res, idx) => {
          if (res.status === 'fulfilled') {
            const r = missing[idx];
            next[r] = res.value;
          }
        });
        setSpotifyProfilesByRange(next);
      } catch {
        // Non-fatal: personalization still works with whatever profile we have.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [personalize, isAuthenticated, spotifyProfilesByRange]);
  
  // Base genre/concept recommendations (curated list)
  const BASE_RECOMMENDATIONS = [
    'indie rock', 'electronic', 'synth-pop', 'dreamy', 'lo-fi', 
    'acoustic', 'ambient', 'jazzy', 'upbeat', 'melancholic',
    'funk', 'r&b', 'hip-hop', 'folk', 'cinematic'
  ];
  
  // Compute recommended tags (base + taste if personalized).
  // This is only recomputed when we reshuffle; adding/removing tags should not reorder the remaining suggestions.
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

    const shuffleWithSeed = <T,>(arr: T[], seed: number): T[] => {
      const rng = mulberry32(seed);
      const copy = [...arr];
      for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
      }
      return copy;
    };

    let recommendations: string[] = [...BASE_RECOMMENDATIONS];
    
    if (personalize && isAuthenticated) {
      // Merge multiple time ranges for a richer pool:
      // short_term (~4w), medium_term (~6m), long_term (years)
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
        tasteArtists.push(...p.top_artists.slice(0, 20).map((a) => a.name)); // preserve casing
        artistGenres.push(...p.top_artists.flatMap((a) => a.genres || []).slice(0, 50));
      }

      recommendations = [
        ...tasteGenres,
        ...artistGenres,
        ...tasteMoods,
        ...tasteArtists,
        ...recommendations,
      ];
    }
    
    // Dedupe case-insensitively but preserve original display casing (important for artist names)
    const uniqueByLower = new Map<string, string>();
    for (const raw of recommendations) {
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const key = trimmed.toLowerCase();
      if (!uniqueByLower.has(key)) uniqueByLower.set(key, trimmed);
    }

    const selectedLower = new Set(selectedTags.map((s) => s.toLowerCase()));
    const available = Array.from(uniqueByLower.entries())
      .filter(([key]) => !selectedLower.has(key))
      .map(([, value]) => value)
      // Avoid showing already-auto-picked tags as "recommended" immediately after Surprise Me
      .filter((t) => !lastAutoPickedTags.some((a) => a.toLowerCase() === t.toLowerCase()));

    // Shuffle to introduce a bit of variance, then take the top N
    return shuffleWithSeed(available, seed).slice(0, 32);
  };

  // Recompute recommendations only on reshuffle events (seed changes).
  useEffect(() => {
    setRecommendedTags(computeRecommendedTags(recommendedTagsSeed));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommendedTagsSeed]);
  
  const addTag = (tag: string) => {
    // Preserve casing for display (e.g., Spotify artist names), but dedupe case-insensitively
    const trimmed = tag.trim();
    if (!trimmed) return;
    const exists = selectedTags.some((t) => t.toLowerCase() === trimmed.toLowerCase());
    if (!exists) {
      setSelectedTags([...selectedTags, trimmed]);
    }
    // Remove from suggestions without reshuffling
    setRecommendedTags((prev) => prev.filter((t) => t.toLowerCase() !== trimmed.toLowerCase()));
  };
  
  const removeTag = (tagToRemove: string) => {
    setSelectedTags(selectedTags.filter((t) => t.toLowerCase() !== tagToRemove.toLowerCase()));
  };
  
  // Promote an auto-picked tag to selected
  const promoteAutoTag = (tag: string) => {
    if (selectedTags.length >= MAX_TAGS) return; // Already at max
    addTag(tag);
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

  // Load variants and models on mount
  useEffect(() => {
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

  const handleGenerateConcept = async () => {
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
          ...BASE_RECOMMENDATIONS,
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
    } catch (error) {
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
    setIsGeneratingLyricsTopic(true);
    try {
      const result = await generateLyricsTopic({
        genres: selectedTags,
        style_prompt: songPrompt.trim() || undefined,
      });
      setLyricsAbout(result.topic);
    } catch (error) {
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

      const request: AdvancedGenerateRequest = {
        user_prompt: songPrompt.trim(),
        lyrics_about: lyricsAbout.trim(),
        tags: selectedTags.length > 0 ? selectedTags.slice(0, 25) : undefined,
        prompt_variant: selectedVariant || undefined,
        model: isTwoStep ? undefined : (selectedModel || undefined),
        style_model: isTwoStep ? (selectedStyleModel || undefined) : undefined,
        lyrics_model: isTwoStep ? (selectedLyricsModel || undefined) : undefined,
        lyric_controls: hasLyricControls ? lyricControls : undefined,
      };

      const result = await generateAdvanced(request);
      onGenerate(result);

      toast({
        title: 'Song generated!',
        description: result.concept_title,
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
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
                        setPersonalize(!personalize);
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

