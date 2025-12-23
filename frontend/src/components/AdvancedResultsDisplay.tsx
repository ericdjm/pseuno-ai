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
  Tooltip,
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
} from '@chakra-ui/react';
import { CopyIcon, StarIcon } from '@chakra-ui/icons';
import { AdvancedGenerateResponse, createSavedPrompt } from '../api';

interface AdvancedResultsDisplayProps {
  result: AdvancedGenerateResponse;
  isAuthenticated?: boolean;
  onPromptSaved?: () => void;
}

export default function AdvancedResultsDisplay({
  result,
  isAuthenticated = false,
  onPromptSaved,
}: AdvancedResultsDisplayProps) {
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState(result.concept_title);

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
        title: title || result.concept_title,
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

  return (
    <VStack spacing={6} align="stretch">
      {/* Title and ID */}
      <Box>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={1}>
            <Text fontSize="2xl" fontWeight="bold">
              {result.concept_title}
            </Text>
            <Text fontSize="sm" color="gray.500">
              ID: {result.generation_id}
            </Text>
          </VStack>
          <HStack spacing={2}>
            {isAuthenticated ? (
              <Button
                leftIcon={<Icon as={StarIcon} />}
                colorScheme="yellow"
                variant="outline"
                size="sm"
                onClick={onOpen}
              >
                Save
              </Button>
            ) : (
              <Tooltip label="Sign in to save prompts" placement="left">
                <Button
                  leftIcon={<Icon as={StarIcon} />}
                  colorScheme="yellow"
                  variant="outline"
                  size="sm"
                  isDisabled
                >
                  Save
                </Button>
              </Tooltip>
            )}
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
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter a title for this prompt"
                bg="gray.700"
              />
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

      {/* Parameters */}
      <Box>
        <Text fontWeight="bold" mb={3}>Parameters</Text>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
          <Stat size="sm">
            <StatLabel>Exclude</StatLabel>
            <StatNumber fontSize="sm">{result.exclude || 'None'}</StatNumber>
          </Stat>
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
    </VStack>
  );
}
