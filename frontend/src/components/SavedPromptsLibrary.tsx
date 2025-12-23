import { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  useToast,
  Heading,
  IconButton,
  Badge,
  Collapse,
  useDisclosure,
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogBody,
  AlertDialogFooter,
  Spinner,
  Center,
  Editable,
  EditableInput,
  EditablePreview,
} from '@chakra-ui/react';
import { ChevronDownIcon, ChevronUpIcon, DeleteIcon, CopyIcon } from '@chakra-ui/icons';
import { useRef } from 'react';
import {
  SavedSunoPrompt,
  listSavedPrompts,
  deleteSavedPrompt,
  updateSavedPrompt,
  ApiError,
} from '../api';

interface SavedPromptsLibraryProps {
  refreshTrigger?: number;
  onReuse?: (prompt: SavedSunoPrompt) => void;
  onPromptsLoaded?: (prompts: SavedSunoPrompt[]) => void;
}

interface PromptCardProps {
  key?: number;
  prompt: SavedSunoPrompt;
  onDelete: (id: number) => void;
  onUpdate: (id: number, title: string) => void;
  onReuse?: (prompt: SavedSunoPrompt) => void;
}

function PromptCard({ prompt, onDelete, onUpdate, onReuse }: PromptCardProps) {
  const { isOpen, onToggle } = useDisclosure();
  const toast = useToast();

  const MAX_TITLE_LEN = 255;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: 'Prompt copied!',
      status: 'success',
      duration: 2000,
    });
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const copyPromptOnly = () => {
    const sunoPrompt =
      prompt.suno_prompt.length > 500
        ? prompt.suno_prompt.slice(0, 500)
        : prompt.suno_prompt;

    if (prompt.suno_prompt.length > 500) {
      toast({
        title: 'Prompt truncated to 500 characters',
        description: 'Suno prompts must be 500 characters or less.',
        status: 'info',
        duration: 3000,
      });
    }

    copyToClipboard(sunoPrompt);
  };

  return (
    <Box
      bg="gray.800"
      borderRadius="md"
      p={4}
      borderWidth="1px"
      borderColor="gray.700"
    >
      <HStack justify="space-between" align="start">
        <VStack align="start" spacing={1} flex={1}>
          <Editable
            defaultValue={prompt.title || 'Untitled'}
            fontSize="lg"
            fontWeight="semibold"
            onSubmit={(value: string) => onUpdate(prompt.id, value.slice(0, MAX_TITLE_LEN))}
          >
            <EditablePreview />
            <EditableInput bg="gray.700" px={2} maxLength={MAX_TITLE_LEN} />
          </Editable>
          <HStack spacing={2} flexWrap="wrap">
            <Badge colorScheme="blue" fontSize="xs">
              Weirdness: {prompt.weirdness}%
            </Badge>
            <Badge colorScheme="purple" fontSize="xs">
              Style: {prompt.style_influence}%
            </Badge>
            <Text fontSize="xs" color="gray.500">
              {formatDate(prompt.created_at)}
            </Text>
          </HStack>
        </VStack>
        <HStack spacing={1}>
          {onReuse && (
            <Button size="sm" variant="outline" onClick={() => onReuse(prompt)}>
              Reuse
            </Button>
          )}
          <IconButton
            aria-label="Copy prompt"
            icon={<CopyIcon />}
            size="sm"
            variant="ghost"
            onClick={copyPromptOnly}
          />
          <IconButton
            aria-label="Delete prompt"
            icon={<DeleteIcon />}
            size="sm"
            variant="ghost"
            colorScheme="red"
            onClick={() => onDelete(prompt.id)}
          />
          <IconButton
            aria-label={isOpen ? 'Collapse' : 'Expand'}
            icon={isOpen ? <ChevronUpIcon /> : <ChevronDownIcon />}
            size="sm"
            variant="ghost"
            onClick={onToggle}
          />
        </HStack>
      </HStack>

      <Collapse in={isOpen} animateOpacity>
        <Box mt={4}>
          <Text fontSize="sm" fontWeight="medium" mb={2} color="gray.400">
            Prompt Content:
          </Text>
          <Box
            p={3}
            bg="gray.900"
            borderRadius="md"
            fontSize="sm"
            fontFamily="monospace"
            whiteSpace="pre-wrap"
            maxH="200px"
            overflowY="auto"
          >
            {prompt.suno_prompt}
          </Box>
          {prompt.exclude && (
            <>
              <Text fontSize="sm" fontWeight="medium" mt={3} mb={1} color="gray.400">
                Exclude:
              </Text>
              <Text fontSize="sm" color="gray.300">
                {prompt.exclude}
              </Text>
            </>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}

export default function SavedPromptsLibrary({
  refreshTrigger,
  onReuse,
  onPromptsLoaded,
}: SavedPromptsLibraryProps) {
  const toast = useToast();
  const [prompts, setPrompts] = useState<SavedSunoPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const loadPrompts = async () => {
    setLoading(true);
    try {
      const data = await listSavedPrompts();
      setPrompts(data.prompts);
      onPromptsLoaded?.(data.prompts);
    } catch (e) {
      // 401 means no auth (new user) - treat as empty, not error
      if (e instanceof ApiError && e.status === 401) {
        setPrompts([]);
        onPromptsLoaded?.([]);
      } else {
        toast({
          title: 'Failed to load prompts',
          status: 'error',
          duration: 4000,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, [refreshTrigger]);

  const handleDelete = async () => {
    if (deleteId === null) return;
    setDeleting(true);
    try {
      await deleteSavedPrompt(deleteId);
      const newPrompts = prompts.filter((p: SavedSunoPrompt) => p.id !== deleteId);
      setPrompts(newPrompts);
      onPromptsLoaded?.(newPrompts);
      toast({
        title: 'Prompt deleted',
        status: 'success',
        duration: 2000,
      });
    } catch (e) {
      toast({
        title: 'Failed to delete',
        status: 'error',
        duration: 4000,
      });
    } finally {
      setDeleting(false);
      setDeleteId(null);
    }
  };

  const handleUpdate = async (id: number, title: string) => {
    try {
      const updated = await updateSavedPrompt(id, { title });
      const newPrompts = prompts.map((p: SavedSunoPrompt) =>
        p.id === id ? { ...p, title: updated.title } : p
      );
      setPrompts(newPrompts);
      onPromptsLoaded?.(newPrompts);
    } catch (e) {
      toast({
        title: 'Failed to update',
        status: 'error',
        duration: 4000,
      });
    }
  };

  if (loading) {
    return (
      <Center py={8}>
        <Spinner size="lg" />
      </Center>
    );
  }

  if (prompts.length === 0) {
    return (
      <Box textAlign="center" py={8}>
        <Text color="gray.500">No saved prompts yet.</Text>
        <Text color="gray.600" fontSize="sm" mt={1}>
          Generate a prompt and click "Save" to add it to your library.
        </Text>
      </Box>
    );
  }

  return (
    <Box>
      <HStack justify="space-between" mb={4}>
        <Heading size="md">My Saved Prompts</Heading>
        <Badge colorScheme="green">{prompts.length} saved</Badge>
      </HStack>

      <VStack spacing={3} align="stretch">
        {prompts.map((prompt: SavedSunoPrompt) => (
          <PromptCard
            key={prompt.id}
            prompt={prompt}
            onDelete={setDeleteId}
            onUpdate={handleUpdate}
            onReuse={onReuse}
          />
        ))}
      </VStack>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={deleteId !== null}
        leastDestructiveRef={cancelRef}
        onClose={() => setDeleteId(null)}
        isCentered
      >
        <AlertDialogOverlay>
          <AlertDialogContent bg="gray.800">
            <AlertDialogHeader>Delete Prompt?</AlertDialogHeader>
            <AlertDialogBody>
              This action cannot be undone. The prompt will be permanently deleted.
            </AlertDialogBody>
            <AlertDialogFooter>
              <Button ref={cancelRef} onClick={() => setDeleteId(null)}>
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleDelete}
                ml={3}
                isLoading={deleting}
              >
                Delete
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialogOverlay>
      </AlertDialog>
    </Box>
  );
}
