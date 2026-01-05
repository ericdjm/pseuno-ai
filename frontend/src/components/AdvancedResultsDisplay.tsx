import { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  useToast,
  Divider,
  Badge,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Icon,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Link,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
  Textarea,
  useDisclosure,
} from '@chakra-ui/react';
import { CopyIcon, StarIcon, ExternalLinkIcon, EditIcon } from '@chakra-ui/icons';
import { 
  AdvancedGenerateResponse, 
  updateSavedPrompt, 
  refineLyrics, 
  LyricsRefinementRequest 
} from '../api';
import DebugTraceViewer from './debug/DebugTraceViewer';

interface AdvancedResultsDisplayProps {
  result: AdvancedGenerateResponse;
  onFavoriteToggled?: () => void;
}

export default function AdvancedResultsDisplay({
  result,
  onFavoriteToggled,
}: AdvancedResultsDisplayProps) {
  const toast = useToast();
  const [isFavorite, setIsFavorite] = useState(result.is_favorite);
  const [togglingFavorite, setTogglingFavorite] = useState(false);

  // Lyrics refinement state
  const { isOpen: isLyricsRefineOpen, onOpen: onLyricsRefineOpen, onClose: onLyricsRefineClose } = useDisclosure();
  const [currentLyrics, setCurrentLyrics] = useState(result.lyrics);
  const [lyricsChangeRequest, setLyricsChangeRequest] = useState('');
  const [isRefiningLyrics, setIsRefiningLyrics] = useState(false);

  // Sync isFavorite state when result changes (new generation)
  useEffect(() => {
    setIsFavorite(result.is_favorite);
    setCurrentLyrics(result.lyrics);
  }, [result.prompt_id, result.is_favorite, result.lyrics]);

  const handleRefineLyrics = async () => {
    if (!lyricsChangeRequest.trim()) {
      toast({
        title: 'Please describe the changes you want',
        status: 'warning',
        duration: 2000,
      });
      return;
    }

    setIsRefiningLyrics(true);
    try {
      const payload: LyricsRefinementRequest = {
        current_lyrics: currentLyrics,
        change_request: lyricsChangeRequest,
      };

      const response = await refineLyrics(payload);
      
      setCurrentLyrics(response.refined_lyrics);
      setLyricsChangeRequest('');
      onLyricsRefineClose();

      toast({
        title: 'Lyrics refined successfully',
        description: response.changes_made || 'Applied your requested changes',
        status: 'success',
        duration: 3000,
      });
    } catch (err) {
      console.error('Error refining lyrics:', err);
      toast({
        title: 'Failed to refine lyrics',
        description: err instanceof Error ? err.message : 'Unknown error',
        status: 'error',
        duration: 4000,
      });
    } finally {
      setIsRefiningLyrics(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: `${label} copied!`,
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleToggleFavorite = async () => {
    if (!result.prompt_id) {
      toast({
        title: 'Cannot favorite',
        description: 'Prompt was not saved. Try generating again.',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setTogglingFavorite(true);
    try {
      const newFavoriteState = !isFavorite;
      await updateSavedPrompt(result.prompt_id, { is_favorite: newFavoriteState });
      setIsFavorite(newFavoriteState);
      toast({
        title: newFavoriteState ? 'Added to favorites!' : 'Removed from favorites',
        status: 'success',
        duration: 2000,
      });
      onFavoriteToggled?.();
    } catch (e) {
      toast({
        title: 'Failed to update',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setTogglingFavorite(false);
    }
  };

  const promptLength = result.suno_prompt.length;
  const lyricsLength = result.lyrics.length;

  // Build the Suno create URL with the style prompt pre-filled
  const sunoCreateUrl = result.suno_prompt
    ? `https://suno.com/create?style=${encodeURIComponent(result.suno_prompt)}`
    : null;

  return (
    <VStack spacing={6} align="stretch">
      {/* Title and ID */}
      <Box>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1} flex={1}>
            <HStack spacing={2} align="center">
              <Text fontSize="2xl" fontWeight="bold">
                {result.concept_title}
              </Text>
              <Button
                size="xs"
                leftIcon={<CopyIcon />}
                onClick={() => copyToClipboard(result.concept_title, 'Title')}
                colorScheme="green"
                variant="ghost"
              >
                Copy
              </Button>
            </HStack>
            <Text fontSize="sm" color="gray.500">
              ID: {result.generation_id}
            </Text>
          </VStack>
          <HStack spacing={2}>
            <Button
              leftIcon={<Icon as={StarIcon} color={isFavorite ? 'yellow.400' : undefined} />}
              colorScheme="yellow"
              variant={isFavorite ? 'solid' : 'outline'}
              size="sm"
              onClick={handleToggleFavorite}
              isLoading={togglingFavorite}
            >
              {isFavorite ? 'Favorited' : 'Favorite'}
            </Button>
            <Badge colorScheme="purple" fontSize="md" px={3} py={1}>
              Agent Output
            </Badge>
          </HStack>
        </HStack>
      </Box>

      <Divider />

      {/* Suno Prompt */}
      <Box>
        <HStack justify="space-between" mb={2}>
          <Text fontWeight="bold">Suno Prompt</Text>
          <HStack>
            <Text fontSize="sm" color="gray.500">
              {promptLength} chars
            </Text>
            <Button
              size="sm"
              leftIcon={<CopyIcon />}
              onClick={() => copyToClipboard(result.suno_prompt, 'Prompt')}
              colorScheme="green"
            >
              Copy
            </Button>
          </HStack>
        </HStack>
        <Box
          p={4}
          bg="gray.800"
          borderRadius="md"
          whiteSpace="pre-wrap"
          fontFamily="monospace"
          fontSize="sm"
        >
          {result.suno_prompt}
        </Box>
        {/* Open in Suno link */}
        {sunoCreateUrl && (
          <HStack mt={3} spacing={2}>
            <Link
              href={sunoCreateUrl}
              isExternal
              color="cyan.400"
              fontWeight="medium"
              fontSize="sm"
              _hover={{ color: 'cyan.300', textDecoration: 'underline' }}
            >
              <HStack spacing={1}>
                <ExternalLinkIcon />
                <Text>Open in Suno</Text>
              </HStack>
            </Link>
            <Button
              size="xs"
              leftIcon={<CopyIcon />}
              onClick={() => copyToClipboard(sunoCreateUrl, 'Suno link')}
              colorScheme="cyan"
              variant="ghost"
            >
              Copy link
            </Button>
          </HStack>
        )}
      </Box>

      <Divider />

      {/* Lyrics */}
      <Box>
        <HStack justify="space-between" mb={2}>
          <HStack spacing={2}>
            <Text fontWeight="bold">Lyrics</Text>
            {lyricsLength === 0 && (
              <Badge colorScheme="purple" fontSize="xs">
                Instrumental
              </Badge>
            )}
          </HStack>
          <HStack>
            <Text fontSize="sm" color="gray.500">
              {lyricsLength} chars
            </Text>
            {lyricsLength > 0 && (
              <>
                <Button
                  size="sm"
                  leftIcon={<EditIcon />}
                  onClick={onLyricsRefineOpen}
                  colorScheme="purple"
                  variant="outline"
                >
                  Refine
                </Button>
                <Button
                  size="sm"
                  leftIcon={<CopyIcon />}
                  onClick={() => copyToClipboard(currentLyrics, 'Lyrics')}
                  colorScheme="green"
                >
                  Copy
                </Button>
              </>
            )}
          </HStack>
        </HStack>
        <Box
          p={4}
          bg="gray.800"
          borderRadius="md"
          whiteSpace="pre-wrap"
          fontFamily="monospace"
          fontSize="sm"
        >
          {lyricsLength > 0 ? currentLyrics : (
            <Text color="gray.500" fontStyle="italic">
              No lyrics generated — instrumental mode
            </Text>
          )}
        </Box>
      </Box>

      {/* Exclude - positioned after lyrics for easy copy-paste */}
      {result.exclude && (
        <>
          <Divider />
          <Box>
            <HStack justify="space-between" mb={2}>
              <Text fontWeight="bold">Exclude</Text>
              <Button
                size="sm"
                leftIcon={<CopyIcon />}
                onClick={() => copyToClipboard(result.exclude, 'Exclude')}
                colorScheme="green"
              >
                Copy
              </Button>
            </HStack>
            <Box
              p={4}
              bg="gray.800"
              borderRadius="md"
              whiteSpace="pre-wrap"
              fontFamily="monospace"
              fontSize="sm"
            >
              {result.exclude}
            </Box>
          </Box>
        </>
      )}

      <Divider />

      {/* Parameters */}
      <Box>
        <Text fontWeight="bold" mb={3}>Parameters</Text>
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
          <Stat size="sm">
            <StatLabel>Weirdness</StatLabel>
            <StatNumber>{result.weirdness}%</StatNumber>
          </Stat>
          <Stat size="sm">
            <StatLabel>Style Influence</StatLabel>
            <StatNumber>{result.style_influence}%</StatNumber>
          </Stat>
        </SimpleGrid>
      </Box>

      {/* Debug Info - Expandable */}
      {result.debug_info && (
        <>
          <Divider />
          <Accordion allowToggle>
            <AccordionItem border="none">
              <AccordionButton px={0} _hover={{ bg: 'transparent' }}>
                <HStack flex="1" justify="space-between">
                  <Text fontSize="sm" color="gray.500">
                    Debug Trace
                  </Text>
                  <HStack spacing={2}>
                    {result.debug_info.summary && (
                      <>
                        <Badge colorScheme="blue" fontSize="xs">
                          {(result.debug_info.summary.total_elapsed_ms / 1000).toFixed(1)}s
                        </Badge>
                        <Badge colorScheme="purple" fontSize="xs">
                          {result.debug_info.summary.variant}
                        </Badge>
                        <Badge colorScheme="green" fontSize="xs">
                          {result.debug_info.summary.model}
                        </Badge>
                        {result.debug_info.summary.repairs > 0 && (
                          <Badge colorScheme="orange" fontSize="xs">
                            {result.debug_info.summary.repairs} repairs
                          </Badge>
                        )}
                      </>
                    )}
                    <AccordionIcon />
                  </HStack>
                </HStack>
              </AccordionButton>
              <AccordionPanel pb={4} px={0}>
                <DebugTraceViewer trace={result.debug_info} />
              </AccordionPanel>
            </AccordionItem>
          </Accordion>
        </>
      )}

      {/* Lyrics Refinement Modal */}
      <Modal isOpen={isLyricsRefineOpen} onClose={onLyricsRefineClose} size="xl">
        <ModalOverlay />
        <ModalContent bg="gray.900">
          <ModalHeader>Refine Lyrics</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontWeight="bold" mb={2}>Current Lyrics</Text>
                <Box
                  p={3}
                  bg="gray.800"
                  borderRadius="md"
                  whiteSpace="pre-wrap"
                  fontFamily="monospace"
                  fontSize="sm"
                  maxH="300px"
                  overflowY="auto"
                >
                  {currentLyrics}
                </Box>
              </Box>
              <Box>
                <Text fontWeight="bold" mb={2}>What would you like to change?</Text>
                <Text fontSize="sm" color="gray.400" mb={2}>
                  Examples: "change the chorus", "add another verse", "make the bridge darker"
                </Text>
                <Textarea
                  value={lyricsChangeRequest}
                  onChange={(e) => setLyricsChangeRequest(e.target.value)}
                  placeholder="Describe the changes you want..."
                  bg="gray.800"
                  rows={4}
                  maxLength={500}
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  {lyricsChangeRequest.length}/500
                </Text>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onLyricsRefineClose}>
              Cancel
            </Button>
            <Button
              colorScheme="purple"
              onClick={handleRefineLyrics}
              isLoading={isRefiningLyrics}
              loadingText="Refining..."
            >
              Refine Lyrics
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
}

