/**
 * DebugTraceViewer - Summary-first debug trace viewer
 * 
 * Displays a unified view of debug traces from all variants (V1-V5).
 * Features:
 * - Summary cards at the top (time, LLM calls, repairs)
 * - Calls table showing all LLM calls with timing
 * - Expandable artifacts (prompts, responses) - hidden by default
 */

import { useState } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  Button,
  Collapse,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Code,
  useClipboard,
  IconButton,
  Tooltip,
} from '@chakra-ui/react';
import { ChevronDownIcon, ChevronUpIcon, CopyIcon, CheckIcon } from '@chakra-ui/icons';
import { DebugTrace, DebugSpan } from '../../api';

interface DebugTraceViewerProps {
  trace: DebugTrace;
}

export default function DebugTraceViewer({ trace }: DebugTraceViewerProps) {
  const [expandedSpans, setExpandedSpans] = useState<Set<string>>(new Set());
  const { summary, spans } = trace;

  // Filter spans to show in the calls table (llm_call, repair, profile_infer)
  const callSpans = spans.filter(
    (s) => s.kind === 'llm_call' || s.kind === 'repair' || s.kind === 'profile_infer'
  );

  const toggleSpan = (spanId: string) => {
    setExpandedSpans((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) {
        next.delete(spanId);
      } else {
        next.add(spanId);
      }
      return next;
    });
  };

  const formatTime = (ms: number) => {
    if (ms >= 1000) {
      return `${(ms / 1000).toFixed(1)}s`;
    }
    return `${ms}ms`;
  };

  const getKindColor = (kind: string) => {
    switch (kind) {
      case 'llm_call':
        return 'blue';
      case 'repair':
        return 'orange';
      case 'profile_infer':
        return 'purple';
      case 'validate':
        return 'green';
      case 'parse':
        return 'cyan';
      default:
        return 'gray';
    }
  };

  const getSpanLabel = (span: DebugSpan) => {
    // Extract a friendly label from the span name
    const parts = span.name.split('.');
    if (parts.length >= 2) {
      const step = parts[0]; // style, lyrics, song
      const action = parts[1]; // generate, repair, profile_infer
      if (action === 'repair' && span.meta?.attempt) {
        return `${step} repair #${span.meta.attempt}`;
      }
      return `${step} ${action.replace('_', ' ')}`;
    }
    return span.name;
  };

  return (
    <VStack spacing={4} align="stretch" fontSize="sm">
      {/* Summary Cards */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={3}>
        <Stat size="sm" p={2} bg="gray.800" borderRadius="md">
          <StatLabel fontSize="xs" color="gray.400">Total Time</StatLabel>
          <StatNumber fontSize="lg">{formatTime(summary.total_elapsed_ms)}</StatNumber>
        </Stat>
        <Stat size="sm" p={2} bg="gray.800" borderRadius="md">
          <StatLabel fontSize="xs" color="gray.400">LLM Calls</StatLabel>
          <StatNumber fontSize="lg">{summary.llm_calls}</StatNumber>
        </Stat>
        <Stat size="sm" p={2} bg="gray.800" borderRadius="md">
          <StatLabel fontSize="xs" color="gray.400">Repairs</StatLabel>
          <StatNumber fontSize="lg" color={summary.repairs > 0 ? 'orange.300' : undefined}>
            {summary.repairs}
          </StatNumber>
        </Stat>
        <Stat size="sm" p={2} bg="gray.800" borderRadius="md">
          <StatLabel fontSize="xs" color="gray.400">Architecture</StatLabel>
          <HStack spacing={1} mt={1}>
            <Badge colorScheme="purple" fontSize="xs">{summary.variant}</Badge>
            <Badge colorScheme="gray" fontSize="xs">{summary.architecture}</Badge>
          </HStack>
        </Stat>
      </SimpleGrid>

      {/* Model Info */}
      <HStack spacing={2} flexWrap="wrap">
        <Text fontSize="xs" color="gray.500">Model:</Text>
        <Badge colorScheme="green" fontSize="xs">{summary.model}</Badge>
        {summary.fast_model && (
          <>
            <Text fontSize="xs" color="gray.500">Fast:</Text>
            <Badge colorScheme="purple" fontSize="xs">{summary.fast_model}</Badge>
          </>
        )}
      </HStack>

      {/* Error Banner */}
      {!summary.success && summary.error && (
        <Box p={3} bg="red.900" borderRadius="md">
          <Text color="red.200" fontSize="sm">{summary.error}</Text>
        </Box>
      )}

      {/* Calls Table */}
      {callSpans.length > 0 && (
        <Box overflowX="auto">
          <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th borderColor="gray.700" fontSize="xs">Step</Th>
                <Th borderColor="gray.700" fontSize="xs">Time</Th>
                <Th borderColor="gray.700" fontSize="xs">Chars</Th>
                <Th borderColor="gray.700" fontSize="xs" isNumeric></Th>
              </Tr>
            </Thead>
            <Tbody>
              {callSpans.map((span) => (
                <SpanRow
                  key={span.id}
                  span={span}
                  isExpanded={expandedSpans.has(span.id)}
                  onToggle={() => toggleSpan(span.id)}
                  formatTime={formatTime}
                  getKindColor={getKindColor}
                  getSpanLabel={getSpanLabel}
                />
              ))}
            </Tbody>
          </Table>
        </Box>
      )}

      {/* All spans timeline (collapsed by default) */}
      <SpansTimeline spans={spans} formatTime={formatTime} getKindColor={getKindColor} />
    </VStack>
  );
}

