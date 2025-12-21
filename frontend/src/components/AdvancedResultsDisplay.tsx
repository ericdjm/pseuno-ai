import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  useToast,
  Divider,
  Badge,
  Wrap,
  WrapItem,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
  Stat,
  StatLabel,
  StatNumber,
  SimpleGrid,
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

  const getIntensityColor = (value: number) => {
    if (value >= 70) return 'red';
    if (value >= 40) return 'orange';
    return 'green';
  };

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
            {result.debug_info.mode}
          </Badge>
        </HStack>
      </Box>

      <Divider />

      {/* Vibe Signature */}
      <Box>
        <Text fontWeight="bold" mb={3}>Vibe Signature</Text>
        <VStack align="stretch" spacing={3}>
          <HStack>
            <Text fontSize="sm" color="gray.500">Primary Feeling:</Text>
            <Badge colorScheme="purple">{result.vibe_signature.primary_feeling}</Badge>
          </HStack>

          <Box>
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Intensity Vector</Text>
            <SimpleGrid columns={3} spacing={3}>
              <Stat size="sm">
                <StatLabel>Vocal</StatLabel>
                <StatNumber color={`${getIntensityColor(result.vibe_signature.intensity_vector.vocal)}.400`}>
                  {result.vibe_signature.intensity_vector.vocal}
                </StatNumber>
              </Stat>
              <Stat size="sm">
                <StatLabel>Rhythmic</StatLabel>
                <StatNumber color={`${getIntensityColor(result.vibe_signature.intensity_vector.rhythmic)}.400`}>
                  {result.vibe_signature.intensity_vector.rhythmic}
                </StatNumber>
              </Stat>
              <Stat size="sm">
                <StatLabel>Textural</StatLabel>
                <StatNumber color={`${getIntensityColor(result.vibe_signature.intensity_vector.textural)}.400`}>
                  {result.vibe_signature.intensity_vector.textural}
                </StatNumber>
              </Stat>
            </SimpleGrid>
          </Box>

          <Box>
            <Text fontSize="sm" fontWeight="semibold" mb={2}>Control Fingerprint</Text>
            <Wrap>
              {result.vibe_signature.control_fingerprint.map((control, i) => (
                <WrapItem key={i}>
                  <Badge colorScheme="cyan">{control}</Badge>
                </WrapItem>
              ))}
            </Wrap>
          </Box>
        </VStack>
      </Box>

      <Divider />

      {/* Active Control Layers */}
      <Box>
        <Text fontWeight="bold" mb={3}>Active Control Layers</Text>
        <Wrap>
          {Object.entries(result.control_layers_used).map(([layer, active]) => (
            active && (
              <WrapItem key={layer}>
                <Badge colorScheme="green">{layer.replace(/_/g, ' ')}</Badge>
              </WrapItem>
            )
          ))}
        </Wrap>
      </Box>

      <Divider />

      {/* Suno Prompt */}
      <Box>
        <HStack justify="space-between" mb={2}>
          <Text fontWeight="bold">Suno Prompt</Text>
          <HStack>
            <Text fontSize="sm" color="gray.500">
              {result.debug_info.prompt_length} chars
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
          <HStack>
            <Text fontWeight="bold">Lyrics</Text>
            <Badge colorScheme="blue">{result.debug_info.lyric_density}</Badge>
          </HStack>
          <HStack>
            <Text fontSize="sm" color="gray.500">
              {result.debug_info.lyrics_length} chars
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

      {/* Debug Info (Collapsible) */}
      <Accordion allowToggle>
        <AccordionItem>
          <h2>
            <AccordionButton>
              <Box flex="1" textAlign="left">
                <Text fontWeight="semibold">Debug Info</Text>
              </Box>
              <AccordionIcon />
            </AccordionButton>
          </h2>
          <AccordionPanel pb={4}>
            <VStack align="stretch" spacing={2}>
              <Code p={2} borderRadius="md" display="block">
                <pre>{JSON.stringify(result, null, 2)}</pre>
              </Code>
            </VStack>
          </AccordionPanel>
        </AccordionItem>
      </Accordion>
    </VStack>
  );
}
