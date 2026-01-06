import { useState, useEffect, useCallback, useRef } from 'react';
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
  refineAll,
  UnifiedRefineRequest,
  ApiError,
  DebugTrace,
} from '../api';
import DebugTraceViewer from './debug/DebugTraceViewer';

// Session storage key prefix for refined result snapshots
const REFINED_SNAPSHOT_PREFIX = 'pseuno:v1:refined:';

// Serializable version of refine trace (Date -> ISO string)
interface SerializableRefineTrace {
  trace: DebugTrace;
  timestamp: string; // ISO string
  changedFields: string[];
}

interface RefinedSnapshot {
  prompt: string;
  lyrics: string;
  exclude: string;
  title: string;
  weirdness: number;
  refineTraces: SerializableRefineTrace[];
}

function loadRefinedSnapshot(generationId: string): RefinedSnapshot | null {
  try {
    const stored = sessionStorage.getItem(REFINED_SNAPSHOT_PREFIX + generationId);
    if (stored) {
      return JSON.parse(stored) as RefinedSnapshot;
    }
  } catch (e) {
    console.warn('Failed to load refined snapshot:', e);
  }
  return null;
}

function saveRefinedSnapshot(generationId: string, snapshot: RefinedSnapshot): void {
  try {
    sessionStorage.setItem(REFINED_SNAPSHOT_PREFIX + generationId, JSON.stringify(snapshot));
  } catch (e) {
    console.warn('Failed to save refined snapshot:', e);
  }
}

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

  // Unified refinement state
  const { isOpen: isRefineOpen, onOpen: onRefineOpen, onClose: onRefineClose } = useDisclosure();
  const [changeRequest, setChangeRequest] = useState('');
  const [isRefining, setIsRefining] = useState(false);

  // Local preview state for all editable fields
  // Initialize from persisted snapshot if available, otherwise from result
  const getInitialState = useCallback((): RefinedSnapshot & { refineTracesDeserialized: Array<{ trace: DebugTrace; timestamp: Date; changedFields: string[] }> } => {
    const snapshot = loadRefinedSnapshot(result.generation_id);
    if (snapshot) {
      // Convert ISO strings back to Date objects for refineTraces
      const tracesWithDates = (snapshot.refineTraces || []).map(t => ({
        ...t,
        timestamp: new Date(t.timestamp),
      }));
      return { ...snapshot, refineTracesDeserialized: tracesWithDates };
    }
    return {
      prompt: result.suno_prompt,
      lyrics: result.lyrics,
      exclude: result.exclude,
      title: result.concept_title,
      weirdness: result.weirdness,
      refineTraces: [],
      refineTracesDeserialized: [],
    };
  }, [result.generation_id, result.suno_prompt, result.lyrics, result.exclude, result.concept_title, result.weirdness]);

  const [currentPrompt, setCurrentPrompt] = useState(() => getInitialState().prompt);
  const [currentLyrics, setCurrentLyrics] = useState(() => getInitialState().lyrics);
  const [currentExclude, setCurrentExclude] = useState(() => getInitialState().exclude);
  const [currentTitle, setCurrentTitle] = useState(() => getInitialState().title);
  const [currentWeirdness, setCurrentWeirdness] = useState(() => getInitialState().weirdness);

  // Track refine debug traces (restored from snapshot if available)
  const [refineTraces, setRefineTraces] = useState<Array<{ trace: DebugTrace; timestamp: Date; changedFields: string[] }>>(() => getInitialState().refineTracesDeserialized);

  // Track the current generation_id to detect when result changes
  const lastGenerationIdRef = useRef(result.generation_id);

  // Check on mount if we loaded from a snapshot (for initial render)
  useEffect(() => {
    const snapshot = loadRefinedSnapshot(result.generation_id);
    if (snapshot) {
      hasRefinedRef.current = true;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Sync state when result changes (new generation)
  useEffect(() => {
    // Only reset if the generation_id actually changed (new result)
    if (lastGenerationIdRef.current !== result.generation_id) {
      lastGenerationIdRef.current = result.generation_id;
      
      // Check for persisted snapshot for this new result
      const snapshot = loadRefinedSnapshot(result.generation_id);
      if (snapshot) {
        setCurrentPrompt(snapshot.prompt);
        setCurrentLyrics(snapshot.lyrics);
        setCurrentExclude(snapshot.exclude);
        setCurrentTitle(snapshot.title);
        setCurrentWeirdness(snapshot.weirdness);
        // Restore refine traces (convert ISO strings back to Dates)
        const tracesWithDates = (snapshot.refineTraces || []).map(t => ({
          ...t,
          timestamp: new Date(t.timestamp),
        }));
        setRefineTraces(tracesWithDates);
        // Mark as refined since we restored from a snapshot
        hasRefinedRef.current = true;
      } else {
        setCurrentPrompt(result.suno_prompt);
        setCurrentLyrics(result.lyrics);
        setCurrentExclude(result.exclude);
        setCurrentTitle(result.concept_title);
        setCurrentWeirdness(result.weirdness);
        setRefineTraces([]); // Clear refine traces for fresh result
        // Reset refined flag for fresh result
        hasRefinedRef.current = false;
      }
    }
    setIsFavorite(result.is_favorite);
  }, [result.generation_id, result.is_favorite, result.suno_prompt, result.lyrics, result.exclude, result.concept_title, result.weirdness]);

  // Persist refined state whenever it changes (but only after initial refinement)
  const hasRefinedRef = useRef(false);
  useEffect(() => {
    // Only persist if we've refined at least once (to avoid persisting initial state)
    if (hasRefinedRef.current) {
      // Serialize refineTraces with ISO date strings
      const serializedTraces: SerializableRefineTrace[] = refineTraces.map(t => ({
        trace: t.trace,
        timestamp: t.timestamp.toISOString(),
        changedFields: t.changedFields,
      }));
      saveRefinedSnapshot(result.generation_id, {
        prompt: currentPrompt,
        lyrics: currentLyrics,
        exclude: currentExclude,
        title: currentTitle,
        weirdness: currentWeirdness,
        refineTraces: serializedTraces,
      });
    }
  }, [result.generation_id, currentPrompt, currentLyrics, currentExclude, currentTitle, currentWeirdness, refineTraces]);

  const handleUnifiedRefine = async () => {
    if (!changeRequest.trim()) {
      toast({
        title: 'Please describe the changes you want',
        status: 'warning',
        duration: 2000,
      });
      return;
    }

    // Capture request and close modal immediately for non-blocking UX
    const request = changeRequest;
    setChangeRequest('');
    onRefineClose();
    setIsRefining(true);

    // Show in-progress toast
    toast({
      title: 'Refining...',
      description: 'Your changes are being applied',
      status: 'loading',
      duration: null, // Stays until dismissed or replaced
      id: 'refine-progress',
    });

    try {
      const payload: UnifiedRefineRequest = {
        suno_prompt: currentPrompt,
        lyrics: currentLyrics,
        exclude: currentExclude,
        title: currentTitle,
        weirdness: currentWeirdness,
        change_request: request,
      };

      const response = await refineAll(payload);
      
      // Update local state with response
      setCurrentPrompt(response.suno_prompt);
      setCurrentLyrics(response.lyrics);
      setCurrentExclude(response.exclude);
      setCurrentTitle(response.title);
      setCurrentWeirdness(response.weirdness);

      // Mark that we've refined, so the effect starts persisting
      hasRefinedRef.current = true;

      // Add refine trace if available
      if (response.debug_info) {
        setRefineTraces(prev => [...prev, {
          trace: response.debug_info!,
          timestamp: new Date(),
          changedFields: response.changed_fields,
        }]);
      }

      // Dismiss loading toast and show success
      toast.close('refine-progress');
      
      const changedStr = response.changed_fields.length > 0
        ? `Updated: ${response.changed_fields.join(', ')}`
        : 'No changes made';
      
      toast({
        title: 'Refinement complete',
        description: response.assistant_message || changedStr,
        status: response.changed_fields.length > 0 ? 'success' : 'info',
        duration: 4000,
      });
    } catch (err) {
      console.error('Error refining:', err);
      toast.close('refine-progress');
      
      const errorMsg = err instanceof ApiError 
        ? (err.detail || err.message) 
        : (err instanceof Error ? err.message : 'Unknown error');
      toast({
        title: 'Failed to refine',
        description: errorMsg,
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsRefining(false);
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

  const promptLength = currentPrompt.length;
  const lyricsLength = currentLyrics.length;

  // Build the Suno create URL with the style prompt pre-filled
  const sunoCreateUrl = currentPrompt
    ? `https://suno.com/create?style=${encodeURIComponent(currentPrompt)}`
    : null;

  return (
    <VStack spacing={6} align="stretch">
      {/* Title and ID */}
      <Box>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1} flex={1}>
            <HStack spacing={2} align="center">
              <Text fontSize="2xl" fontWeight="bold">
                {currentTitle}
              </Text>
              <Button
                size="xs"
                leftIcon={<CopyIcon />}
                onClick={() => copyToClipboard(currentTitle, 'Title')}
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
              leftIcon={<EditIcon />}
              colorScheme="purple"
              variant="outline"
              size="sm"
              onClick={onRefineOpen}
            >
              Refine
            </Button>
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
              onClick={() => copyToClipboard(currentPrompt, 'Prompt')}
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
          {currentPrompt}
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
              <Button
                size="sm"
                leftIcon={<CopyIcon />}
                onClick={() => copyToClipboard(currentLyrics, 'Lyrics')}
                colorScheme="green"
              >
                Copy
              </Button>
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
      {currentExclude && (
        <>
          <Divider />
          <Box>
            <HStack justify="space-between" mb={2}>
              <Text fontWeight="bold">Exclude</Text>
              <Button
                size="sm"
                leftIcon={<CopyIcon />}
                onClick={() => copyToClipboard(currentExclude, 'Exclude')}
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
              {currentExclude}
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
            <StatNumber>{currentWeirdness}%</StatNumber>
          </Stat>
          <Stat size="sm">
            <StatLabel>Style Influence</StatLabel>
            <StatNumber>{result.style_influence}%</StatNumber>
          </Stat>
        </SimpleGrid>
      </Box>

      {/* Debug Info - Expandable */}
      {(result.debug_info || refineTraces.length > 0) && (
        <>
          <Divider />
          <Accordion allowToggle>
            {/* Initial Generation Trace */}
            {result.debug_info && (
              <AccordionItem border="none">
                <AccordionButton px={0} _hover={{ bg: 'transparent' }}>
                  <HStack flex="1" justify="space-between">
                    <Text fontSize="sm" color="gray.500">
                      Generation Trace
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
            )}

            {/* Refine Traces */}
            {refineTraces.map((refineData, index) => (
              <AccordionItem key={index} border="none">
                <AccordionButton px={0} _hover={{ bg: 'transparent' }}>
                  <HStack flex="1" justify="space-between">
                    <Text fontSize="sm" color="gray.500">
                      Refine #{index + 1}
                    </Text>
                    <HStack spacing={2}>
                      {refineData.trace.summary && (
                        <Badge colorScheme="blue" fontSize="xs">
                          {(refineData.trace.summary.total_elapsed_ms / 1000).toFixed(1)}s
                        </Badge>
                      )}
                      {refineData.changedFields.map(field => (
                        <Badge key={field} colorScheme="teal" fontSize="xs">
                          {field}
                        </Badge>
                      ))}
                      <AccordionIcon />
                    </HStack>
                  </HStack>
                </AccordionButton>
                <AccordionPanel pb={4} px={0}>
                  <DebugTraceViewer trace={refineData.trace} />
                </AccordionPanel>
              </AccordionItem>
            ))}
          </Accordion>
        </>
      )}

      {/* Unified Refinement Modal */}
      <Modal isOpen={isRefineOpen} onClose={onRefineClose} size="xl">
        <ModalOverlay />
        <ModalContent bg="gray.900">
          <ModalHeader>Refine Song</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Box>
                <Text fontSize="sm" color="gray.400" mb={3}>
                  Describe the change you want. We'll intelligently update the prompt, lyrics, excludes, title, and/or weirdness as needed.
                </Text>
                <Text fontSize="xs" color="gray.500" mb={2}>
                  Examples: "make the ending a dubstep drop", "change the chorus to be about heartbreak", "make it more experimental", "avoid any autotune"
                </Text>
              </Box>
              <Box>
                <Textarea
                  value={changeRequest}
                  onChange={(e) => setChangeRequest(e.target.value)}
                  placeholder="Describe the changes you want..."
                  bg="gray.800"
                  rows={4}
                  maxLength={1000}
                  autoFocus
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  {changeRequest.length}/1000
                </Text>
              </Box>
              
              {/* Current state summary */}
              <Box borderTop="1px solid" borderColor="gray.700" pt={4}>
                <Text fontWeight="bold" mb={2} fontSize="sm">Current State</Text>
                <SimpleGrid columns={2} spacing={2} fontSize="xs" color="gray.400">
                  <Text>Title: {currentTitle}</Text>
                  <Text>Weirdness: {currentWeirdness}%</Text>
                  <Text>Prompt: {promptLength} chars</Text>
                  <Text>Lyrics: {lyricsLength > 0 ? `${lyricsLength} chars` : 'instrumental'}</Text>
                  {currentExclude && <Text gridColumn="span 2">Exclude: {currentExclude.slice(0, 50)}{currentExclude.length > 50 ? '...' : ''}</Text>}
                </SimpleGrid>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onRefineClose}>
              Cancel
            </Button>
            <Button
              colorScheme="purple"
              onClick={handleUnifiedRefine}
              isLoading={isRefining}
              loadingText="Refining..."
            >
              Apply Changes
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
}
