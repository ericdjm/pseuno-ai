/**
 * NewLyricsForStyleView - Generate new lyrics for an existing style (style locked).
 * 
 * Features:
 * - Style prompt preview (read-only)
 * - Lyrics topic input
 * - Instrumental toggle
 * - Primary CTA: Generate Lyrics
 * - Advanced disclosure for lyric controls
 */

import { useState, useRef, useEffect } from 'react';
import type { ChangeEvent } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Input,
  FormControl,
  FormLabel,
  Switch,
  Collapse,
  useToast,
  Badge,
  Select,
  IconButton,
} from '@chakra-ui/react';
import { ChevronDownIcon, ChevronUpIcon, CopyIcon } from '@chakra-ui/icons';
import {
  generateLyricsOnly,
  generateLyricsTopic,
  createLyricsThread,
  getModels,
  getSavedPrompt,
  LyricsThread,
  ModelInfo,
  LyricControls,
  LyricAudience,
  LyricHumor,
  LyricPersona,
} from '../api';
import { useSessionStorageState } from '../hooks';

interface NewLyricsForStyleViewProps {
  stylePromptId: number;
  stylePromptText: string;
  styleTitle: string;
  onGenerate: (thread: LyricsThread) => void;
  onCancel: () => void;
}

export default function NewLyricsForStyleView({
  stylePromptId,
  stylePromptText,
  styleTitle,
  onGenerate,
  onCancel,
}: NewLyricsForStyleViewProps) {
  const toast = useToast();

  // Core inputs
  const [lyricsAbout, setLyricsAbout] = useSessionStorageState('draft:newLyricsAbout', '');
  const [isInstrumental, setIsInstrumental] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isGeneratingTopic, setIsGeneratingTopic] = useState(false);

  // Model selection
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [selectedLyricsModel, setSelectedLyricsModel] = useSessionStorageState<string>('draft:selectedLyricsModel', '');
  const initializedFromApi = useRef(false);

  // Lyric controls
  const [lyricAudience, setLyricAudience] = useSessionStorageState<LyricAudience>('draft:lyricAudience', 'auto');
  const [lyricHumor, setLyricHumor] = useSessionStorageState<LyricHumor>('draft:lyricHumor', 'auto');
  const [lyricPersona, setLyricPersona] = useSessionStorageState<LyricPersona>('draft:lyricPersona', 'auto');

  const MAX_LYRICS_ABOUT_LEN = 500;

  // Load models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await getModels();
        setAvailableModels(response.models);
        if (!initializedFromApi.current) {
          if (!selectedLyricsModel) setSelectedLyricsModel(response.default_lyrics_model);
          initializedFromApi.current = true;
        }
      } catch (error) {
        console.error('Failed to fetch models:', error);
      }
    };
    fetchModels();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Copied!',
      status: 'success',
      duration: 1500,
    });
  };

  const handleGenerateTopic = async () => {
    setIsGeneratingTopic(true);
    try {
      const result = await generateLyricsTopic({
        style_prompt: stylePromptText,
      });
      setLyricsAbout(result.topic);
      toast({
        title: result.chosen_moods.length > 0 
          ? `Mood: ${result.chosen_moods.join(', ')}`
          : 'Topic generated',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Failed to generate topic',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGeneratingTopic(false);
    }
  };

  const handleGenerate = async () => {
    if (!isInstrumental && !lyricsAbout.trim()) {
      toast({
        title: 'Missing lyrics topic',
        description: 'Please fill the lyrics topic or enable Instrumental mode',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      let lyricsText = '';
      let songTitle = styleTitle || 'New Song';

      if (!isInstrumental) {
        // Generate lyrics using the locked style
        const lyricsResult = await generateLyricsOnly({
          suno_prompt: stylePromptText,
          lyrics_about: lyricsAbout.trim(),
        });
        lyricsText = lyricsResult.lyrics;
        songTitle = lyricsResult.song_title || songTitle;
      }

      // Create a new thread with the generated lyrics
      const newThread = await createLyricsThread({
        style_prompt_id: stylePromptId,
        title: songTitle,
      });

      // The thread is created empty, we need to update it with lyrics
      // For now, we pass the thread to the parent which can handle updating
      // Actually, the createLyricsThread doesn't set lyrics, so we need a different approach
      // Let me check the API...
      
      // Actually, let's just create the thread and set lyrics via update
      if (lyricsText) {
        const { updateLyricsThread } = await import('../api');
        await updateLyricsThread(newThread.id, { lyrics_text: lyricsText, title: songTitle });
        newThread.lyrics_text = lyricsText;
        newThread.title = songTitle;
      }

      onGenerate(newThread);

      toast({
        title: isInstrumental ? 'Instrumental variation created!' : 'Lyrics generated!',
        description: songTitle,
        status: 'success',
        duration: 3000,
      });

      // Clear the draft
      setLyricsAbout('');
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

  return (
    <Box flex={1} overflow="auto" bg="gray.900" py={4} pt={14} px={4} minW={0}>
      <Box maxW="800px" mx="auto">
        <VStack spacing={6} align="stretch">
          {/* Header */}
          <HStack justify="space-between">
            <Heading size="md">New Lyrics Variation</Heading>
            <Button size="sm" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          </HStack>

          {/* Style Preview (locked) */}
          <Box p={4} bg="gray.800" borderRadius="md" borderLeft="4px solid" borderColor="purple.500">
            <HStack justify="space-between" mb={2}>
              <HStack spacing={2}>
                <Text fontSize="sm" color="gray.400">Style</Text>
                <Badge colorScheme="purple" fontSize="xs">Locked</Badge>
              </HStack>
              <IconButton
                aria-label="Copy style"
                icon={<CopyIcon />}
                size="xs"
                variant="ghost"
                onClick={() => copyToClipboard(stylePromptText)}
              />
            </HStack>
            <Text fontSize="sm" fontFamily="monospace" noOfLines={4} color="gray.300">
              {stylePromptText || 'No style loaded'}
            </Text>
          </Box>

          {/* Instrumental Toggle */}
          <FormControl display="flex" alignItems="center">
            <Switch
              id="instrumental-toggle"
              isChecked={isInstrumental}
              onChange={(e) => setIsInstrumental(e.target.checked)}
              colorScheme="purple"
              mr={3}
            />
            <FormLabel htmlFor="instrumental-toggle" mb="0" cursor="pointer">
              Instrumental (no lyrics)
            </FormLabel>
            {isInstrumental && (
              <Badge colorScheme="purple" ml={2}>Lyrics skipped</Badge>
            )}
          </FormControl>

          {/* Lyrics Topic (hidden if instrumental) */}
          <Collapse in={!isInstrumental} animateOpacity>
            <FormControl isRequired>
              <HStack justify="space-between" mb={1}>
                <FormLabel mb={0}>Lyrics Topic</FormLabel>
                <Button
                  size="xs"
                  colorScheme="purple"
                  variant="outline"
                  isLoading={isGeneratingTopic}
                  loadingText="..."
                  onClick={handleGenerateTopic}
                >
                  ✨ Generate
                </Button>
              </HStack>
              <Input
                placeholder="What should the lyrics be about?"
                value={lyricsAbout}
                maxLength={MAX_LYRICS_ABOUT_LEN}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setLyricsAbout(e.target.value)}
              />
              <Text fontSize="xs" color="gray.500" mt={1} textAlign="right">
                {lyricsAbout.length}/{MAX_LYRICS_ABOUT_LEN}
              </Text>
            </FormControl>
          </Collapse>

          {/* Generate Button */}
          <Button
            colorScheme="green"
            size="lg"
            onClick={handleGenerate}
            isLoading={isLoading}
            loadingText="Generating..."
          >
            {isInstrumental ? 'Create Instrumental Variation' : 'Generate Lyrics'}
          </Button>

          {/* Advanced Disclosure */}
          {!isInstrumental && (
            <Box>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAdvanced(!showAdvanced)}
                leftIcon={showAdvanced ? <ChevronUpIcon /> : <ChevronDownIcon />}
                color="gray.400"
                fontWeight="normal"
                _hover={{ color: 'white' }}
              >
                Advanced options
              </Button>
              <Collapse in={showAdvanced} animateOpacity>
                <VStack spacing={3} align="stretch" mt={4} pl={2} borderLeft="2px solid" borderColor="gray.700">
                  {/* Model Selection */}
                  {availableModels.length > 0 && (
                    <FormControl>
                      <FormLabel fontSize="sm">Lyrics Model</FormLabel>
                      <Select
                        value={selectedLyricsModel}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => setSelectedLyricsModel(e.target.value)}
                        size="sm"
                        bg="gray.800"
                      >
                        {availableModels.map((model) => (
                          <option key={model.id} value={model.id}>
                            {model.name} {model.is_lyrics_default ? '★' : ''}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                  )}

                  {/* Lyric Controls */}
                  <HStack spacing={2} flexWrap="wrap">
                    <FormControl flex="1" minW="120px">
                      <FormLabel fontSize="xs" color="gray.400">Audience</FormLabel>
                      <Select size="xs" value={lyricAudience} onChange={(e) => setLyricAudience(e.target.value as LyricAudience)} bg="gray.800">
                        <option value="auto">Auto</option>
                        <option value="kids">Kids</option>
                        <option value="general">General</option>
                        <option value="adult">Adult</option>
                      </Select>
                    </FormControl>
                    <FormControl flex="1" minW="120px">
                      <FormLabel fontSize="xs" color="gray.400">Humor</FormLabel>
                      <Select size="xs" value={lyricHumor} onChange={(e) => setLyricHumor(e.target.value as LyricHumor)} bg="gray.800">
                        <option value="auto">Auto</option>
                        <option value="none">None</option>
                        <option value="light">Light</option>
                        <option value="comedic">Comedic</option>
                      </Select>
                    </FormControl>
                    <FormControl flex="1" minW="120px">
                      <FormLabel fontSize="xs" color="gray.400">Persona</FormLabel>
                      <Select size="xs" value={lyricPersona} onChange={(e) => setLyricPersona(e.target.value as LyricPersona)} bg="gray.800">
                        <option value="auto">Auto</option>
                        <option value="earnest">Earnest</option>
                        <option value="playful">Playful</option>
                        <option value="aggressive">Aggressive</option>
                        <option value="romantic">Romantic</option>
                        <option value="melancholic">Melancholic</option>
                      </Select>
                    </FormControl>
                  </HStack>
                </VStack>
              </Collapse>
            </Box>
          )}
        </VStack>
      </Box>
    </Box>
  );
}

