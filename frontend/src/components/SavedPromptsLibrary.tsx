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
  Input,
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
} from '../api';

interface SavedPromptsLibraryProps {
  refreshTrigger?: number;
}

interface PromptCardProps {
  prompt: SavedSunoPrompt;
  onDelete: (id: number) => void;
  onUpdate: (id: number, title: string) => void;
}

function PromptCard({ prompt, onDelete, onUpdate }: PromptCardProps) {
  const { isOpen, onToggle } = useDisclosure();
  const toast = useToast();

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
            onSubmit={(value) => onUpdate(prompt.id, value)}
          >
            <EditablePreview />
            <EditableInput bg="gray.700" px={2} />
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
          <IconButton
            aria-label="Copy prompt"
            icon={<CopyIcon />}
            size="sm"
            variant="ghost"
            onClick={() => copyToClipboard(prompt.suno_prompt)}
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

export default function SavedPromptsLibrary({ refreshTrigger }: SavedPromptsLibraryProps) {
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
    } catch (e) {
      toast({
        title: 'Failed to load prompts',
        status: 'error',
        duration: 4000,
      });
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
      setPrompts((prev) => prev.filter((p) => p.id !== deleteId));
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
      setPrompts((prev) =>
        prev.map((p) => (p.id === id ? { ...p, title: updated.title } : p))
      );
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
        {prompts.map((prompt) => (
          <PromptCard
            key={prompt.id}
            prompt={prompt}
            onDelete={setDeleteId}
            onUpdate={handleUpdate}
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

