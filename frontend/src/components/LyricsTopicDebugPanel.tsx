/**
 * Debug panel for lyrics topic generation.
 * Shows trait extraction, bank selection, and routing info.
 * Only visible in dev mode.
 */

import { useState } from 'react';
import {
  Box,
  Text,
  VStack,
  HStack,
  Collapse,
  Progress,
  Tag,
  Wrap,
  WrapItem,
  Divider,
  Grid,
  GridItem,
} from '@chakra-ui/react';
import type { LyricsTopicDebugInfo } from '../api';

interface Props {
  debug: LyricsTopicDebugInfo | null | undefined;
  bankId: string | null;
  topic: string;
  basedOn?: string; // async classifier basis (empty if not ready)
}

export function LyricsTopicDebugPanel({ debug, bankId, topic, basedOn }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Only show in dev mode
  if (import.meta.env.PROD) {
    return null;
  }

  if (!debug) {
    return null;
  }

  const TraitBar = ({ value, label }: { value: number; label: string }) => (
    <HStack spacing={1} w="full" fontSize="10px">
      <Text w="70px" isTruncated color="gray.400" fontFamily="mono">
        {label}
      </Text>
      <Progress
        value={value * 100}
        size="xs"
        flex={1}
        colorScheme="purple"
        bg="gray.700"
        borderRadius="sm"
      />
      <Text w="28px" textAlign="right" color="gray.500" fontFamily="mono">
        {(value * 100).toFixed(0)}%
      </Text>
    </HStack>
  );

  return (
    <Box
      mt={2}
      borderRadius="md"
      border="1px solid"
      borderColor="purple.500"
      bg="gray.900"
      fontSize="10px"
      opacity={0.9}
    >
      {/* Header - always visible */}
      <HStack
        px={2}
        py={1}
        cursor="pointer"
        onClick={() => setIsExpanded(!isExpanded)}
        _hover={{ bg: 'whiteAlpha.50' }}
        justify="space-between"
      >
        <HStack spacing={2}>
          <Text color="purple.400" fontFamily="mono" fontWeight="bold">
            🔍 DEBUG
          </Text>
          <Text color="gray.500">Bank:</Text>
          <Text color="pink.400" fontWeight="medium">
            {bankId || 'unknown'}
          </Text>
          {debug.style_prompt_keywords_matched.length > 0 && (
            <Text color="gray.600">
              • {debug.style_prompt_keywords_matched.length} keywords
            </Text>
          )}
        </HStack>
        <Text color="gray.500">{isExpanded ? '▼' : '▶'}</Text>
      </HStack>

      {/* Expanded content - scrollable */}
      <Collapse in={isExpanded} animateOpacity>
        <Box
          px={2}
          pb={2}
          borderTop="1px solid"
          borderColor="gray.700"
          maxH="250px"
          overflowY="auto"
        >
          <VStack spacing={2} align="stretch" pt={2}>
            {/* Topic preview */}
            <Box>
              <Text color="gray.500" fontSize="9px" mb={0.5}>
                Generated Topic:
              </Text>
              <Text color="gray.300" fontStyle="italic" fontSize="10px">
                "{topic.slice(0, 80)}..."
              </Text>
              {basedOn && basedOn.trim().length > 0 && (
                <Text color="gray.500" fontSize="9px" mt={1}>
                  Based on:{" "}
                  <Text as="span" color="gray.300" fontFamily="mono">
                    {basedOn.length > 80 ? `${basedOn.slice(0, 80)}…` : basedOn}
                  </Text>
                </Text>
              )}
            </Box>

            {/* Keywords matched */}
            {debug.style_prompt_keywords_matched.length > 0 && (
              <Box>
                <Text color="gray.500" fontSize="9px" mb={1}>
                  Keywords Matched:
                </Text>
                <Wrap spacing={1}>
                  {debug.style_prompt_keywords_matched.slice(0, 10).map((kw) => (
                    <WrapItem key={kw}>
                      <Tag size="sm" colorScheme="purple" fontSize="9px" px={1} py={0}>
                        {kw}
                      </Tag>
                    </WrapItem>
                  ))}
                </Wrap>
              </Box>
            )}

            <Divider borderColor="gray.700" />

            {/* Three-column trait comparison */}
            <Grid templateColumns="repeat(3, 1fr)" gap={2}>
              {/* Tag traits */}
              <GridItem>
                <Text color="gray.500" fontSize="9px" mb={1} fontWeight="medium">
                  From Tags
                </Text>
                {Object.entries(debug.tag_traits).length > 0 ? (
                  <VStack spacing={0.5} align="stretch">
                    {Object.entries(debug.tag_traits)
                      .slice(0, 5)
                      .map(([trait, value]) => (
                        <TraitBar key={trait} label={trait} value={value} />
                      ))}
                  </VStack>
                ) : (
                  <Text color="gray.600" fontStyle="italic" fontSize="9px">
                    No tags
                  </Text>
                )}
              </GridItem>

              {/* Style prompt traits */}
              <GridItem>
                <Text color="gray.500" fontSize="9px" mb={1} fontWeight="medium">
                  From Style Prompt
                </Text>
                {Object.entries(debug.style_prompt_traits).length > 0 ? (
                  <VStack spacing={0.5} align="stretch">
                    {Object.entries(debug.style_prompt_traits)
                      .slice(0, 5)
                      .map(([trait, value]) => (
                        <TraitBar key={trait} label={trait} value={value} />
                      ))}
                  </VStack>
                ) : (
                  <Text color="gray.600" fontStyle="italic" fontSize="9px">
                    No style traits matched
                  </Text>
                )}
              </GridItem>

              {/* Merged traits */}
              <GridItem>
                <Text color="gray.500" fontSize="9px" mb={1} fontWeight="medium">
                  Merged (Used)
                </Text>
                {Object.entries(debug.merged_traits).length > 0 ? (
                  <VStack spacing={0.5} align="stretch">
                    {Object.entries(debug.merged_traits)
                      .slice(0, 5)
                      .map(([trait, value]) => (
                        <TraitBar key={trait} label={trait} value={value} />
                      ))}
                  </VStack>
                ) : (
                  <Text color="gray.600" fontStyle="italic" fontSize="9px">
                    Defaults
                  </Text>
                )}
              </GridItem>
            </Grid>

            <Divider borderColor="gray.700" />

            {/* Top banks - compact */}
            <Box>
              <Text color="gray.500" fontSize="9px" mb={1} fontWeight="medium">
                Top Banks
              </Text>
              <VStack spacing={0.5} align="stretch">
                {debug.top_banks.slice(0, 5).map((bank, idx) => (
                  <HStack
                    key={bank.bank_id}
                    spacing={1}
                    color={bank.bank_id === bankId ? 'green.400' : 'gray.400'}
                    fontSize="9px"
                  >
                    <Text w="12px" textAlign="right" color="gray.600">
                      {idx + 1}.
                    </Text>
                    <Progress
                      value={bank.probability * 100 * 5}
                      size="xs"
                      w="50px"
                      colorScheme={bank.bank_id === bankId ? 'green' : 'blue'}
                      bg="gray.700"
                      borderRadius="sm"
                    />
                    <Text w="30px" fontFamily="mono">
                      {(bank.probability * 100).toFixed(1)}%
                    </Text>
                    <Text flex={1} isTruncated>
                      {bank.name}
                    </Text>
                    {bank.bank_id === bankId && (
                      <Text color="green.500" fontSize="8px">
                        ✓
                      </Text>
                    )}
                  </HStack>
                ))}
              </VStack>
            </Box>
          </VStack>
        </Box>
      </Collapse>
    </Box>
  );
}
