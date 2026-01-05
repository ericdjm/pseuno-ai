import {
  Box,
  Button,
  ButtonGroup,
  VStack,
  HStack,
  Text,
  Input,
  Textarea,
  FormControl,
  FormLabel,
  Badge,
  Wrap,
  WrapItem,
  useToast,
  Collapse,
  Select,
  Tooltip,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Portal,
  Switch,
  IconButton,
} from '@chakra-ui/react';
import { ChevronDownIcon, StarIcon } from '@chakra-ui/icons';
import { useState, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import {
  generateAdvanced,
  generateLyricsOnly,
  generateInputConcept,
  generateLyricsTopic,
  getPromptVariants,
  getModels,
  updateSavedPrompt,
  AdvancedGenerateRequest,
  SpotifyProfileResponse,
  SavedSunoPrompt,
  PromptVariantInfo,
  PromptVariant,
  ModelInfo,
  LyricControls,
  LyricAudience,
  LyricDirectness,
  LyricHumor,
  LyricExplicitness,
  LyricPersona,
  LyricLinesPerSection,
  LyricLineLength,
  LyricPOV,
  LyricRhymeScheme,
} from '../api';

type StyleMode = 'songStylePrompt' | 'pastSunoPrompts' | 'favorites';

// Two-step variants that support instrumental mode (can skip lyrics branch)
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

interface AdvancedGenerationControlsProps {
  onGenerate: (result: any) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  profile?: SpotifyProfileResponse | null;
  savedPrompts: SavedSunoPrompt[];
  selectedSavedPrompt: SavedSunoPrompt | null;
  onSelectSavedPrompt: (prompt: SavedSunoPrompt | null) => void;
  styleMode: StyleMode;
  onStyleModeChange: (mode: StyleMode) => void;
  onPromptUpdated?: () => void;
}

export default function AdvancedGenerationControls({
  onGenerate,
  isLoading,
  setIsLoading,
  profile,
  savedPrompts,
  selectedSavedPrompt,
  onSelectSavedPrompt,
  styleMode,
  onStyleModeChange,
  onPromptUpdated,
}: AdvancedGenerationControlsProps) {
  const toast = useToast();

  // State for favorite toggle
  const [togglingFavoriteId, setTogglingFavoriteId] = useState<number | null>(null);

  // State for inline title editing
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [editingTitleValue, setEditingTitleValue] = useState('');

  const handleTitleDoubleClick = (e: React.MouseEvent, prompt: SavedSunoPrompt) => {
    e.stopPropagation();
    setEditingTitleId(prompt.id);
    setEditingTitleValue(prompt.title || '');
  };

  const handleTitleSave = async (promptId: number) => {
    const trimmedTitle = editingTitleValue.trim();
    if (!trimmedTitle) {
      // Don't save empty titles
      setEditingTitleId(null);
      return;
    }
    try {
      await updateSavedPrompt(promptId, { title: trimmedTitle });
      toast({
        title: 'Title updated',
        status: 'success',
        duration: 2000,
      });
      onPromptUpdated?.();
    } catch (err) {
      toast({
        title: 'Failed to update title',
        status: 'error',
        duration: 3000,
      });
    }
    setEditingTitleId(null);
  };

  const handleTitleKeyDown = (e: React.KeyboardEvent, promptId: number) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleTitleSave(promptId);
    } else if (e.key === 'Escape') {
      setEditingTitleId(null);
    }
  };

  const handleToggleFavorite = async (e: React.MouseEvent, prompt: SavedSunoPrompt) => {
    e.stopPropagation(); // Don't select the prompt when clicking the star
    setTogglingFavoriteId(prompt.id);
    try {
      const newFavoriteState = !prompt.is_favorite;
      await updateSavedPrompt(prompt.id, { is_favorite: newFavoriteState });
      toast({
        title: newFavoriteState ? 'Added to favorites' : 'Removed from favorites',
        status: 'success',
        duration: 2000,
      });
      onPromptUpdated?.();
    } catch (err) {
      toast({
        title: 'Failed to update',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setTogglingFavoriteId(null);
    }
  };

  const MAX_STYLE_PROMPT_LEN = 500;
  const MAX_LYRICS_ABOUT_LEN = 500;
  const MAX_ARTISTS_INPUT_LEN = 300;
  const MAX_TAGS_INPUT_LEN = 300;
  const MAX_ARTISTS_COUNT = 20;
  const MAX_TAGS_COUNT = 25;
  const MAX_ARTIST_NAME_LEN = 60;
  const MAX_TAG_LEN = 40;
  const MAX_GENRES_INPUT_LEN = 300;
  const MAX_GENRE_LEN = 40;
  const MAX_GENRES_COUNT = 20;

  const [artistInput, setArtistInput] = useState('');
  const [genreInput, setGenreInput] = useState('');
  const [songPrompt, setSongPrompt] = useState('');
  const [lyricsAbout, setLyricsAbout] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [isInstrumental, setIsInstrumental] = useState(false);

  // Input concept generation state
  const [isGeneratingConcept, setIsGeneratingConcept] = useState(false);

  // Lyrics topic generation state
  const [isGeneratingLyricsTopic, setIsGeneratingLyricsTopic] = useState(false);

  // Prompt variant and model selection state
  const [promptVariants, setPromptVariants] = useState<PromptVariantInfo[]>([]);
  const [selectedVariant, setSelectedVariant] = useState<PromptVariant | ''>('');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedStyleModel, setSelectedStyleModel] = useState<string>('');
  const [selectedLyricsModel, setSelectedLyricsModel] = useState<string>('');

  // Lyric controls state
  const [showLyricControls, setShowLyricControls] = useState(false);
  const [lyricAudience, setLyricAudience] = useState<LyricAudience>('auto');
  const [lyricDirectness, setLyricDirectness] = useState<LyricDirectness>('auto');
  const [lyricHumor, setLyricHumor] = useState<LyricHumor>('auto');
  const [lyricExplicitness, setLyricExplicitness] = useState<LyricExplicitness>('auto');
  const [lyricPersona, setLyricPersona] = useState<LyricPersona>('auto');
  const [lyricLinesPerSection, setLyricLinesPerSection] = useState<LyricLinesPerSection>('auto');
  const [lyricLineLength, setLyricLineLength] = useState<LyricLineLength>('auto');
  const [lyricPOV, setLyricPOV] = useState<LyricPOV>('auto');
  const [lyricRhymeScheme, setLyricRhymeScheme] = useState<LyricRhymeScheme>('auto');

  // Fetch available prompt variants and models on mount
  useEffect(() => {
    const fetchVariants = async () => {
      try {
        const response = await getPromptVariants();
        setPromptVariants(response.variants);
        const defaultVariant = response.variants.find((v: PromptVariantInfo) => v.is_default);
        if (defaultVariant) {
          setSelectedVariant(defaultVariant.id as PromptVariant);
        }
      } catch (error) {
        console.error('Failed to fetch prompt variants:', error);
      }
    };
    
    const fetchModels = async () => {
      try {
        const response = await getModels();
        setAvailableModels(response.models);
        setSelectedModel(response.default_model);
        setSelectedStyleModel(response.default_style_model);
        setSelectedLyricsModel(response.default_lyrics_model);
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }
    };
    
    fetchVariants();
    fetchModels();
  }, []);

  // Filter variants based on instrumental mode (hide v1/v2 when instrumental is on)
  const availableVariants = isInstrumental
    ? promptVariants.filter((v) => TWO_STEP_VARIANTS.includes(v.id as PromptVariant))
    : promptVariants;

  // Handle instrumental toggle - switch to two-step variant if needed
  const handleInstrumentalToggle = (checked: boolean) => {
    setIsInstrumental(checked);
    if (checked) {
      // If enabling instrumental with a single-step variant selected, switch to v5_hybrid
      if (selectedVariant && !TWO_STEP_VARIANTS.includes(selectedVariant as PromptVariant)) {
        setSelectedVariant('v5_hybrid');
      }
    }
  };

  const parseList = (value: string) =>
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

  const handleGenerate = async () => {
    // Validation based on modes
    if (styleMode === 'songStylePrompt' && !songPrompt.trim()) {
      toast({
        title: 'Missing input',
        description: 'Please fill the song style prompt',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    const isReusingSavedPrompt = styleMode === 'pastSunoPrompts' || styleMode === 'favorites';
    if (isReusingSavedPrompt && !selectedSavedPrompt) {
      toast({
        title: 'No prompt selected',
        description: 'Please select a prompt from the list',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    // Skip lyrics validation if instrumental mode is enabled
    if (!lyricsAbout.trim() && !isInstrumental) {
      toast({
        title: 'Missing input',
        description: 'Please fill the lyrics topic or enable Instrumental mode',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      if (isReusingSavedPrompt) {
        // Use lyrics-only generation + copy saved prompt
        const sunoPrompt = selectedSavedPrompt!.suno_prompt.slice(0, MAX_STYLE_PROMPT_LEN);

        if (isInstrumental) {
          // Instrumental mode: skip lyrics generation, return empty lyrics
          const result = {
            generation_id: `reuse-${Date.now()}`,
            concept_title: selectedSavedPrompt!.title || 'Instrumental',
            suno_prompt: sunoPrompt,
            lyrics: '',
            exclude: selectedSavedPrompt!.exclude,
            weirdness: selectedSavedPrompt!.weirdness,
            style_influence: selectedSavedPrompt!.style_influence,
            prompt_id: selectedSavedPrompt!.id,
            is_favorite: selectedSavedPrompt!.is_favorite,
            auto_tags: selectedSavedPrompt!.auto_tags,
          };

          onGenerate(result);

          toast({
            title: 'Instrumental prompt ready!',
            description: 'No lyrics generated for instrumental mode.',
            status: 'success',
            duration: 3000,
          });
        } else {
          // Generate lyrics using the saved prompt as style context
          const lyricsResult = await generateLyricsOnly({
            suno_prompt: sunoPrompt,
            lyrics_about: lyricsAbout.trim(),
          });

          // Build a result object that matches AdvancedGenerateResponse shape
          const result = {
            generation_id: `reuse-${Date.now()}`,
            concept_title: lyricsResult.song_title || selectedSavedPrompt!.title || 'Reused Prompt',
            suno_prompt: sunoPrompt,
            lyrics: lyricsResult.lyrics,
            exclude: selectedSavedPrompt!.exclude,
            weirdness: selectedSavedPrompt!.weirdness,
            style_influence: selectedSavedPrompt!.style_influence,
            prompt_id: selectedSavedPrompt!.id,
            is_favorite: selectedSavedPrompt!.is_favorite,
            auto_tags: selectedSavedPrompt!.auto_tags,
          };

          onGenerate(result);

          toast({
            title: 'Lyrics generated!',
            status: 'success',
            duration: 3000,
          });
        }
      } else {
        // Standard full generation
        const artists = parseList(artistInput)
          .map((a) => a.slice(0, MAX_ARTIST_NAME_LEN))
          .slice(0, MAX_ARTISTS_COUNT);
        const tags = parseList(tagsInput)
          .map((t) => t.slice(0, MAX_TAG_LEN))
          .slice(0, MAX_TAGS_COUNT);

        // Build lyric controls if any non-auto values are set
        const lyricControls: LyricControls = {};
        if (lyricAudience !== 'auto') lyricControls.audience = lyricAudience;
        if (lyricDirectness !== 'auto') lyricControls.directness = lyricDirectness;
        if (lyricHumor !== 'auto') lyricControls.humor = lyricHumor;
        if (lyricExplicitness !== 'auto') lyricControls.explicitness = lyricExplicitness;
        if (lyricPersona !== 'auto') lyricControls.persona = lyricPersona;
        if (lyricLinesPerSection !== 'auto') lyricControls.lines_per_section = lyricLinesPerSection;
        if (lyricLineLength !== 'auto') lyricControls.line_length = lyricLineLength;
        if (lyricPOV !== 'auto') lyricControls.pov = lyricPOV;
        if (lyricRhymeScheme !== 'auto') lyricControls.rhyme_scheme = lyricRhymeScheme;
        const hasLyricControls = Object.keys(lyricControls).length > 0;

        // Check if using a two-step variant
        const isTwoStep =
          selectedVariant && TWO_STEP_VARIANTS.includes(selectedVariant as PromptVariant);
        
        const request: AdvancedGenerateRequest = {
          user_prompt: songPrompt.trim(),
          // Send empty lyrics_about when instrumental mode is enabled
          lyrics_about: isInstrumental ? '' : lyricsAbout.trim(),
          selected_artists: artists.length > 0 ? artists : undefined,
          tags: tags.length > 0 ? tags : undefined,
          prompt_variant: selectedVariant || undefined,
          // For two-step variants, use separate style/lyrics models
          model: isTwoStep ? undefined : (selectedModel || undefined),
          style_model: isTwoStep ? (selectedStyleModel || undefined) : undefined,
          lyrics_model: isTwoStep ? (selectedLyricsModel || undefined) : undefined,
          lyric_controls: hasLyricControls ? lyricControls : undefined,
        };

        const result = await generateAdvanced(request);
        onGenerate(result);

        toast({
          title: 'Generation complete',
          description: `Created: ${result.concept_title}`,
          status: 'success',
          duration: 5000,
        });
      }
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

  const addArtist = (name: string) => {
    const safeName = name.slice(0, MAX_ARTIST_NAME_LEN);
    const current = parseList(artistInput)
      .map((a) => a.slice(0, MAX_ARTIST_NAME_LEN))
      .slice(0, MAX_ARTISTS_COUNT);
    if (
      !current.some((artist) => artist.toLowerCase() === safeName.toLowerCase()) &&
      current.length < MAX_ARTISTS_COUNT
    ) {
      const updated = [...current, safeName];
      setArtistInput(updated.join(', '));
    }
  };


  const getButtonLabel = () => {
    if (styleMode === 'pastSunoPrompts' || styleMode === 'favorites') {
      return isInstrumental ? 'Use Prompt (Instrumental)' : 'Generate Lyrics';
    }
    return isInstrumental ? 'Generate Instrumental' : 'Generate Song';
  };

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        {/* Genre Influence - only show for Song Style Prompt mode */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
          <FormControl>
            <FormLabel>Genre Influence (Optional)</FormLabel>
            <Input
              placeholder="Comma-separated genres (e.g., indie rock, electronic, trip-hop)"
              value={genreInput}
              maxLength={MAX_GENRES_INPUT_LEN}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setGenreInput(e.target.value.slice(0, MAX_GENRES_INPUT_LEN))
              }
            />
            {genreInput.trim() ? (
              <Wrap mt={2}>
                {parseList(genreInput)
                  .map((g) => g.slice(0, MAX_GENRE_LEN))
                  .slice(0, MAX_GENRES_COUNT)
                  .map((genre) => (
                    <WrapItem key={genre}>
                      <Badge colorScheme="purple">{genre}</Badge>
                    </WrapItem>
                  ))}
              </Wrap>
            ) : null}
            <Text fontSize="xs" color="gray.500" mt={2}>
              Leave empty to use random genres. 1-3 will be selected.
            </Text>
          </FormControl>
        </Collapse>

        {/* Artist Influence - only show for Song Style Prompt mode */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
          <FormControl>
            <FormLabel>Artist Influence (Optional)</FormLabel>
            <Input
              placeholder="Comma-separated artist references"
              value={artistInput}
              maxLength={MAX_ARTISTS_INPUT_LEN}
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setArtistInput(e.target.value.slice(0, MAX_ARTISTS_INPUT_LEN))
            }
            />
            {artistInput.trim() ? (
              <Wrap mt={2}>
                {parseList(artistInput)
                  .map((a) => a.slice(0, MAX_ARTIST_NAME_LEN))
                  .slice(0, MAX_ARTISTS_COUNT)
                  .map((artist) => (
                    <WrapItem key={artist}>
                      <Badge colorScheme="green">{artist}</Badge>
                    </WrapItem>
                  ))}
              </Wrap>
            ) : null}
            {profile?.top_artists?.length ? (
              <>
                <Text fontSize="sm" color="gray.500" mt={3}>
                  Quick pick from your top artists
                </Text>
                <Wrap mt={1}>
                  {profile.top_artists.slice(0, 10).map((artist) => (
                    <WrapItem key={`artist-${artist.name}`}>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => addArtist(artist.name)}
                      >
                        {artist.name.slice(0, MAX_ARTIST_NAME_LEN)}
                      </Button>
                    </WrapItem>
                  ))}
                </Wrap>
              </>
            ) : null}
          </FormControl>
        </Collapse>

        {/* Style Mode Toggle */}
        <FormControl>
          <FormLabel>Style Source</FormLabel>
          <ButtonGroup size="sm" isAttached variant="outline" width="100%">
            <Button
              flex={1}
              colorScheme={styleMode === 'songStylePrompt' ? 'green' : 'gray'}
              variant={styleMode === 'songStylePrompt' ? 'solid' : 'outline'}
              onClick={() => {
                onStyleModeChange('songStylePrompt');
                onSelectSavedPrompt(null);
              }}
            >
              New Style
            </Button>
            <Button
              flex={1}
              colorScheme={styleMode === 'pastSunoPrompts' ? 'blue' : 'gray'}
              variant={styleMode === 'pastSunoPrompts' ? 'solid' : 'outline'}
              onClick={() => onStyleModeChange('pastSunoPrompts')}
            >
              Past Prompts
            </Button>
            <Button
              flex={1}
              colorScheme={styleMode === 'favorites' ? 'yellow' : 'gray'}
              variant={styleMode === 'favorites' ? 'solid' : 'outline'}
              onClick={() => onStyleModeChange('favorites')}
            >
              Favorites
            </Button>
          </ButtonGroup>
        </FormControl>

        {/* Song Style Prompt (editable) */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
          <FormControl isRequired>
            <HStack justify="space-between" align="center" mb={1}>
              <FormLabel mb={0}>Song Style Prompt</FormLabel>
              <HStack spacing={2}>
                <Button
                  size="xs"
                  colorScheme="purple"
                  variant="outline"
                  isLoading={isGeneratingConcept}
                  loadingText="Generating..."
                  onClick={async () => {
                  setIsGeneratingConcept(true);
                  try {
                    // Parse genres from input if available
                    const genreList = genreInput
                      .split(',')
                      .map(g => g.trim())
                      .filter(g => g.length > 0);
                    
                    // Parse artists for future use (passed through)
                    const artistList = artistInput
                      .split(',')
                      .map(a => a.trim())
                      .filter(a => a.length > 0);
                    
                    const result = await generateInputConcept({
                      genres: genreList,
                      artists: artistList,
                    });
                    
                    setSongPrompt(result.concept);
                    
                    // Show which genres were chosen
                    if (result.chosen_genres.length > 0) {
                      toast({
                        title: `Picked: ${result.chosen_genres.join(', ')}`,
                        description: 'Concept generated! Edit as needed.',
                        status: 'success',
                        duration: 3000,
                        isClosable: true,
                      });
                    } else {
                      toast({
                        title: 'Concept generated',
                        description: 'Using random style seed. Edit as needed.',
                        status: 'success',
                        duration: 3000,
                        isClosable: true,
                      });
                    }
                  } catch (error) {
                    toast({
                      title: 'Failed to generate concept',
                      description: error instanceof Error ? error.message : 'Unknown error',
                      status: 'error',
                      duration: 5000,
                      isClosable: true,
                    });
                  } finally {
                    setIsGeneratingConcept(false);
                  }
                }}
              >
                ✨ Generate for me
              </Button>
              </HStack>
            </HStack>
            <Textarea
              placeholder="Describe the style or sound you want"
              value={songPrompt}
              maxLength={MAX_STYLE_PROMPT_LEN}
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setSongPrompt(e.target.value.slice(0, MAX_STYLE_PROMPT_LEN))}
            />
            <HStack justify="space-between" mt={1}>
              <Text fontSize="xs" color="gray.500">
                Max {MAX_STYLE_PROMPT_LEN} characters
              </Text>
              <Text
                fontSize="xs"
                color={songPrompt.length >= MAX_STYLE_PROMPT_LEN ? 'orange.300' : 'gray.500'}
              >
                {songPrompt.length}/{MAX_STYLE_PROMPT_LEN}
              </Text>
            </HStack>
          </FormControl>
        </Collapse>

        {/* Prompt Selector for Past/Favorites modes */}
        <Collapse in={styleMode === 'pastSunoPrompts' || styleMode === 'favorites'} animateOpacity>
          <FormControl isRequired>
            <FormLabel>
              {styleMode === 'favorites' ? 'Select a Favorite' : 'Select a Past Prompt'}
            </FormLabel>
            {savedPrompts.length === 0 ? (
              <Box
                p={4}
                bg="gray.800"
                borderRadius="md"
                borderWidth="1px"
                borderColor="gray.600"
                textAlign="center"
              >
                <Text color="gray.500">
                  {styleMode === 'favorites' ? 'No favorites yet.' : 'No past prompts yet.'}
                </Text>
                <Text color="gray.600" fontSize="sm" mt={1}>
                  {styleMode === 'favorites'
                    ? 'Star a prompt to add it to your favorites.'
                    : 'Generate a prompt to see it here.'}
                </Text>
              </Box>
            ) : (
              <VStack spacing={2} align="stretch" maxH="300px" overflowY="auto">
                {savedPrompts.map((prompt) => (
                  <Box
                    key={prompt.id}
                    p={3}
                    bg="gray.800"
                    borderRadius="md"
                    borderWidth="2px"
                    borderColor={
                      selectedSavedPrompt?.id === prompt.id
                        ? styleMode === 'favorites' ? 'yellow.400' : 'blue.400'
                        : prompt.is_favorite ? 'yellow.700' : 'gray.600'
                    }
                    cursor="pointer"
                    onClick={() => onSelectSavedPrompt(prompt)}
                    _hover={{
                      borderColor:
                        selectedSavedPrompt?.id === prompt.id
                          ? styleMode === 'favorites' ? 'yellow.300' : 'blue.300'
                          : 'gray.500',
                    }}
                    transition="border-color 0.2s"
                  >
                    <HStack justify="space-between" align="start">
                      <VStack align="start" spacing={1}>
                        <HStack spacing={2}>
                          {editingTitleId === prompt.id ? (
                            <Input
                              size="sm"
                              value={editingTitleValue}
                              onChange={(e) => setEditingTitleValue(e.target.value.slice(0, 255))}
                              onBlur={() => handleTitleSave(prompt.id)}
                              onKeyDown={(e) => handleTitleKeyDown(e, prompt.id)}
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                              bg="gray.700"
                              width="200px"
                            />
                          ) : (
                            <Text
                              fontWeight="semibold"
                              fontSize="sm"
                              onDoubleClick={(e) => handleTitleDoubleClick(e, prompt)}
                              cursor="text"
                              title="Double-click to rename"
                              _hover={{ textDecoration: 'underline', textDecorationStyle: 'dotted' }}
                            >
                              {prompt.title || 'Untitled'}
                            </Text>
                          )}
                          {prompt.is_favorite && styleMode !== 'favorites' && (
                            <Badge colorScheme="yellow" fontSize="2xs">★</Badge>
                          )}
                        </HStack>
                        <HStack spacing={2} flexWrap="wrap">
                          <Badge colorScheme="blue" fontSize="xs">
                            Weirdness: {prompt.weirdness}%
                          </Badge>
                          <Badge colorScheme="purple" fontSize="xs">
                            Style: {prompt.style_influence}%
                          </Badge>
                        </HStack>
                        {/* Auto-tags */}
                        {prompt.auto_tags && prompt.auto_tags.length > 0 && (
                          <Wrap spacing={1}>
                            {prompt.auto_tags.slice(0, 4).map((tag, idx) => (
                              <WrapItem key={idx}>
                                <Badge colorScheme="teal" fontSize="2xs" variant="subtle">
                                  {tag}
                                </Badge>
                              </WrapItem>
                            ))}
                          </Wrap>
                        )}
                      </VStack>
                      <VStack spacing={1} align="end">
                        {selectedSavedPrompt?.id === prompt.id && (
                          <Badge colorScheme={styleMode === 'favorites' ? 'yellow' : 'blue'}>
                            Selected
                          </Badge>
                        )}
                        <IconButton
                          aria-label={prompt.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                          icon={<StarIcon />}
                          size="xs"
                          variant="ghost"
                          color={prompt.is_favorite ? 'yellow.400' : 'gray.500'}
                          onClick={(e) => handleToggleFavorite(e, prompt)}
                          isLoading={togglingFavoriteId === prompt.id}
                          _hover={{ color: prompt.is_favorite ? 'yellow.300' : 'yellow.400' }}
                        />
                      </VStack>
                    </HStack>
                    <Text
                      fontSize="xs"
                      color="gray.400"
                      mt={2}
                      noOfLines={2}
                      fontFamily="monospace"
                    >
                      {prompt.suno_prompt}
                    </Text>
                  </Box>
                ))}
              </VStack>
            )}
          </FormControl>
        </Collapse>

        {/* Instrumental Toggle */}
        <FormControl display="flex" alignItems="center">
          <Switch
            id="instrumental-toggle"
            isChecked={isInstrumental}
            onChange={(e) => handleInstrumentalToggle(e.target.checked)}
            colorScheme="purple"
            mr={3}
          />
          <FormLabel htmlFor="instrumental-toggle" mb="0" cursor="pointer">
            Instrumental (no lyrics)
          </FormLabel>
          {isInstrumental && (
            <Badge colorScheme="purple" ml={2}>
              Lyrics skipped
            </Badge>
          )}
        </FormControl>

        {/* Lyrics Topic - hidden when instrumental */}
        <Collapse in={!isInstrumental} animateOpacity>
          <FormControl isRequired>
            <HStack justify="space-between" align="center" mb={1}>
              <FormLabel mb={0}>Lyrics Topic</FormLabel>
              <Button
                size="xs"
                colorScheme="purple"
                variant="outline"
                isLoading={isGeneratingLyricsTopic}
                loadingText="Generating..."
                onClick={async () => {
                  setIsGeneratingLyricsTopic(true);
                  try {
                    // Parse genres from input if available
                    const genreList = genreInput
                      .split(',')
                      .map(g => g.trim())
                      .filter(g => g.length > 0);
                    
                    // Use the current song prompt as style context if available
                    const stylePromptContext = songPrompt.trim() || undefined;
                    
                    const result = await generateLyricsTopic({
                      genres: genreList,
                      style_prompt: stylePromptContext,
                    });
                    
                    setLyricsAbout(result.topic);
                    
                    // Show which moods influenced the topic
                    if (result.chosen_moods.length > 0) {
                      toast({
                        title: `Mood: ${result.chosen_moods.join(', ')}`,
                        description: 'Topic generated! Edit as needed.',
                        status: 'success',
                        duration: 3000,
                        isClosable: true,
                      });
                    } else {
                      toast({
                        title: 'Topic generated',
                        description: 'Using random mood seed. Edit as needed.',
                        status: 'success',
                        duration: 3000,
                        isClosable: true,
                      });
                    }
                  } catch (error) {
                    toast({
                      title: 'Failed to generate topic',
                      description: error instanceof Error ? error.message : 'Unknown error',
                      status: 'error',
                      duration: 5000,
                      isClosable: true,
                    });
                  } finally {
                    setIsGeneratingLyricsTopic(false);
                  }
                }}
              >
                ✨ Generate for me
              </Button>
            </HStack>
            <Input
              placeholder="What should the lyrics be about?"
              value={lyricsAbout}
              maxLength={MAX_LYRICS_ABOUT_LEN}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setLyricsAbout(e.target.value.slice(0, MAX_LYRICS_ABOUT_LEN))
              }
            />
            <HStack justify="space-between" mt={1}>
              <Text fontSize="xs" color="gray.500">
                Max {MAX_LYRICS_ABOUT_LEN} characters
              </Text>
              <Text
                fontSize="xs"
                color={lyricsAbout.length >= MAX_LYRICS_ABOUT_LEN ? 'orange.300' : 'gray.500'}
              >
                {lyricsAbout.length}/{MAX_LYRICS_ABOUT_LEN}
              </Text>
            </HStack>
          </FormControl>
        </Collapse>

        {/* Tags - only show for Song Style Prompt mode */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
          <FormControl>
            <FormLabel>Tags (Optional)</FormLabel>
            <Input
              placeholder="Comma-separated tags (e.g., dubstep, airy, 90s)"
              value={tagsInput}
              maxLength={MAX_TAGS_INPUT_LEN}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setTagsInput(e.target.value.slice(0, MAX_TAGS_INPUT_LEN))}
            />
          </FormControl>
        </Collapse>

        {/* Lyric Style Controls - collapsible, hidden when instrumental */}
        <Collapse in={styleMode === 'songStylePrompt' && !isInstrumental} animateOpacity>
          <Box>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowLyricControls(!showLyricControls)}
              mb={2}
              leftIcon={<Text fontSize="xs">{showLyricControls ? '▼' : '▶'}</Text>}
              color="gray.400"
              fontWeight="normal"
              _hover={{ color: 'gray.200' }}
            >
              Lyrics Style (Optional)
            </Button>
            <Collapse in={showLyricControls} animateOpacity>
              <VStack spacing={3} align="stretch" pl={2} borderLeft="2px solid" borderColor="gray.700">
                <HStack spacing={4} flexWrap="wrap">
                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Audience</FormLabel>
                    <Select
                      size="sm"
                      value={lyricAudience}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricAudience(e.target.value as LyricAudience)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="kids">Kids</option>
                      <option value="general">General</option>
                      <option value="adult">Adult</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Directness</FormLabel>
                    <Select
                      size="sm"
                      value={lyricDirectness}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricDirectness(e.target.value as LyricDirectness)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="direct">Direct (literal)</option>
                      <option value="balanced">Balanced</option>
                      <option value="metaphor_heavy">Metaphor Heavy</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Humor</FormLabel>
                    <Select
                      size="sm"
                      value={lyricHumor}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricHumor(e.target.value as LyricHumor)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="none">None</option>
                      <option value="light">Light</option>
                      <option value="comedic">Comedic</option>
                      <option value="crude">Crude</option>
                    </Select>
                  </FormControl>
                </HStack>

                <HStack spacing={4} flexWrap="wrap">
                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Explicitness</FormLabel>
                    <Select
                      size="sm"
                      value={lyricExplicitness}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricExplicitness(e.target.value as LyricExplicitness)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="clean">Clean</option>
                      <option value="innuendo">Innuendo</option>
                      <option value="explicit">Explicit</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Persona</FormLabel>
                    <Select
                      size="sm"
                      value={lyricPersona}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricPersona(e.target.value as LyricPersona)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="earnest">Earnest</option>
                      <option value="playful">Playful</option>
                      <option value="aggressive">Aggressive</option>
                      <option value="romantic">Romantic</option>
                      <option value="melancholic">Melancholic</option>
                    </Select>
                  </FormControl>
                </HStack>

                <HStack spacing={4} flexWrap="wrap">
                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Lines per section</FormLabel>
                    <Select
                      size="sm"
                      value={lyricLinesPerSection}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricLinesPerSection(e.target.value as LyricLinesPerSection)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="2_lines">2 lines</option>
                      <option value="4_lines">4 lines</option>
                      <option value="6_lines">6 lines</option>
                      <option value="8_lines">8 lines</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Line length</FormLabel>
                    <Select
                      size="sm"
                      value={lyricLineLength}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricLineLength(e.target.value as LyricLineLength)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="sparse">Sparse (3-5 syllables)</option>
                      <option value="short">Short (5-8 syllables)</option>
                      <option value="default">Default (8-12 syllables)</option>
                      <option value="long">Long (12-16 syllables)</option>
                    </Select>
                  </FormControl>
                </HStack>

                <HStack spacing={4} flexWrap="wrap">
                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Point of view</FormLabel>
                    <Select
                      size="sm"
                      value={lyricPOV}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricPOV(e.target.value as LyricPOV)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="first">First person (I/me/my)</option>
                      <option value="second">Second person (you/your)</option>
                      <option value="third">Third person (he/she/they)</option>
                      <option value="none">None (observational)</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Rhyme scheme</FormLabel>
                    <Select
                      size="sm"
                      value={lyricRhymeScheme}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricRhymeScheme(e.target.value as LyricRhymeScheme)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto (AABB bias)</option>
                      <option value="aabb">AABB</option>
                      <option value="abab">ABAB</option>
                      <option value="abcb">ABCB</option>
                      <option value="aaaa">AAAA</option>
                      <option value="internal">Internal rhyme</option>
                    </Select>
                  </FormControl>
                </HStack>

                <Text fontSize="xs" color="gray.500">
                  Leave on "Auto" to let the AI infer from your style and artists.
                </Text>
              </VStack>
            </Collapse>
          </Box>
        </Collapse>

        {/* Prompt Variant Selector - only show for Song Style Prompt mode */}
        <Collapse in={styleMode === 'songStylePrompt' && availableVariants.length > 1} animateOpacity>
          <FormControl>
            <FormLabel>
              <HStack spacing={2}>
                <Text>Prompt Engine</Text>
                <Tooltip 
                  label="Choose which AI prompt style to use. V2 uses Reddit MAX mode format."
                  placement="top"
                  hasArrow
                >
                  <Badge colorScheme="purple" fontSize="xs" cursor="help" variant="subtle">
                    A/B Test
                  </Badge>
                </Tooltip>
              </HStack>
            </FormLabel>
            <Menu matchWidth autoSelect={false}>
              <MenuButton
                as={Button}
                rightIcon={<ChevronDownIcon />}
                bg="gray.800"
                borderColor="gray.600"
                borderWidth="1px"
                _hover={{ borderColor: 'gray.500', bg: 'gray.800' }}
                _active={{ bg: 'gray.700' }}
                fontWeight="normal"
                w="100%"
                textAlign="left"
                px={4}
              >
                <HStack justify="space-between" w="100%" pr={2}>
                  <HStack spacing={2}>
                    <Text>
                      {selectedVariant === 'v1' ? '🎵 V1 — Baseline' : 
                       selectedVariant === 'v2_reddit_tricks' ? '🚀 V2 — MAX Mode' :
                       selectedVariant === 'v3_two_step' ? '⚡ V3 — Two-Step' :
                       selectedVariant === 'v4_lyric_profile' ? '🎭 V4 — Lyric Profile' :
                       selectedVariant === 'v5_hybrid' ? '🔥 V5 — Hybrid' :
                       selectedVariant === 'v6_genre_disambiguation' ? '🎯 V6 — Genre Precision' :
                       selectedVariant === 'v7_genre_term_disambiguation' ? '🛡️ V7 — Genre+Vocab Guardrails' :
                       selectedVariant === 'v8_channel_split' ? '🎤 V8 — Channel Split' :
                       selectedVariant === 'v9_comprehensive_exclude' ? '🚫 V9 — Comprehensive EXCLUDE' :
                       selectedVariant === 'v10_suno_friendly' ? '🎹 V10 — Suno-Friendly' :
                       selectedVariant}
                    </Text>
                    {promptVariants.find(v => v.id === selectedVariant)?.is_default && (
                      <Text as="span">★</Text>
                    )}
                  </HStack>
                </HStack>
              </MenuButton>
              <Portal>
                <MenuList bg="gray.800" borderColor="gray.600" zIndex={1500}>
                  {availableVariants.map((variant: PromptVariantInfo) => {
                    const formatBreakdown = () => {
                      const b = variant.prompt_lengths_breakdown;
                      if (!b) return `${(variant.prompt_length / 1000).toFixed(1)}k`;
                      
                      const fmt = (n: number) => `${(n / 1000).toFixed(1)}k`;
                      
                      if (b.combined !== undefined) {
                        // Single-step: COMBINED(X), REPAIR(Y), TOTAL(Z)
                        return `COMBINED(${fmt(b.combined)}), REPAIR(${fmt(b.repair)}), TOTAL(${fmt(b.total)})`;
                      } else {
                        // Two-step: STYLE(X), LYRICS(Y), REPAIR(Z), TOTAL(T)
                        return `STYLE(${fmt(b.style || 0)}), LYRICS(${fmt(b.lyrics || 0)}), REPAIR(${fmt(b.repair)}), TOTAL(${fmt(b.total)})`;
                      }
                    };
                    const label = variant.id === 'v1' ? '🎵 V1 — Baseline' : 
                                  variant.id === 'v2_reddit_tricks' ? '🚀 V2 — MAX Mode' :
                                  variant.id === 'v3_two_step' ? '⚡ V3 — Two-Step' :
                                  variant.id === 'v4_lyric_profile' ? '🎭 V4 — Lyric Profile' :
                                  variant.id === 'v5_hybrid' ? '🔥 V5 — Hybrid' :
                                  variant.id === 'v6_genre_disambiguation' ? '🎯 V6 — Genre Precision' :
                                  variant.id === 'v7_genre_term_disambiguation' ? '🛡️ V7 — Genre+Vocab Guardrails' :
                                  variant.id === 'v8_channel_split' ? '🎤 V8 — Channel Split' :
                                  variant.id === 'v9_comprehensive_exclude' ? '🚫 V9 — Comprehensive EXCLUDE' :
                                  variant.id === 'v10_suno_friendly' ? '🎹 V10 — Suno-Friendly' :
                                  variant.id;
                    const isSelected = selectedVariant === variant.id;
                    return (
                      <MenuItem
                        key={variant.id}
                        onClick={() => setSelectedVariant(variant.id as PromptVariant)}
                        bg={isSelected ? 'gray.700' : 'transparent'}
                        _hover={{ bg: 'gray.600' }}
                        _active={{ bg: 'gray.600' }}
                        sx={{
                          '&:focus:not(:hover)': {
                            bg: isSelected ? 'gray.700' : 'transparent',
                            boxShadow: 'none',
                          },
                        }}
                      >
                        <HStack justify="space-between" w="100%">
                          <HStack spacing={2}>
                            <Text>{label}</Text>
                            {variant.is_default && (
                              <Text>★</Text>
                            )}
                          </HStack>
                          <Text color="gray.500" fontSize="xs" ml={4}>
                            {formatBreakdown()}
                          </Text>
                        </HStack>
                      </MenuItem>
                    );
                  })}
                </MenuList>
              </Portal>
            </Menu>
          </FormControl>
        </Collapse>

        {/* Model Selectors - show different options based on variant type */}
        <Collapse in={styleMode === 'songStylePrompt' && availableModels.length > 0} animateOpacity>
          {/* Single-step variants (V1/V2): single model dropdown */}
          <Collapse
            in={
              !selectedVariant ||
              !TWO_STEP_VARIANTS.includes(selectedVariant as PromptVariant)
            }
            animateOpacity
          >
            <FormControl>
              <FormLabel>
                <HStack spacing={2}>
                  <Text>Model</Text>
                  <Badge 
                    colorScheme={availableModels.find((m: ModelInfo) => m.id === selectedModel)?.provider === 'openai' ? 'green' : 'blue'} 
                    fontSize="xs" 
                    variant="subtle"
                  >
                    {availableModels.find((m: ModelInfo) => m.id === selectedModel)?.provider || ''}
                  </Badge>
                </HStack>
              </FormLabel>
              <Select
                value={selectedModel}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedModel(e.target.value)}
                bg="gray.800"
                borderColor="gray.600"
                _hover={{ borderColor: 'gray.500' }}
              >
                {availableModels.map((model: ModelInfo) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                    {model.is_default ? ' ★' : ''}
                  </option>
                ))}
              </Select>
            </FormControl>
          </Collapse>

          {/* Two-step variants (V3/V4/V5): separate style and lyrics model dropdowns */}
          <Collapse
            in={
              Boolean(selectedVariant) &&
              TWO_STEP_VARIANTS.includes(selectedVariant as PromptVariant)
            }
            animateOpacity
          >
            <VStack spacing={3} align="stretch">
              <FormControl>
                <FormLabel>
                  <HStack spacing={2}>
                    <Text>Style Model</Text>
                    <Badge 
                      colorScheme={availableModels.find((m: ModelInfo) => m.id === selectedStyleModel)?.provider === 'openai' ? 'green' : 'blue'} 
                      fontSize="xs" 
                      variant="subtle"
                    >
                      {availableModels.find((m: ModelInfo) => m.id === selectedStyleModel)?.provider || ''}
                    </Badge>
                    <Text fontSize="xs" color="gray.500">(SUNO prompt)</Text>
                  </HStack>
                </FormLabel>
                <Select
                  value={selectedStyleModel}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedStyleModel(e.target.value)}
                  bg="gray.800"
                  borderColor="gray.600"
                  _hover={{ borderColor: 'gray.500' }}
                >
                  {availableModels.map((model: ModelInfo) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                      {model.is_style_default ? ' ★' : ''}
                    </option>
                  ))}
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>
                  <HStack spacing={2}>
                    <Text>Lyrics Model</Text>
                    <Badge 
                      colorScheme={availableModels.find((m: ModelInfo) => m.id === selectedLyricsModel)?.provider === 'openai' ? 'green' : 'blue'} 
                      fontSize="xs" 
                      variant="subtle"
                    >
                      {availableModels.find((m: ModelInfo) => m.id === selectedLyricsModel)?.provider || ''}
                    </Badge>
                    <Text fontSize="xs" color="gray.500">(lyrics)</Text>
                  </HStack>
                </FormLabel>
                <Select
                  value={selectedLyricsModel}
                  onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedLyricsModel(e.target.value)}
                  bg="gray.800"
                  borderColor="gray.600"
                  _hover={{ borderColor: 'gray.500' }}
                >
                  {availableModels.map((model: ModelInfo) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                      {model.is_lyrics_default ? ' ★' : ''}
                    </option>
                  ))}
                </Select>
              </FormControl>
            </VStack>
          </Collapse>
        </Collapse>
      </VStack>

      <Button
        colorScheme="green"
        size="lg"
        width="full"
        mt={6}
        onClick={handleGenerate}
        isLoading={isLoading}
        loadingText={(styleMode === 'pastSunoPrompts' || styleMode === 'favorites') ? 'Processing...' : 'Generating...'}
      >
        {getButtonLabel()}
      </Button>
    </Box>
  );
}
