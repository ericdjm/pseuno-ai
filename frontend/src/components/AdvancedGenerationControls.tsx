import {
  Box,
  Button,
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
} from '@chakra-ui/react';
import { useState } from 'react';
import {
  generateAdvanced,
  AdvancedGenerateRequest,
  SpotifyProfileResponse,
} from '../api';

interface AdvancedGenerationControlsProps {
  onGenerate: (result: any) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  profile?: SpotifyProfileResponse | null;
}

export default function AdvancedGenerationControls({
  onGenerate,
  isLoading,
  setIsLoading,
  profile,
}: AdvancedGenerationControlsProps) {
  const toast = useToast();

  const MAX_STYLE_PROMPT_LEN = 500;
  const MAX_LYRICS_ABOUT_LEN = 500;
  const MAX_ARTISTS_INPUT_LEN = 300;
  const MAX_TAGS_INPUT_LEN = 300;
  const MAX_ARTISTS_COUNT = 20;
  const MAX_TAGS_COUNT = 25;
  const MAX_ARTIST_NAME_LEN = 60;
  const MAX_TAG_LEN = 40;
  const [artistInput, setArtistInput] = useState('');
  const [songPrompt, setSongPrompt] = useState('');
  const [lyricsAbout, setLyricsAbout] = useState('');
  const [tagsInput, setTagsInput] = useState('');

  const parseList = (value: string) =>
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

  const handleGenerate = async () => {
    if (!songPrompt.trim() || !lyricsAbout.trim()) {
      toast({
        title: 'Missing input',
        description: 'Please fill the song prompt and lyrics topic',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      const artists = parseList(artistInput)
        .map((a) => a.slice(0, MAX_ARTIST_NAME_LEN))
        .slice(0, MAX_ARTISTS_COUNT);
      const tags = parseList(tagsInput)
        .map((t) => t.slice(0, MAX_TAG_LEN))
        .slice(0, MAX_TAGS_COUNT);

      const request: AdvancedGenerateRequest = {
        user_prompt: songPrompt.trim(),
        lyrics_about: lyricsAbout.trim(),
        selected_artists: artists.length > 0 ? artists : undefined,
        tags: tags.length > 0 ? tags : undefined,
      };

      const result = await generateAdvanced(request);
      onGenerate(result);

      toast({
        title: 'Generation complete',
        description: `Created: ${result.concept_title}`,
        status: 'success',
        duration: 5000,
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

  return (
    <Box>
      <VStack spacing={6} align="stretch">
        <FormControl>
          <FormLabel>Artist Influence (Optional)</FormLabel>
          <Input
            placeholder="Comma-separated artist references"
            value={artistInput}
            maxLength={MAX_ARTISTS_INPUT_LEN}
            onChange={(e) =>
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

        <FormControl isRequired>
          <FormLabel>Song Style Prompt</FormLabel>
          <Textarea
            placeholder="Describe the style or sound you want"
            value={songPrompt}
            maxLength={MAX_STYLE_PROMPT_LEN}
            onChange={(e) => setSongPrompt(e.target.value.slice(0, MAX_STYLE_PROMPT_LEN))}
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

        <FormControl isRequired>
          <FormLabel>Lyrics Topic</FormLabel>
          <Input
            placeholder="What should the lyrics be about?"
            value={lyricsAbout}
            maxLength={MAX_LYRICS_ABOUT_LEN}
            onChange={(e) =>
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

        <FormControl>
          <FormLabel>Tags (Optional)</FormLabel>
          <Input
            placeholder="Comma-separated tags (e.g., dubstep, airy, 90s)"
            value={tagsInput}
            maxLength={MAX_TAGS_INPUT_LEN}
            onChange={(e) => setTagsInput(e.target.value.slice(0, MAX_TAGS_INPUT_LEN))}
          />
        </FormControl>
      </VStack>

      <Button
        colorScheme="green"
        size="lg"
        width="full"
        mt={6}
        onClick={handleGenerate}
        isLoading={isLoading}
        loadingText="Generating..."
      >
        Generate Song
      </Button>
    </Box>
  );
}
