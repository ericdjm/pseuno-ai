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
} from '@chakra-ui/react';
import { ChevronDownIcon } from '@chakra-ui/icons';
import { useState, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import {
  generateAdvanced,
  generateLyricsOnly,
  getPromptVariants,
  getModels,
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
  LyricDensity,
  LyricPacing,
} from '../api';

type StyleMode = 'songStylePrompt' | 'savedSunoPrompt';
type LyricsMode = 'lyricsTopic' | 'lyricsEditable';

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
}: AdvancedGenerationControlsProps) {
  const toast = useToast();

  const MAX_STYLE_PROMPT_LEN = 500;
  const MAX_LYRICS_ABOUT_LEN = 500;
  const MAX_LYRICS_TEXT_LEN = 4000;
  const MAX_ARTISTS_INPUT_LEN = 300;
  const MAX_TAGS_INPUT_LEN = 300;
  const MAX_ARTISTS_COUNT = 20;
  const MAX_TAGS_COUNT = 25;
  const MAX_ARTIST_NAME_LEN = 60;
  const MAX_TAG_LEN = 40;

  const [artistInput, setArtistInput] = useState('');
  const [songPrompt, setSongPrompt] = useState('');
  const [lyricsAbout, setLyricsAbout] = useState('');
  const [lyricsEditable, setLyricsEditable] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [lyricsMode, setLyricsMode] = useState<LyricsMode>('lyricsTopic');

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
  const [lyricDensity, setLyricDensity] = useState<LyricDensity>('auto');
  const [lyricPacing, setLyricPacing] = useState<LyricPacing>('auto');

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

    if (styleMode === 'savedSunoPrompt' && !selectedSavedPrompt) {
      toast({
        title: 'No prompt selected',
        description: 'Please select a saved prompt from your library',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    if (lyricsMode === 'lyricsTopic' && !lyricsAbout.trim()) {
      toast({
        title: 'Missing input',
        description: 'Please fill the lyrics topic',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      if (styleMode === 'savedSunoPrompt') {
        // Use lyrics-only generation + copy saved prompt
        const sunoPrompt = selectedSavedPrompt!.suno_prompt.slice(0, MAX_STYLE_PROMPT_LEN);

        if (lyricsMode === 'lyricsTopic') {
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
          };

          onGenerate(result);

          toast({
            title: 'Lyrics generated!',
            status: 'success',
            duration: 3000,
          });
        } else {
          // Lyrics editable mode - just copy the package
          const packageText = [
            `SUNO PROMPT:\n${sunoPrompt}`,
            '',
            `EXCLUDE: ${selectedSavedPrompt!.exclude || 'None'}`,
            `WEIRDNESS: ${selectedSavedPrompt!.weirdness}%`,
            `STYLE INFLUENCE: ${selectedSavedPrompt!.style_influence}%`,
            '',
            `LYRICS:\n${lyricsEditable || '(paste your lyrics here)'}`,
          ].join('\n');

          navigator.clipboard.writeText(packageText);

          toast({
            title: 'Package copied!',
            description: 'Suno prompt and your lyrics have been copied to clipboard.',
            status: 'success',
            duration: 5000,
          });

          // Build a result for display
          const result = {
            generation_id: `reuse-${Date.now()}`,
            concept_title: selectedSavedPrompt!.title || 'Reused Prompt',
            suno_prompt: sunoPrompt,
            lyrics: lyricsEditable,
            exclude: selectedSavedPrompt!.exclude,
            weirdness: selectedSavedPrompt!.weirdness,
            style_influence: selectedSavedPrompt!.style_influence,
          };
          onGenerate(result);
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
        if (lyricDensity !== 'auto') lyricControls.density = lyricDensity;
        if (lyricPacing !== 'auto') lyricControls.pacing = lyricPacing;
        const hasLyricControls = Object.keys(lyricControls).length > 0;

        // Check if using a two-step variant
        const isTwoStep =
          selectedVariant &&
          [
            'v3_two_step',
            'v4_lyric_profile',
            'v5_hybrid',
            'v6_genre_disambiguation',
            'v7_genre_term_disambiguation',
          ].includes(selectedVariant);
        
        const request: AdvancedGenerateRequest = {
          user_prompt: songPrompt.trim(),
          lyrics_about: lyricsAbout.trim(),
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
    if (styleMode === 'savedSunoPrompt') {
      if (lyricsMode === 'lyricsTopic') {
        return 'Generate Lyrics';
      }
      return 'Copy Package';
    }
    return 'Generate Song';
  };

  return (
    <Box>
      <VStack spacing={6} align="stretch">
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
              Song Style Prompt
            </Button>
            <Button
              flex={1}
              colorScheme={styleMode === 'savedSunoPrompt' ? 'green' : 'gray'}
              variant={styleMode === 'savedSunoPrompt' ? 'solid' : 'outline'}
              onClick={() => onStyleModeChange('savedSunoPrompt')}
            >
              Saved Suno Prompt
            </Button>
          </ButtonGroup>
        </FormControl>

        {/* Song Style Prompt (editable) */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
          <FormControl isRequired>
            <FormLabel>Song Style Prompt</FormLabel>
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

        {/* Saved Prompt Selector */}
        <Collapse in={styleMode === 'savedSunoPrompt'} animateOpacity>
          <FormControl isRequired>
            <FormLabel>Select a Saved Prompt</FormLabel>
            {savedPrompts.length === 0 ? (
              <Box
                p={4}
                bg="gray.800"
                borderRadius="md"
                borderWidth="1px"
                borderColor="gray.600"
                textAlign="center"
              >
                <Text color="gray.500">No saved prompts yet.</Text>
                <Text color="gray.600" fontSize="sm" mt={1}>
                  Generate and save a prompt first.
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
                      selectedSavedPrompt?.id === prompt.id ? 'green.400' : 'gray.600'
                    }
                    cursor="pointer"
                    onClick={() => onSelectSavedPrompt(prompt)}
                    _hover={{
                      borderColor:
                        selectedSavedPrompt?.id === prompt.id ? 'green.300' : 'gray.500',
                    }}
                    transition="border-color 0.2s"
                  >
                    <HStack justify="space-between" align="start">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="semibold" fontSize="sm">
                          {prompt.title || 'Untitled'}
                        </Text>
                        <HStack spacing={2} flexWrap="wrap">
                          <Badge colorScheme="blue" fontSize="xs">
                            Weirdness: {prompt.weirdness}%
                          </Badge>
                          <Badge colorScheme="purple" fontSize="xs">
                            Style: {prompt.style_influence}%
                          </Badge>
                        </HStack>
                      </VStack>
                      {selectedSavedPrompt?.id === prompt.id && (
                        <Badge colorScheme="green">Selected</Badge>
                      )}
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

        {/* Lyrics Mode Toggle */}
        <FormControl>
          <FormLabel>Lyrics Input</FormLabel>
          <ButtonGroup size="sm" isAttached variant="outline" width="100%">
            <Button
              flex={1}
              colorScheme={lyricsMode === 'lyricsTopic' ? 'green' : 'gray'}
              variant={lyricsMode === 'lyricsTopic' ? 'solid' : 'outline'}
              onClick={() => setLyricsMode('lyricsTopic')}
            >
              Lyrics Topic
            </Button>
            <Button
              flex={1}
              colorScheme={lyricsMode === 'lyricsEditable' ? 'green' : 'gray'}
              variant={lyricsMode === 'lyricsEditable' ? 'solid' : 'outline'}
              onClick={() => setLyricsMode('lyricsEditable')}
            >
              Custom Lyrics
            </Button>
          </ButtonGroup>
        </FormControl>

        {/* Lyrics Topic */}
        <Collapse in={lyricsMode === 'lyricsTopic'} animateOpacity>
          <FormControl isRequired>
            <FormLabel>Lyrics Topic</FormLabel>
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

        {/* Custom Lyrics */}
        <Collapse in={lyricsMode === 'lyricsEditable'} animateOpacity>
          <FormControl>
            <FormLabel>Custom Lyrics</FormLabel>
            <Textarea
              placeholder="Paste or write your own lyrics here..."
              value={lyricsEditable}
              maxLength={MAX_LYRICS_TEXT_LEN}
              minH="200px"
              onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
                setLyricsEditable(e.target.value.slice(0, MAX_LYRICS_TEXT_LEN))
              }
            />
            <HStack justify="space-between" mt={1}>
              <Text fontSize="xs" color="gray.500">
                Max {MAX_LYRICS_TEXT_LEN} characters
              </Text>
              <Text
                fontSize="xs"
                color={lyricsEditable.length >= MAX_LYRICS_TEXT_LEN ? 'orange.300' : 'gray.500'}
              >
                {lyricsEditable.length}/{MAX_LYRICS_TEXT_LEN}
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

        {/* Lyric Style Controls - collapsible */}
        <Collapse in={styleMode === 'songStylePrompt'} animateOpacity>
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
                    <FormLabel fontSize="sm" color="gray.400">Density</FormLabel>
                    <Select
                      size="sm"
                      value={lyricDensity}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricDensity(e.target.value as LyricDensity)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="sparse">Sparse (atmospheric)</option>
                      <option value="standard">Standard</option>
                      <option value="dense">Dense (wordy)</option>
                    </Select>
                  </FormControl>

                  <FormControl flex="1" minW="140px">
                    <FormLabel fontSize="sm" color="gray.400">Pacing</FormLabel>
                    <Select
                      size="sm"
                      value={lyricPacing}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => setLyricPacing(e.target.value as LyricPacing)}
                      bg="gray.800"
                      borderColor="gray.600"
                    >
                      <option value="auto">Auto</option>
                      <option value="slow">Slow (rhyme every line)</option>
                      <option value="mid">Mid (standard)</option>
                      <option value="fast">Fast (punchy, sparse rhymes)</option>
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
        <Collapse in={styleMode === 'songStylePrompt' && promptVariants.length > 1} animateOpacity>
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
                       selectedVariant === 'v7_genre_term_disambiguation' ? '🛡️ V7 — Anti-Drift' :
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
                  {promptVariants.map((variant: PromptVariantInfo) => {
                    const formatLengths = (lengths: number[]) => {
                      if (!lengths || lengths.length === 0) {
                        const total = (variant.prompt_length / 1000).toFixed(1);
                        return `${total}k`;
                      }
                      const parts = lengths.map(l => `${(l / 1000).toFixed(1)}k`).join(' + ');
                      const total = (lengths.reduce((a, b) => a + b, 0) / 1000).toFixed(1);
                      return `${parts} = ${total}k`;
                    };
                    const label = variant.id === 'v1' ? '🎵 V1 — Baseline' : 
                                  variant.id === 'v2_reddit_tricks' ? '🚀 V2 — MAX Mode' :
                                  variant.id === 'v3_two_step' ? '⚡ V3 — Two-Step' :
                                  variant.id === 'v4_lyric_profile' ? '🎭 V4 — Lyric Profile' :
                                  variant.id === 'v5_hybrid' ? '🔥 V5 — Hybrid' :
                                  variant.id === 'v6_genre_disambiguation' ? '🎯 V6 — Genre Precision' :
                                  variant.id === 'v7_genre_term_disambiguation' ? '🛡️ V7 — Anti-Drift' :
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
                            {formatLengths(variant.prompt_lengths)}
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
              ![
                'v3_two_step',
                'v4_lyric_profile',
                'v5_hybrid',
                'v6_genre_disambiguation',
                'v7_genre_term_disambiguation',
              ].includes(selectedVariant as string)
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
              [
                'v3_two_step',
                'v4_lyric_profile',
                'v5_hybrid',
                'v6_genre_disambiguation',
                'v7_genre_term_disambiguation',
              ].includes(selectedVariant as string)
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
        loadingText={styleMode === 'savedSunoPrompt' ? 'Processing...' : 'Generating...'}
      >
        {getButtonLabel()}
      </Button>
    </Box>
  );
}
