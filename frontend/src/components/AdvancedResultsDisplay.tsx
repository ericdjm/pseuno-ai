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
  Code,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from '@chakra-ui/react';
import { CopyIcon, StarIcon } from '@chakra-ui/icons';
import { AdvancedGenerateResponse, createSavedPrompt } from '../api';

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
                    Debug Info
                  </Text>
                  <HStack spacing={2}>
                    {result.debug_info.elapsed_seconds && (
                      <Badge colorScheme="blue" fontSize="xs">
                        {result.debug_info.elapsed_seconds}s
                      </Badge>
                    )}
                    {result.debug_info.variant && (
                      <Badge colorScheme="purple" fontSize="xs">
                        {result.debug_info.variant}
                      </Badge>
                    )}
                    {result.debug_info.model && (
                      <Badge colorScheme="green" fontSize="xs">
                        {result.debug_info.model}
                      </Badge>
                    )}
                    <AccordionIcon />
                  </HStack>
                </HStack>
              </AccordionButton>
              <AccordionPanel pb={4} px={0}>
                <DebugInfoPanel debugInfo={result.debug_info} />
              </AccordionPanel>
            </AccordionItem>
          </Accordion>
        </>
      )}
    </VStack>
  );
}

interface DebugInfoPanelProps {
  debugInfo: Record<string, any>;
}

