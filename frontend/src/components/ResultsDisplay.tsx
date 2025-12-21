/**
 * Results Display Component
 * Shows generated prompt, lyrics, and copy/share functionality
 */

import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  VStack,
  HStack,
  Button,
  Code,
  useClipboard,
  IconButton,
  Tooltip,
  Divider,
  useToast,
} from '@chakra-ui/react';
import { FaCopy, FaCheck, FaShareAlt, FaRedo } from 'react-icons/fa';

import { GenerateResponse, createShareUrl } from '../api';

interface ResultsDisplayProps {
  result: GenerateResponse;
  onGenerateVariation: () => void;
  generating: boolean;
}

export function ResultsDisplay({
  result,
  onGenerateVariation,
  generating,
}: ResultsDisplayProps) {
  const toast = useToast();
  const promptClipboard = useClipboard(result.suno_prompt);
  const lyricsClipboard = useClipboard(result.lyrics);

  const handleShare = () => {
    const url = createShareUrl(result);
    navigator.clipboard.writeText(url);
    toast({
      title: 'Share link copied!',
      description: 'Anyone with this link can see your generated result',
      status: 'success',
      duration: 3000,
    });
  };

  return (
    <Card bg="gray.800" borderColor="gray.700" variant="outline">
      <CardHeader pb={2}>
        <HStack justify="space-between" align="start" wrap="wrap" gap={4}>
          <VStack align="start" spacing={1}>
            <Heading size="lg" color="brand.400">
              {result.concept_title}
            </Heading>
            <Text color="gray.400" fontSize="sm">
              Your personalized Suno AI prompt is ready
            </Text>
          </VStack>
          
          <HStack spacing={2}>
            <Tooltip label="Generate a new variation">
              <Button
                leftIcon={<FaRedo />}
                variant="outline"
                size="sm"
                onClick={onGenerateVariation}
                isLoading={generating}
              >
                New Variation
              </Button>
            </Tooltip>
            <Tooltip label="Copy shareable link">
              <IconButton
                aria-label="Share"
                icon={<FaShareAlt />}
                variant="ghost"
                size="sm"
                onClick={handleShare}
              />
            </Tooltip>
          </HStack>
        </HStack>
      </CardHeader>
      
      <CardBody pt={4}>
        <VStack spacing={6} align="stretch">
          {/* Suno Prompt */}
          <Box>
            <HStack mb={2} justify="space-between">
              <Text fontWeight="semibold" color="gray.300">
                Suno AI Prompt
              </Text>
              <Button
                leftIcon={promptClipboard.hasCopied ? <FaCheck /> : <FaCopy />}
                size="xs"
                variant="ghost"
                onClick={promptClipboard.onCopy}
                colorScheme={promptClipboard.hasCopied ? 'green' : 'gray'}
              >
                {promptClipboard.hasCopied ? 'Copied!' : 'Copy'}
              </Button>
            </HStack>
            <Code
              display="block"
              whiteSpace="pre-wrap"
              p={4}
              borderRadius="md"
              bg="gray.900"
              color="green.300"
              fontSize="sm"
              fontFamily="mono"
              overflowX="auto"
            >
              {result.suno_prompt}
            </Code>
            <Text fontSize="xs" color="gray.500" mt={1}>
              {result.suno_prompt.length} / 700 characters
            </Text>
          </Box>
          
          <Divider borderColor="gray.700" />
          
          {/* Lyrics */}
          <Box>
            <HStack mb={2} justify="space-between">
              <Text fontWeight="semibold" color="gray.300">
                Original Lyrics
              </Text>
              <Button
                leftIcon={lyricsClipboard.hasCopied ? <FaCheck /> : <FaCopy />}
                size="xs"
                variant="ghost"
                onClick={lyricsClipboard.onCopy}
                colorScheme={lyricsClipboard.hasCopied ? 'green' : 'gray'}
              >
                {lyricsClipboard.hasCopied ? 'Copied!' : 'Copy'}
              </Button>
            </HStack>
            <Box
              p={4}
              borderRadius="md"
              bg="gray.900"
              maxH="400px"
              overflowY="auto"
            >
              <Text
                whiteSpace="pre-wrap"
                fontFamily="mono"
                fontSize="sm"
                lineHeight="tall"
              >
                {result.lyrics.split('\n').map((line, idx) => {
                  // Highlight section tags
                  if (line.startsWith('[') && line.endsWith(']')) {
                    return (
                      <Text
                        as="span"
                        key={idx}
                        display="block"
                        color="brand.400"
                        fontWeight="bold"
                        mt={idx > 0 ? 2 : 0}
                      >
                        {line}
                      </Text>
                    );
                  }
                  return (
                    <Text as="span" key={idx} display="block" color="gray.200">
                      {line || '\u00A0'}
                    </Text>
                  );
                })}
              </Text>
            </Box>
            <Text fontSize="xs" color="gray.500" mt={1}>
              {result.lyrics.length} / 1800 characters
            </Text>
          </Box>
          
          {/* Debug Profile (if present) */}
          {result.debug_profile && (
            <>
              <Divider borderColor="gray.700" />
              <Box>
                <Text fontWeight="semibold" color="gray.500" mb={2} fontSize="sm">
                  Debug: Taste Profile Used
                </Text>
                <Code
                  display="block"
                  whiteSpace="pre-wrap"
                  p={3}
                  borderRadius="md"
                  bg="gray.900"
                  color="gray.400"
                  fontSize="xs"
                >
                  {JSON.stringify(result.debug_profile, null, 2)}
                </Code>
              </Box>
            </>
          )}
        </VStack>
      </CardBody>
    </Card>
  );
}