interface SpanRowProps {
  span: DebugSpan;
  isExpanded: boolean;
  onToggle: () => void;
  formatTime: (ms: number) => string;
  getKindColor: (kind: string) => string;
  getSpanLabel: (span: DebugSpan) => string;
}

function SpanRow({ span, isExpanded, onToggle, formatTime, getKindColor, getSpanLabel }: SpanRowProps) {
  const hasArtifacts = Object.keys(span.artifacts).length > 0;
  const promptChars = span.meta?.prompt_chars as number | undefined;
  const responseChars = span.meta?.response_chars as number | undefined;

  return (
    <>
      <Tr>
        <Td borderColor="gray.700">
          <HStack spacing={2}>
            <Badge colorScheme={getKindColor(span.kind)} fontSize="xs">
              {getSpanLabel(span)}
            </Badge>
            {span.kind === 'repair' && Array.isArray(span.meta?.issues) && (
              <Tooltip
                label={span.meta.issues.join(', ')}
                placement="top"
                hasArrow
              >
                <Badge colorScheme="red" fontSize="xs" cursor="help">
                  {span.meta.issues.length} issues
                </Badge>
              </Tooltip>
            )}
          </HStack>
        </Td>
        <Td borderColor="gray.700">
          <Badge colorScheme="blue" fontSize="xs">{formatTime(span.elapsed_ms)}</Badge>
        </Td>
        <Td borderColor="gray.700" fontSize="xs">
          {promptChars && responseChars ? (
            <Text color="gray.400">
              {formatChars(promptChars)} → {formatChars(responseChars)}
            </Text>
          ) : (
            <Text color="gray.600">—</Text>
          )}
        </Td>
        <Td borderColor="gray.700" isNumeric>
          {hasArtifacts && (
            <Button
              size="xs"
              variant="ghost"
              onClick={onToggle}
              rightIcon={isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
            >
              {isExpanded ? 'Hide' : 'Show'}
            </Button>
          )}
        </Td>
      </Tr>
      {hasArtifacts && (
        <Tr>
          <Td colSpan={4} borderColor="gray.700" p={0}>
            <Collapse in={isExpanded}>
              <ArtifactsPanel artifacts={span.artifacts} />
            </Collapse>
          </Td>
        </Tr>
      )}
    </>
  );
}

function formatChars(chars: number): string {
  if (chars >= 1000) {
    return `${(chars / 1000).toFixed(1)}k`;
  }
  return String(chars);
}

interface ArtifactsPanelProps {
  artifacts: Record<string, string>;
}

function ArtifactsPanel({ artifacts }: ArtifactsPanelProps) {
  return (
    <VStack align="stretch" spacing={2} p={3} bg="gray.900">
      {Object.entries(artifacts).map(([key, value]) => (
        <ArtifactBlock key={key} label={key} content={value} />
      ))}
    </VStack>
  );
}

interface ArtifactBlockProps {
  label: string;
  content: string;
}

function ArtifactBlock({ label, content }: ArtifactBlockProps) {
  const { hasCopied, onCopy } = useClipboard(content);
  const displayLabel = label.replace(/_/g, ' ');

  return (
    <Box>
      <HStack justify="space-between" mb={1}>
        <Text fontSize="xs" fontWeight="bold" color="gray.400" textTransform="capitalize">
          {displayLabel}
        </Text>
        <IconButton
          aria-label="Copy"
          icon={hasCopied ? <CheckIcon /> : <CopyIcon />}
          size="xs"
          variant="ghost"
          onClick={onCopy}
        />
      </HStack>
      <Box
        p={2}
        bg="gray.800"
        borderRadius="md"
        maxH="200px"
        overflowY="auto"
        fontFamily="monospace"
        fontSize="xs"
        whiteSpace="pre-wrap"
      >
        <Code colorScheme="gray" display="block" bg="transparent">
          {content}
        </Code>
      </Box>
    </Box>
  );
}

interface SpansTimelineProps {
  spans: DebugSpan[];
  formatTime: (ms: number) => string;
  getKindColor: (kind: string) => string;
}

function SpansTimeline({ spans, formatTime, getKindColor }: SpansTimelineProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (spans.length === 0) return null;

  // Sort by start time
  const sortedSpans = [...spans].sort((a, b) => a.start_ms - b.start_ms);

  return (
    <Box>
      <Button
        size="xs"
        variant="ghost"
        onClick={() => setIsExpanded(!isExpanded)}
        rightIcon={isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
        color="gray.500"
      >
        All spans ({spans.length})
      </Button>
      <Collapse in={isExpanded}>
        <VStack align="stretch" spacing={1} mt={2} pl={2} borderLeft="1px solid" borderColor="gray.700">
          {sortedSpans.map((span) => (
            <HStack key={span.id} spacing={2} fontSize="xs">
              <Text color="gray.500" minW="50px" textAlign="right">
                {formatTime(span.start_ms)}
              </Text>
              <Badge colorScheme={getKindColor(span.kind)} fontSize="xs">
                {span.name}
              </Badge>
              <Text color="gray.500">{formatTime(span.elapsed_ms)}</Text>
              {span.meta?.valid === false && (
                <Badge colorScheme="red" fontSize="xs">invalid</Badge>
              )}
            </HStack>
          ))}
        </VStack>
      </Collapse>
    </Box>
  );
}

