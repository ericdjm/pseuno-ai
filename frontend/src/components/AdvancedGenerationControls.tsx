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
      const artists = parseList(artistInput);
      const tags = parseList(tagsInput);

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
    const current = parseList(artistInput);
    if (!current.some((artist) => artist.toLowerCase() === name.toLowerCase())) {
      const updated = [...current, name];
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
            onChange={(e) => setArtistInput(e.target.value)}
          />
          {artistInput.trim() ? (
            <Wrap mt={2}>
              {parseList(artistInput).map((artist) => (
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
                      {artist.name}
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
            onChange={(e) => setSongPrompt(e.target.value)}
          />
        </FormControl>

        <FormControl isRequired>
          <FormLabel>Lyrics Topic</FormLabel>
          <Input
            placeholder="What should the lyrics be about?"
            value={lyricsAbout}
            onChange={(e) => setLyricsAbout(e.target.value)}
          />
        </FormControl>

        <FormControl>
          <FormLabel>Tags (Optional)</FormLabel>
          <Input
            placeholder="Comma-separated tags (e.g., dubstep, airy, 90s)"
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
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
