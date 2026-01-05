import { useState } from 'react';
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
  Input,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Link,
} from '@chakra-ui/react';
import { CopyIcon, StarIcon, ExternalLinkIcon } from '@chakra-ui/icons';
import { AdvancedGenerateResponse, createSavedPrompt } from '../api';
import DebugTraceViewer from './debug/DebugTraceViewer';

interface AdvancedResultsDisplayProps {
  result: AdvancedGenerateResponse;
  onPromptSaved?: () => void;
}

export default function AdvancedResultsDisplay({
  result,
  onPromptSaved,
}: AdvancedResultsDisplayProps) {
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [saving, setSaving] = useState(false);
  const MAX_SAVED_TITLE_LEN = 255;
  const [title, setTitle] = useState(result.concept_title.slice(0, MAX_SAVED_TITLE_LEN));

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: `${label} copied!`,
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  const handleSavePrompt = async () => {
    setSaving(true);
    try {
      await createSavedPrompt({
        suno_prompt: result.suno_prompt,
        exclude: result.exclude,
        weirdness: result.weirdness,
        style_influence: result.style_influence,
        title: (title || result.concept_title).slice(0, MAX_SAVED_TITLE_LEN),
      });
      toast({
        title: 'Prompt saved!',
        description: 'Added to your saved prompts library.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      onClose();
      onPromptSaved?.();
    } catch (e) {
      toast({
        title: 'Failed to save',
        description: 'Could not save prompt. Please try again.',
        status: 'error',
        duration: 4000,
        isClosable: true,
      });
    } finally {
      setSaving(false);
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
              leftIcon={<Icon as={StarIcon} />}
              colorScheme="yellow"
              variant="outline"
              size="sm"
              onClick={onOpen}
            >
              Save
            </Button>
            <Badge colorScheme="purple" fontSize="md" px={3} py={1}>
              Agent Output
            </Badge>
          </HStack>
        </HStack>
      </Box>

      {/* Save Prompt Modal */}
      <Modal isOpen={isOpen} onClose={onClose} isCentered>
        <ModalOverlay />
        <ModalContent bg="gray.800">
          <ModalHeader>Save SUNO Prompt</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>Title</FormLabel>
              <Input
                value={title}
                maxLength={MAX_SAVED_TITLE_LEN}
                onChange={(e) => setTitle(e.target.value.slice(0, MAX_SAVED_TITLE_LEN))}
                placeholder="Enter a title for this prompt"
                bg="gray.700"
              />
              <HStack justify="space-between" mt={1}>
                <Text fontSize="xs" color="gray.500">
                  Max {MAX_SAVED_TITLE_LEN} characters
                </Text>
                <Text
                  fontSize="xs"
                  color={title.length >= MAX_SAVED_TITLE_LEN ? 'orange.300' : 'gray.500'}
                >
                  {title.length}/{MAX_SAVED_TITLE_LEN}
                </Text>
              </HStack>
            </FormControl>
            <Text fontSize="sm" color="gray.400" mt={4}>
              This will save the prompt along with its parameters (weirdness: {result.weirdness}%, 
              style influence: {result.style_influence}%).
            </Text>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="yellow"
              onClick={handleSavePrompt}
              isLoading={saving}
            >
              Save Prompt
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

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
          <Text fontWeight="bold">Lyrics</Text>
          <HStack>
            <Text fontSize="sm" color="gray.500">
              {lyricsLength} chars
            </Text>
            <Button
              size="sm"
              leftIcon={<CopyIcon />}
              onClick={() => copyToClipboard(result.lyrics, 'Lyrics')}
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
          {result.lyrics}
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
    </VStack>
  );
}

