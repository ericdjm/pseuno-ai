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
} from '@chakra-ui/react';
import { CopyIcon } from '@chakra-ui/icons';
import { AdvancedGenerateResponse } from '../api';

interface AdvancedResultsDisplayProps {
  result: AdvancedGenerateResponse;
}

export default function AdvancedResultsDisplay({ result }: AdvancedResultsDisplayProps) {
  const toast = useToast();

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: `${label} copied!`,
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
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
          <Badge colorScheme="purple" fontSize="md" px={3} py={1}>
            Agent Output
          </Badge>
        </HStack>
      </Box>

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