function DebugInfoPanel({ debugInfo }: DebugInfoPanelProps) {
  const styleBranch = debugInfo.style_branch;
  const lyricsBranch = debugInfo.lyrics_branch;
  const hasParallelBranches = styleBranch && lyricsBranch;
  const singleStepGeneration = debugInfo.generation;

  if (!hasParallelBranches && singleStepGeneration) {
    // Single-step variant (V1/V2) - show generation details
    return (
      <Tabs size="sm" variant="enclosed" colorScheme="gray">
        <TabList>
          <Tab fontSize="xs">
            Generation
            {singleStepGeneration?.elapsed_ms && (
              <Badge ml={2} colorScheme="blue" fontSize="xs">
                {singleStepGeneration.elapsed_ms}ms
              </Badge>
            )}
          </Tab>
          {singleStepGeneration?.repairs?.length > 0 && (
            <Tab fontSize="xs">
              Repairs ({singleStepGeneration.repairs.length})
            </Tab>
          )}
        </TabList>
        <TabPanels>
          <TabPanel p={2}>
            <BranchDebugPanel branch={singleStepGeneration} />
          </TabPanel>
          {singleStepGeneration?.repairs?.length > 0 && (
            <TabPanel p={2}>
              <VStack align="stretch" spacing={2}>
                {singleStepGeneration.repairs.map((repair: any, idx: number) => (
                  <Box key={idx} p={2} bg="orange.900" borderRadius="md">
                    <HStack justify="space-between">
                      <Text color="orange.200" fontSize="xs">
                        Attempt {repair.attempt}: {repair.issues?.join(', ')}
                      </Text>
                      {repair.elapsed_ms && (
                        <Badge colorScheme="orange" fontSize="xs">{repair.elapsed_ms}ms</Badge>
                      )}
                    </HStack>
                  </Box>
                ))}
              </VStack>
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>
    );
  }

  if (!hasParallelBranches) {
    // Fallback - just show raw debug info
    return (
      <Box
        p={3}
        bg="gray.900"
        borderRadius="md"
        fontSize="xs"
        fontFamily="monospace"
        overflowX="auto"
        whiteSpace="pre-wrap"
      >
        <Code colorScheme="gray" display="block" p={2}>
          {JSON.stringify(debugInfo, null, 2)}
        </Code>
      </Box>
    );
  }

  // Two-step variant with parallel branches
  return (
    <Tabs size="sm" variant="enclosed" colorScheme="gray">
      <TabList>
        <Tab fontSize="xs">
          Style Branch
          {styleBranch?.elapsed_ms && (
            <Badge ml={2} colorScheme="blue" fontSize="xs">
              {styleBranch.elapsed_ms}ms
            </Badge>
          )}
        </Tab>
        <Tab fontSize="xs">
          Lyrics Branch
          {lyricsBranch?.elapsed_ms && (
            <Badge ml={2} colorScheme="blue" fontSize="xs">
              {lyricsBranch.elapsed_ms}ms
            </Badge>
          )}
        </Tab>
        {debugInfo.lyric_profile && (
          <Tab fontSize="xs">Lyric Profile</Tab>
        )}
      </TabList>
      <TabPanels>
        <TabPanel p={2}>
          <BranchDebugPanel branch={styleBranch} />
        </TabPanel>
        <TabPanel p={2}>
          <BranchDebugPanel branch={lyricsBranch} />
        </TabPanel>
        {debugInfo.lyric_profile && (
          <TabPanel p={2}>
            <Box
              p={3}
              bg="gray.900"
              borderRadius="md"
              fontSize="xs"
              fontFamily="monospace"
            >
              <Code colorScheme="gray" display="block" p={2}>
                {JSON.stringify(debugInfo.lyric_profile, null, 2)}
              </Code>
            </Box>
          </TabPanel>
        )}
      </TabPanels>
    </Tabs>
  );
}

interface BranchDebugPanelProps {
  branch: Record<string, any>;
}

function BranchDebugPanel({ branch }: BranchDebugPanelProps) {
  if (!branch) return <Text fontSize="xs" color="gray.500">No data</Text>;

  return (
    <VStack align="stretch" spacing={3} fontSize="xs">
      {/* System Prompt */}
      {branch.system_prompt && (
        <Box>
          <Text fontWeight="bold" color="gray.400" mb={1}>System Prompt</Text>
          <Box
            p={2}
            bg="gray.900"
            borderRadius="md"
            fontFamily="monospace"
            maxH="200px"
            overflowY="auto"
            whiteSpace="pre-wrap"
            fontSize="xs"
          >
            {branch.system_prompt}
          </Box>
        </Box>
      )}

      {/* User Message */}
      {branch.user_message && (
        <Box>
          <Text fontWeight="bold" color="gray.400" mb={1}>User Message</Text>
          <Box
            p={2}
            bg="gray.900"
            borderRadius="md"
            fontFamily="monospace"
            maxH="150px"
            overflowY="auto"
            whiteSpace="pre-wrap"
          >
            {branch.user_message}
          </Box>
        </Box>
      )}

      {/* Raw Response */}
      {branch.raw_response && (
        <Box>
          <Text fontWeight="bold" color="gray.400" mb={1}>Raw Response</Text>
          <Box
            p={2}
            bg="gray.900"
            borderRadius="md"
            fontFamily="monospace"
            maxH="200px"
            overflowY="auto"
            whiteSpace="pre-wrap"
          >
            {branch.raw_response}
          </Box>
        </Box>
      )}

      {/* Repairs */}
      {branch.repairs && branch.repairs.length > 0 && (
        <Box>
          <Text fontWeight="bold" color="orange.400" mb={1}>
            Repairs ({branch.repairs.length})
          </Text>
          {branch.repairs.map((repair: any, idx: number) => (
            <Box key={idx} p={2} bg="orange.900" borderRadius="md" mb={2}>
              <HStack justify="space-between">
                <Text color="orange.200">Attempt {repair.attempt}: {repair.issues?.join(', ')}</Text>
                {repair.elapsed_ms && (
                  <Badge colorScheme="orange" fontSize="xs">{repair.elapsed_ms}ms</Badge>
                )}
              </HStack>
              <Box
                mt={1}
                p={2}
                bg="gray.900"
                borderRadius="md"
                fontFamily="monospace"
                maxH="100px"
                overflowY="auto"
                whiteSpace="pre-wrap"
              >
                {repair.output}
              </Box>
            </Box>
          ))}
        </Box>
      )}

      {/* Profile Inference (for lyrics branch) */}
      {branch.profile_inference && (
        <Box>
          <Text fontWeight="bold" color="purple.400" mb={1}>
            Profile Inference
            {branch.profile_inference.elapsed_ms && (
              <Badge ml={2} colorScheme="purple" fontSize="xs">
                {branch.profile_inference.elapsed_ms}ms
              </Badge>
            )}
          </Text>
          <Box p={2} bg="purple.900" borderRadius="md">
            <Text color="purple.200" fontSize="xs" mb={1}>
              Model: {branch.profile_inference.model}
            </Text>
            {branch.profile_inference.raw_response && (
              <Box
                p={2}
                bg="gray.900"
                borderRadius="md"
                fontFamily="monospace"
                whiteSpace="pre-wrap"
              >
                {branch.profile_inference.raw_response}
              </Box>
            )}
          </Box>
        </Box>
      )}
    </VStack>
  );
}
