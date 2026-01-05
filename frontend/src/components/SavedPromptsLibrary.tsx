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
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { ChevronDownIcon, ChevronUpIcon, DeleteIcon, CopyIcon, StarIcon } from '@chakra-ui/icons';
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
  favoritesOnly?: boolean;
  showHeader?: boolean;
}

interface PromptCardProps {
  key?: number;
  prompt: SavedSunoPrompt;
  onDelete: (id: number) => void;
  onUpdate: (id: number, title: string) => void;
  onToggleFavorite: (id: number, isFavorite: boolean) => void;
  onReuse?: (prompt: SavedSunoPrompt) => void;
}

function PromptCard({ prompt, onDelete, onUpdate, onToggleFavorite, onReuse }: PromptCardProps) {
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
      borderColor={prompt.is_favorite ? 'yellow.600' : 'gray.700'}
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
          {/* Auto-tags */}
          {prompt.auto_tags && prompt.auto_tags.length > 0 && (
            <Wrap spacing={1} mt={1}>
              {prompt.auto_tags.slice(0, 5).map((tag, idx) => (
                <WrapItem key={idx}>
                  <Badge colorScheme="teal" fontSize="2xs" variant="subtle">
                    {tag}
                  </Badge>
                </WrapItem>
              ))}
            </Wrap>
          )}
        </VStack>
        <HStack spacing={1}>
          {onReuse && (
            <Button size="sm" variant="outline" onClick={() => onReuse(prompt)}>
              Reuse
            </Button>
          )}
          <IconButton
            aria-label={prompt.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
            icon={<StarIcon />}
            size="sm"
            variant="ghost"
            color={prompt.is_favorite ? 'yellow.400' : 'gray.500'}
            onClick={() => onToggleFavorite(prompt.id, !prompt.is_favorite)}
            _hover={{ color: prompt.is_favorite ? 'yellow.300' : 'yellow.400' }}
          />
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
  favoritesOnly = false,
  showHeader = true,
}: SavedPromptsLibraryProps) {
  const toast = useToast();
  const [prompts, setPrompts] = useState<SavedSunoPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const LIMIT = 50;

  const loadPrompts = async (loadMore = false) => {
    if (loadMore) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setOffset(0);
    }
    try {
      const newOffset = loadMore ? offset : 0;
      const data = await listSavedPrompts({
        limit: LIMIT,
        offset: newOffset,
        favoritesOnly,
      });
      if (loadMore) {
        const combined = [...prompts, ...data.prompts];
        setPrompts(combined);
        setOffset(newOffset + LIMIT);
        onPromptsLoaded?.(combined);
      } else {
        setPrompts(data.prompts);
        setOffset(LIMIT);
        onPromptsLoaded?.(data.prompts);
      }
      setTotal(data.total);
    } catch (e) {
      // 401 means no auth (new user) - treat as empty, not error
      if (e instanceof ApiError && e.status === 401) {
        setPrompts([]);
        setTotal(0);
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
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadPrompts();
  }, [refreshTrigger, favoritesOnly]);

  const handleDelete = async () => {
    if (deleteId === null) return;
    setDeleting(true);
    try {
      await deleteSavedPrompt(deleteId);
      const newPrompts = prompts.filter((p: SavedSunoPrompt) => p.id !== deleteId);
      setPrompts(newPrompts);
      setTotal((t) => Math.max(0, t - 1));
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

  const handleToggleFavorite = async (id: number, isFavorite: boolean) => {
    try {
      const updated = await updateSavedPrompt(id, { is_favorite: isFavorite });
      
      if (favoritesOnly && !isFavorite) {
        // Remove from list if we're in favorites-only mode and unfavoriting
        const newPrompts = prompts.filter((p) => p.id !== id);
        setPrompts(newPrompts);
        setTotal((t) => Math.max(0, t - 1));
        onPromptsLoaded?.(newPrompts);
      } else {
        // Update in place
        const newPrompts = prompts.map((p: SavedSunoPrompt) =>
          p.id === id ? { ...p, is_favorite: updated.is_favorite } : p
        );
        setPrompts(newPrompts);
        onPromptsLoaded?.(newPrompts);
      }

      toast({
        title: isFavorite ? 'Added to favorites' : 'Removed from favorites',
        status: 'success',
        duration: 2000,
      });
    } catch (e) {
      toast({
        title: 'Failed to update',
        status: 'error',
        duration: 4000,
      });
    }
  };

  const hasMore = prompts.length < total;

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
        <Text color="gray.500">
          {favoritesOnly ? 'No favorites yet.' : 'No prompts yet.'}
        </Text>
        <Text color="gray.600" fontSize="sm" mt={1}>
          {favoritesOnly
            ? 'Star a prompt to add it to your favorites.'
            : 'Generate a prompt to see it here.'}
        </Text>
      </Box>
    );
  }

  return (
    <Box>
      {showHeader && (
        <HStack justify="space-between" mb={4}>
          <Heading size="md">
            {favoritesOnly ? 'My Favorites' : 'Prompt History'}
          </Heading>
          <Badge colorScheme={favoritesOnly ? 'yellow' : 'green'}>
            {total} {favoritesOnly ? 'favorite' : 'prompt'}{total !== 1 ? 's' : ''}
          </Badge>
        </HStack>
      )}

      <VStack spacing={3} align="stretch">
        {prompts.map((prompt: SavedSunoPrompt) => (
          <PromptCard
            key={prompt.id}
            prompt={prompt}
            onDelete={setDeleteId}
            onUpdate={handleUpdate}
            onToggleFavorite={handleToggleFavorite}
            onReuse={onReuse}
          />
        ))}
      </VStack>

      {/* Load More button */}
      {hasMore && (
        <Center mt={4}>
          <Button
            size="sm"
            variant="outline"
            onClick={() => loadPrompts(true)}
            isLoading={loadingMore}
          >
            Load more ({total - prompts.length} remaining)
          </Button>
        </Center>
      )}

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
