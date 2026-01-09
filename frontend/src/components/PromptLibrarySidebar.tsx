/**
 * PromptLibrarySidebar - Left panel showing StylePrompts with nested songs.
 * 
 * ChatGPT-style layout:
 * - New Song button
 * - Search Styles (expands to search bar on click)
 * - Your Songs / Favourites sections (collapsible)
 * - Profile at bottom
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Spinner,
  Collapse,
  useToast,
  Input,
  IconButton,
  Avatar,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
  Button,
} from '@chakra-ui/react';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  AddIcon,
  SearchIcon,
  DeleteIcon,
  CloseIcon,
  EditIcon,
} from '@chakra-ui/icons';
import { BsThreeDots, BsPinAngleFill } from 'react-icons/bs';
import { LuPanelLeftClose } from 'react-icons/lu';
import { FaSpotify } from 'react-icons/fa';
import {
  SavedSunoPrompt,
  LyricsThreadSummary,
  AuthStatus,
  listSavedPrompts,
  getPromptThreads,
  updateSavedPrompt,
  deleteSavedPrompt,
} from '../api';

interface PromptLibrarySidebarProps {
  refreshTrigger: number;
  activeStylePromptId: number | null;
  activeThreadId: number | null;
  onSelectStylePrompt: (prompt: SavedSunoPrompt, threads: LyricsThreadSummary[]) => void;
  onSelectThread: (prompt: SavedSunoPrompt, thread: LyricsThreadSummary) => void;
  onNewLyricsVariation: (prompt: SavedSunoPrompt) => void;
  onNewPrompt: () => void;
  onCloseSidebar: () => void;
  authStatus: AuthStatus;
  onLogin: () => void;
}

export default function PromptLibrarySidebar({
  refreshTrigger,
  activeStylePromptId,
  activeThreadId,
  onSelectStylePrompt,
  onSelectThread,
  onNewLyricsVariation,
  onNewPrompt,
  onCloseSidebar,
  authStatus,
  onLogin,
}: PromptLibrarySidebarProps) {
  const toast = useToast();
  const searchInputRef = useRef<HTMLInputElement>(null);

  // All prompts
  const [allPrompts, setAllPrompts] = useState<SavedSunoPrompt[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  

  // Expanded prompts (for showing threads)
  const [expandedPromptIds, setExpandedPromptIds] = useState<Set<number>>(new Set());
  // Threads cache: promptId -> threads
  const [threadsCache, setThreadsCache] = useState<Record<number, LyricsThreadSummary[]>>({});
  // Loading threads for specific prompt
  const [loadingThreadsFor, setLoadingThreadsFor] = useState<number | null>(null);
  // Toggling favorite
  const [togglingFavoriteId, setTogglingFavoriteId] = useState<number | null>(null);
  // Deleting prompt
  const [deletingPromptId, setDeletingPromptId] = useState<number | null>(null);
  // Delete confirmation
  const [promptToDelete, setPromptToDelete] = useState<SavedSunoPrompt | null>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);
  // Renaming prompt - track both ID and section to avoid duplicates
  const [renamingKey, setRenamingKey] = useState<string | null>(null); // "fav-123" or "all-123"
  const [renameValue, setRenameValue] = useState('');
  // Your songs section collapsed state
  const [yourSongsOpen, setYourSongsOpen] = useState(true);

  // Fetch all prompts (works for both Spotify-authenticated and guest users via device token)
  const fetchPrompts = useCallback(async () => {
    setLoading(true);
    try {
      const response = await listSavedPrompts({ limit: 100, favoritesOnly: false });
      // Sort with pinned items at top
      const sorted = [...response.prompts].sort((a, b) => {
        if (a.is_favorite && !b.is_favorite) return -1;
        if (!a.is_favorite && b.is_favorite) return 1;
        return 0;
      });
      setAllPrompts(sorted);
    } catch (err) {
      // 401 is expected for brand-new users without a device token yet - just show empty
      if (err instanceof Error && err.message.includes('401')) {
        setAllPrompts([]);
      } else {
        console.error('Failed to fetch prompts:', err);
        toast({
          title: 'Failed to load prompts',
          status: 'error',
          duration: 3000,
        });
      }
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchPrompts();
  }, [fetchPrompts, refreshTrigger]);

  // Focus search input when opened
  useEffect(() => {
    if (searchOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [searchOpen]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      // Command+K or Ctrl+K to open search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
      // Command+/ or Ctrl+/ to create new song
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        onNewPrompt();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onNewPrompt]);

  // Filter prompts by search query
  const filterBySearch = (prompts: SavedSunoPrompt[]) => {
    if (!searchQuery.trim()) return prompts;
    const q = searchQuery.toLowerCase();
    return prompts.filter((p) =>
      (p.title || '').toLowerCase().includes(q) ||
      p.suno_prompt.toLowerCase().includes(q) ||
      p.auto_tags.some((t) => t.toLowerCase().includes(q))
    );
  };

  // Apply search (list is already sorted with pinned at top)
  const filteredPrompts = filterBySearch(allPrompts);

  // Toggle expand for a prompt (only one can be expanded at a time)
  const handleToggleExpand = async (prompt: SavedSunoPrompt) => {
    if (expandedPromptIds.has(prompt.id)) {
      // Collapse this one
      setExpandedPromptIds(new Set());
    } else {
      // Expand this one, collapse all others
      setExpandedPromptIds(new Set([prompt.id]));
      // Fetch threads if not cached
      if (!threadsCache[prompt.id]) {
        setLoadingThreadsFor(prompt.id);
        try {
          const threads = await getPromptThreads(prompt.id);
          setThreadsCache((prev) => ({ ...prev, [prompt.id]: threads }));
        } catch (err) {
          console.error('Failed to fetch threads:', err);
        } finally {
          setLoadingThreadsFor(null);
        }
      }
    }
  };

  // Select a StylePrompt (load it + auto-select most recent thread if any)
  const handleSelectPrompt = async (prompt: SavedSunoPrompt) => {
    // Ensure threads are loaded
    let threads = threadsCache[prompt.id];
    if (!threads) {
      setLoadingThreadsFor(prompt.id);
      try {
        threads = await getPromptThreads(prompt.id);
        setThreadsCache((prev) => ({ ...prev, [prompt.id]: threads }));
      } catch (err) {
        console.error('Failed to fetch threads:', err);
        threads = [];
      } finally {
        setLoadingThreadsFor(null);
      }
    }
    // Expand this one, collapse all others
    setExpandedPromptIds(new Set([prompt.id]));
    // Notify parent
    onSelectStylePrompt(prompt, threads);
  };

  // Select a specific thread
  const handleSelectThread = (prompt: SavedSunoPrompt, thread: LyricsThreadSummary) => {
    onSelectThread(prompt, thread);
  };

  // Toggle pin (favorite)
  const handleToggleFavorite = async (e: React.MouseEvent, prompt: SavedSunoPrompt) => {
    e.stopPropagation();
    setTogglingFavoriteId(prompt.id);
    try {
      const updated = await updateSavedPrompt(prompt.id, {
        is_favorite: !prompt.is_favorite,
      });
      
      // Update list and reorder
      setAllPrompts((prev) => {
        const updatedPrompt = { ...prompt, is_favorite: updated.is_favorite };
        const others = prev.filter((p) => p.id !== prompt.id);
        
        if (updated.is_favorite) {
          // Pinning: move to the very top
          return [updatedPrompt, ...others];
        } else {
          // Unpinning: move to just after the last pinned item
          const pinned = others.filter((p) => p.is_favorite);
          const unpinned = others.filter((p) => !p.is_favorite);
          return [...pinned, updatedPrompt, ...unpinned];
        }
      });
    } catch (err) {
      console.error('Failed to toggle pin:', err);
      toast({
        title: 'Failed to update',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setTogglingFavoriteId(null);
    }
  };

  // Show delete confirmation
  const handleDeleteClick = (e: React.MouseEvent, prompt: SavedSunoPrompt) => {
    e.stopPropagation();
    setPromptToDelete(prompt);
  };

  // Actually delete prompt
  const handleConfirmDelete = async () => {
    if (!promptToDelete) return;
    setDeletingPromptId(promptToDelete.id);
    try {
      await deleteSavedPrompt(promptToDelete.id);
      // Remove from list
      setAllPrompts((prev) => prev.filter((p) => p.id !== promptToDelete.id));
      toast({
        title: 'Style deleted',
        status: 'success',
        duration: 2000,
      });
    } catch (err) {
      console.error('Failed to delete prompt:', err);
      toast({
        title: 'Failed to delete style',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setDeletingPromptId(null);
      setPromptToDelete(null);
    }
  };

  // Start renaming
  const handleStartRename = (e: React.MouseEvent, prompt: SavedSunoPrompt, section: 'fav' | 'all') => {
    e.stopPropagation();
    setRenamingKey(`${section}-${prompt.id}`);
    setRenameValue(prompt.title || '');
  };

  // Save rename
  const handleSaveRename = async (prompt: SavedSunoPrompt) => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === prompt.title) {
      setRenamingKey(null);
      return;
    }
    try {
      const updated = await updateSavedPrompt(prompt.id, { title: trimmed });
      // Update list
      setAllPrompts((prev) =>
        prev.map((p) => (p.id === prompt.id ? { ...p, title: updated.title } : p))
      );
    } catch (err) {
      console.error('Failed to rename:', err);
      toast({
        title: 'Failed to rename',
        status: 'error',
        duration: 2000,
      });
    } finally {
      setRenamingKey(null);
    }
  };

  // Render a single prompt item
  const renderPromptItem = (prompt: SavedSunoPrompt, section: 'fav' | 'all') => {
    const isExpanded = expandedPromptIds.has(prompt.id);
    const isActive = activeStylePromptId === prompt.id;
    const threads = threadsCache[prompt.id] || [];
    const isLoadingThreads = loadingThreadsFor === prompt.id;
    const itemKey = `${section}-${prompt.id}`;
    const isRenaming = renamingKey === itemKey;

    return (
      <Box key={itemKey} role="group">
        <HStack
          py={1.5}
          px={3}
          cursor={isRenaming ? 'default' : 'pointer'}
          bg={isActive ? 'gray.700' : 'transparent'}
          _hover={{ bg: 'gray.600' }}
          borderRadius="md"
          onClick={() => !isRenaming && handleSelectPrompt(prompt)}
          spacing={0}
        >
          {/* Chevron - appears on hover */}
          <Box
            w={0}
            overflow="visible"
            _groupHover={{ w: '16px' }}
            transition="width 0.1s"
            flexShrink={0}
            display="flex"
            alignItems="center"
          >
            <Box
              color="gray.500"
              cursor="pointer"
              opacity={0}
              _groupHover={{ opacity: 1 }}
              _hover={{ color: 'gray.300' }}
              transition="opacity 0.1s"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                if (!isRenaming) handleToggleExpand(prompt);
              }}
            >
              {isExpanded ? <ChevronDownIcon boxSize={3} /> : <ChevronRightIcon boxSize={3} />}
            </Box>
          </Box>
          {isRenaming ? (
            <Box flex={1} minW={0} onClick={(e) => e.stopPropagation()}>
              <Input
                size="sm"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveRename(prompt);
                  if (e.key === 'Escape') setRenamingKey(null);
                }}
                onBlur={() => handleSaveRename(prompt)}
                autoFocus
                variant="unstyled"
                bg="transparent"
                fontSize="sm"
                px={0}
                _selection={{ bg: 'blue.600' }}
              />
            </Box>
          ) : (
            <Text
              fontSize="sm"
              flex={1}
              minW={0}
              overflow="hidden"
              textOverflow="ellipsis"
              whiteSpace="nowrap"
            >
              {prompt.title || 'Untitled'}
            </Text>
          )}
          {/* Right side: Pin icon (visible if pinned) / Menu (on hover) - always rendered for consistent spacing */}
          <Box
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
            flexShrink={0}
            w="24px"
            h="24px"
            mr={-1}
            display={isRenaming ? 'none' : 'flex'}
            alignItems="center"
            justifyContent="center"
            position="relative"
          >
              {/* Pin icon - visible when pinned and not hovering */}
              {prompt.is_favorite && (
                <Box
                  position="absolute"
                  opacity={1}
                  _groupHover={{ opacity: 0 }}
                  transition="opacity 0.1s"
                  color="gray.400"
                >
                  <BsPinAngleFill size={12} />
                </Box>
              )}
              {/* Three-dot menu - visible on hover */}
              <Box
                opacity={0}
                _groupHover={{ opacity: 1 }}
                transition="opacity 0.1s"
              >
                <Menu placement="right-start" gutter={4} strategy="fixed">
                  <MenuButton
                    as={IconButton}
                    icon={<BsThreeDots />}
                    variant="ghost"
                    size="xs"
                    color="gray.400"
                    _hover={{ color: 'white', bg: 'gray.600' }}
                    aria-label="Options"
                  />
                  <MenuList bg="gray.700" borderColor="gray.600" minW="150px">
                    <MenuItem
                      icon={<AddIcon boxSize={3} color="gray.400" />}
                      onClick={(e) => {
                        e.stopPropagation();
                        onNewPrompt();
                      }}
                      bg="gray.700"
                      _hover={{ bg: 'gray.600' }}
                      fontSize="sm"
                    >
                      New song
                    </MenuItem>
                    <MenuItem
                      icon={isExpanded ? <ChevronDownIcon boxSize={3} color="gray.400" /> : <ChevronRightIcon boxSize={3} color="gray.400" />}
                      onClick={(e) => {
                        e.stopPropagation();
                        // Delay state update so menu closes before text changes
                        setTimeout(() => handleToggleExpand(prompt), 0);
                      }}
                      bg="gray.700"
                      _hover={{ bg: 'gray.600' }}
                      fontSize="sm"
                    >
                      {isExpanded ? 'Collapse songs' : 'Expand songs'}
                    </MenuItem>
                    <MenuItem
                      icon={togglingFavoriteId === prompt.id ? <Spinner size="xs" /> : <BsPinAngleFill color={prompt.is_favorite ? '#A0AEC0' : '#A0AEC0'} />}
                      onClick={(e) => handleToggleFavorite(e, prompt)}
                      bg="gray.700"
                      _hover={{ bg: 'gray.600' }}
                      fontSize="sm"
                    >
                      {prompt.is_favorite ? 'Unpin style' : 'Pin style'}
                    </MenuItem>
                    <MenuItem
                      icon={<EditIcon boxSize={3} color="gray.400" />}
                      onClick={(e) => handleStartRename(e, prompt, section)}
                      bg="gray.700"
                      _hover={{ bg: 'gray.600' }}
                      fontSize="sm"
                    >
                      Rename
                    </MenuItem>
                    <MenuItem
                      icon={<DeleteIcon boxSize={3} color="red.400" />}
                      onClick={(e) => handleDeleteClick(e, prompt)}
                      bg="gray.700"
                      _hover={{ bg: 'gray.600' }}
                      color="red.400"
                      fontSize="sm"
                    >
                      Delete
                    </MenuItem>
                  </MenuList>
                </Menu>
              </Box>
            </Box>
        </HStack>

        {/* Expanded: Songs list */}
        <Collapse in={isExpanded} animateOpacity>
          <Box pl={5} py={1}>
            {isLoadingThreads ? (
              <Spinner size="xs" color="gray.500" />
            ) : threads.length === 0 ? (
              <HStack
                py={1}
                px={2}
                borderRadius="sm"
                cursor="pointer"
                color="gray.500"
                _hover={{ bg: 'gray.700', color: 'gray.300' }}
                onClick={(e) => {
                  e.stopPropagation();
                  onNewLyricsVariation(prompt);
                }}
                fontSize="xs"
              >
                <AddIcon boxSize={2} />
                <Text>New song</Text>
              </HStack>
            ) : (
              <VStack spacing={0} align="stretch">
                {threads.map((thread) => {
                  const isThreadActive = activeThreadId === thread.id;
                  return (
                    <HStack
                      key={thread.id}
                      py={1}
                      px={2}
                      bg={isThreadActive ? 'gray.600' : 'transparent'}
                      borderRadius="sm"
                      cursor="pointer"
                      _hover={{ bg: isThreadActive ? 'gray.600' : 'gray.700' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectThread(prompt, thread);
                      }}
                    >
                      <Text fontSize="xs" flex={1} noOfLines={1} color={isThreadActive ? 'white' : 'gray.400'}>
                        {thread.title || 'Untitled Song'}
                      </Text>
                    </HStack>
                  );
                })}
                <HStack
                  py={1}
                  px={2}
                  borderRadius="sm"
                  cursor="pointer"
                  color="gray.500"
                  _hover={{ bg: 'gray.700', color: 'gray.300' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onNewLyricsVariation(prompt);
                  }}
                  fontSize="xs"
                >
                  <AddIcon boxSize={2} />
                  <Text>New song</Text>
                </HStack>
              </VStack>
            )}
          </Box>
        </Collapse>
      </Box>
    );
  };

  return (
    <Box
      w="280px"
      minW="280px"
      flexShrink={0}
      h="100%"
      maxH="100%"
      bg="gray.800"
      borderRight="1px solid"
      borderColor="gray.700"
      display="flex"
      flexDirection="column"
      overflow="hidden"
    >
      {/* Top: Logo + Close button */}
      <HStack py={2} px={2} justify="space-between">
        <Text
          fontSize="sm"
          fontWeight="bold"
          letterSpacing="widest"
          color="gray.500"
          pl={3}
        >
          PSEUNO
        </Text>
        <IconButton
          aria-label="Close sidebar"
          icon={<LuPanelLeftClose />}
          size="sm"
          variant="ghost"
          color="gray.400"
          _hover={{ color: 'white', bg: 'gray.700' }}
          onClick={onCloseSidebar}
        />
      </HStack>

      {/* Menu Items */}
      <VStack spacing={0} align="stretch" px={2} pb={2}>
        {/* New Song */}
        <HStack
          py={2.5}
          px={3}
          borderRadius="md"
          cursor="pointer"
          _hover={{ bg: 'gray.700' }}
          onClick={onNewPrompt}
          role="group"
        >
          <AddIcon boxSize={4} color="gray.400" />
          <Text fontSize="sm" flex={1}>New Song</Text>
          <Text fontSize="xs" color="gray.500" opacity={0} _groupHover={{ opacity: 1 }} transition="opacity 0.1s" flexShrink={0} w="30px" textAlign="right">⌘/</Text>
        </HStack>

        {/* Search Styles */}
        {searchOpen ? (
          <HStack py={1} px={1}>
            <Input
              ref={searchInputRef}
              placeholder="Search styles..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  setSearchOpen(false);
                  setSearchQuery('');
                }
              }}
              size="sm"
              bg="gray.900"
              border="1px solid"
              borderColor="gray.600"
              borderRadius="md"
              _focus={{ borderColor: 'blue.400' }}
            />
            <IconButton
              aria-label="Close search"
              icon={<CloseIcon boxSize={2} />}
              size="sm"
              variant="ghost"
              color="gray.400"
              onClick={() => {
                setSearchOpen(false);
                setSearchQuery('');
              }}
            />
          </HStack>
        ) : (
          <HStack
            py={2.5}
            px={3}
            borderRadius="md"
            cursor="pointer"
            _hover={{ bg: 'gray.700' }}
            onClick={() => setSearchOpen(true)}
            role="group"
          >
            <SearchIcon boxSize={4} color="gray.400" />
            <Text fontSize="sm" flex={1}>Search Styles</Text>
            <Text fontSize="xs" color="gray.500" opacity={0} _groupHover={{ opacity: 1 }} transition="opacity 0.1s" flexShrink={0} w="40px" textAlign="right">⌘K</Text>
          </HStack>
        )}
      </VStack>


      {/* Scrollable content */}
      <Box flex={1} overflowY="auto" px={2} py={1}>
        {loading ? (
          <Box textAlign="center" py={8}>
            <Spinner size="lg" color="blue.400" />
          </Box>
        ) : (
          <>
            {/* Your songs header */}
            <HStack
              py={1.5}
              px={3}
              cursor="pointer"
              onClick={() => setYourSongsOpen(!yourSongsOpen)}
              _hover={{ bg: 'gray.700' }}
              borderRadius="md"
            >
              {yourSongsOpen ? (
                <ChevronDownIcon boxSize={3} color="gray.500" />
              ) : (
                <ChevronRightIcon boxSize={3} color="gray.500" />
              )}
              <Text fontSize="xs" color="gray.500" fontWeight="medium">
                Your styles
              </Text>
            </HStack>

            <Collapse in={yourSongsOpen} animateOpacity>
              {filteredPrompts.length === 0 ? (
                <Box px={3} py={6} color="gray.500" fontSize="sm" textAlign="center">
                  <Text>No songs yet</Text>
                  <Text fontSize="xs" mt={1}>Generate your first song!</Text>
                </Box>
              ) : (
                <VStack spacing={0} align="stretch">
                  {filteredPrompts.map((p) => renderPromptItem(p, 'all'))}
                </VStack>
              )}
            </Collapse>
          </>
        )}
      </Box>

      {/* Bottom: Profile */}
      <Box p={3} borderTop="1px solid" borderColor="gray.700">
        {authStatus.authenticated ? (
          <HStack spacing={3}>
            <Avatar
              size="sm"
              src={authStatus.user_image || undefined}
              name={authStatus.user_name || undefined}
            />
            <VStack spacing={0} align="start" flex={1}>
              <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
                {authStatus.user_name}
              </Text>
              <HStack spacing={1}>
                <FaSpotify color="#1DB954" size={10} />
                <Text fontSize="xs" color="gray.400">Connected</Text>
              </HStack>
            </VStack>
          </HStack>
        ) : (
          <HStack
            spacing={3}
            cursor="pointer"
            onClick={onLogin}
            p={2}
            borderRadius="md"
            _hover={{ bg: 'gray.700' }}
          >
            <Box
              w={8}
              h={8}
              borderRadius="full"
              bg="green.600"
              display="flex"
              alignItems="center"
              justifyContent="center"
            >
              <FaSpotify color="white" size={16} />
            </Box>
            <Text fontSize="sm" color="gray.300">Connect Spotify</Text>
          </HStack>
        )}
      </Box>

      {/* Delete Confirmation Dialog */}
      <AlertDialog
        isOpen={promptToDelete !== null}
        leastDestructiveRef={cancelDeleteRef}
        onClose={() => setPromptToDelete(null)}
        isCentered
      >
        <AlertDialogOverlay
          bg="blackAlpha.600"
          backdropFilter="blur(2px)"
          sx={{
            paddingLeft: '280px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <AlertDialogContent bg="gray.800" borderColor="gray.600" margin="0">
            <AlertDialogHeader fontSize="lg" fontWeight="bold" color="white">
              Delete Style
            </AlertDialogHeader>

            <AlertDialogBody color="gray.300">
              Are you sure you want to delete "{promptToDelete?.title || 'Untitled'}"? This action cannot be undone.
            </AlertDialogBody>

            <AlertDialogFooter>
              <Button
                ref={cancelDeleteRef}
                onClick={() => setPromptToDelete(null)}
                variant="ghost"
                color="gray.300"
                _hover={{ bg: 'gray.700' }}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleConfirmDelete}
                ml={3}
                isLoading={deletingPromptId === promptToDelete?.id}
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

