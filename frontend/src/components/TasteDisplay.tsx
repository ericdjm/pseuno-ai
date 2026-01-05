/**
 * Taste Display Component
 * Shows user's top artists, genres, and taste summary
 */

import { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  HStack,
  VStack,
  Tag,
  TagLabel,
  Wrap,
  WrapItem,
  Skeleton,
  SkeletonCircle,
  RadioGroup,
  Radio,
  Stack,
  Tooltip,
  Avatar,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useToast,
} from '@chakra-ui/react';
import { AddIcon, CloseIcon } from '@chakra-ui/icons';

import * as api from '../api';
import { SpotifyProfileResponse, TimeRange } from '../api';
import { TIME_RANGE_LABELS } from '../types';

interface TasteDisplayProps {
  profile: SpotifyProfileResponse | null;
  loading: boolean;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  onGenresUpdated?: (genres: string[]) => void;
  onProfileUpdated?: (profile: SpotifyProfileResponse) => void;
}

export function TasteDisplay({
  profile,
  loading,
  timeRange,
  onTimeRangeChange,
  onGenresUpdated,
  onProfileUpdated,
}: TasteDisplayProps) {
  const maxGenres = 20;
  const toast = useToast();
  const [genreCatalog, setGenreCatalog] = useState<api.GenreItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [genreActionLoading, setGenreActionLoading] = useState(false);

  useEffect(() => {
    let active = true;
    if (!profile) {
      setGenreCatalog([]);
      return;
    }
    setCatalogLoading(true);
    api
      .getGenreCatalog()
      .then((data) => {
        if (active) {
          setGenreCatalog(data.genres);
        }
      })
      .catch(() => {
        if (active) {
          setGenreCatalog([]);
        }
      })
      .finally(() => {
        if (active) {
          setCatalogLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [profile]);

  const genreIdByName = useMemo(() => {
    const map = new Map<string, number>();
    for (const genre of genreCatalog) {
      map.set(genre.name.toLowerCase(), genre.id);
    }
    return map;
  }, [genreCatalog]);

  const selectedCount = profile?.taste_profile.top_genres.length ?? 0;
  const availableGenres = useMemo(() => {
    const selected = new Set(
      (profile?.taste_profile.top_genres || []).map((name) => name.toLowerCase())
    );
    return genreCatalog.filter(
      (genre) => !selected.has(genre.name.toLowerCase())
    );
  }, [genreCatalog, profile]);

  const refreshProfile = async () => {
    if (!onProfileUpdated) {
      return;
    }
    try {
      const updatedProfile = await api.getProfile(timeRange);
      onProfileUpdated(updatedProfile);
    } catch (error) {
      toast({
        title: 'Could not refresh profile',
        description: 'Please try again.',
        status: 'error',
        duration: 3000,
      });
    }
  };

  const handleAddGenre = async (genre: api.GenreItem) => {
    if (genreActionLoading) {
      return;
    }
    if (selectedCount >= maxGenres) {
      toast({
        title: 'Genre limit reached',
        description: 'You can add up to 20 genres.',
        status: 'info',
        duration: 3000,
      });
      return;
    }
    setGenreActionLoading(true);
    try {
      const result = await api.addUserGenre(genre.id);
      onGenresUpdated?.(result.genres);
      await refreshProfile();
    } catch (error) {
      toast({
        title: 'Could not add genre',
        description: 'Please try again.',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setGenreActionLoading(false);
    }
  };

  const handleDeleteGenre = async (genreName: string) => {
    if (genreActionLoading) {
      return;
    }
    const genreId = genreIdByName.get(genreName.toLowerCase());
    if (!genreId) {
      toast({
        title: 'Genre not found',
        description: 'Refresh the page and try again.',
        status: 'warning',
        duration: 3000,
      });
      return;
    }
    setGenreActionLoading(true);
    try {
      const result = await api.deleteUserGenre(genreId);
      onGenresUpdated?.(result.genres);
      await refreshProfile();
    } catch (error) {
      toast({
        title: 'Could not remove genre',
        description: 'Please try again.',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setGenreActionLoading(false);
    }
  };

  return (
    <Card bg="gray.800" borderColor="gray.700" variant="outline">
      <CardHeader pb={2}>
        <HStack justify="space-between" align="start" wrap="wrap" gap={4}>
          <VStack align="start" spacing={1}>
            <Heading size="md">Your Music Taste</Heading>
            <Text color="gray.400" fontSize="sm">
              Based on your listening history
            </Text>
          </VStack>
          
          <RadioGroup
            value={timeRange}
            onChange={(val) => onTimeRangeChange(val as TimeRange)}
          >
            <Stack direction={{ base: 'column', sm: 'row' }} spacing={3}>
              {Object.entries(TIME_RANGE_LABELS).map(([value, label]) => (
                <Radio key={value} value={value} colorScheme="brand" size="sm">
                  {label}
                </Radio>
              ))}
            </Stack>
          </RadioGroup>
        </HStack>
      </CardHeader>
      
      <CardBody pt={4}>
        {loading ? (
          <LoadingSkeleton />
        ) : profile ? (
          <VStack spacing={6} align="stretch">
            {/* Summary */}
            <Box
              p={4}
              bg="gray.700"
              borderRadius="md"
              borderLeft="4px"
              borderColor="brand.500"
            >
              <Text fontStyle="italic" color="gray.200">
                {profile.taste_profile.summary_sentence}
              </Text>
            </Box>
            
            {/* Top Artists */}
            <Box>
              <Text fontWeight="semibold" mb={3} color="gray.300">
                Top Artists
              </Text>
              <Wrap spacing={2}>
                {profile.top_artists.slice(0, 10).map((artist, idx) => (
                  <WrapItem key={idx}>
                    <Tooltip
                      label={artist.genres.slice(0, 3).join(', ') || 'No genres'}
                      placement="top"
                    >
                      <HStack
                        bg="gray.700"
                        px={3}
                        py={2}
                        borderRadius="full"
                        spacing={2}
                        _hover={{ bg: 'gray.600' }}
                        cursor="pointer"
                        onClick={() => artist.spotify_url && window.open(artist.spotify_url, '_blank')}
                      >
                        <Avatar
                          size="xs"
                          src={artist.image_url || undefined}
                          name={artist.name}
                        />
                        <Text fontSize="sm">{artist.name}</Text>
                      </HStack>
                    </Tooltip>
                  </WrapItem>
                ))}
              </Wrap>
            </Box>
            
            {/* Top Genres */}
            <Box>
              <Text fontWeight="semibold" mb={3} color="gray.300">
                Top Genres
              </Text>
              <Wrap spacing={2}>
                {profile.taste_profile.top_genres.slice(0, maxGenres).map((genre, idx) => (
                  <WrapItem key={genre}>
                    <Box position="relative" display="inline-flex">
                      <Tag
                        size="md"
                        colorScheme={getGenreColor(idx)}
                        variant="subtle"
                        borderRadius="full"
                        pr={2}
                      >
                        <TagLabel>{genre}</TagLabel>
                      </Tag>
                      <IconButton
                        aria-label={`Remove ${genre}`}
                        icon={<CloseIcon boxSize="8px" />}
                        size="xs"
                        variant="solid"
                        colorScheme="gray"
                        boxSize="16px"
                        position="absolute"
                        top="-5px"
                        right="-5px"
                        borderRadius="full"
                        isDisabled={genreActionLoading}
                        onClick={() => handleDeleteGenre(genre)}
                      />
                    </Box>
                  </WrapItem>
                ))}
                <WrapItem>
                  <Menu>
                    <MenuButton
                      as={IconButton}
                      aria-label="Add genre"
                      icon={<AddIcon />}
                      size="sm"
                      variant="outline"
                      colorScheme="gray"
                      isLoading={catalogLoading || genreActionLoading}
                      isDisabled={
                        catalogLoading ||
                        genreActionLoading ||
                        availableGenres.length === 0 ||
                        selectedCount >= maxGenres
                      }
                    />
                    <MenuList maxH="260px" overflowY="auto">
                      {selectedCount >= maxGenres ? (
                        <MenuItem isDisabled>Max 20 genres reached</MenuItem>
                      ) : availableGenres.length === 0 ? (
                        <MenuItem isDisabled>No genres to add</MenuItem>
                      ) : (
                        availableGenres.map((genre) => (
                          <MenuItem
                            key={genre.id}
                            onClick={() => handleAddGenre(genre)}
                          >
                            {genre.name}
                          </MenuItem>
                        ))
                      )}
                    </MenuList>
                  </Menu>
                </WrapItem>
              </Wrap>
            </Box>
            
            {/* Mood Tags */}
            <Box>
              <Text fontWeight="semibold" mb={3} color="gray.300">
                Your Vibe
              </Text>
              <Wrap spacing={2}>
                {profile.taste_profile.mood_tags.map((mood, idx) => (
                  <WrapItem key={idx}>
                    <Tag
                      size="md"
                      colorScheme="purple"
                      variant="outline"
                      borderRadius="full"
                    >
                      {mood}
                    </Tag>
                  </WrapItem>
                ))}
              </Wrap>
            </Box>
          </VStack>
        ) : (
          <Text color="gray.500">No profile data available</Text>
        )}
      </CardBody>
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <VStack spacing={6} align="stretch">
      <Skeleton height="60px" borderRadius="md" />
      <Box>
        <Skeleton height="20px" width="100px" mb={3} />
        <HStack spacing={2}>
          {[1, 2, 3, 4, 5].map((i) => (
            <HStack key={i} bg="gray.700" px={3} py={2} borderRadius="full">
              <SkeletonCircle size="6" />
              <Skeleton height="14px" width="60px" />
            </HStack>
          ))}
        </HStack>
      </Box>
      <Box>
        <Skeleton height="20px" width="80px" mb={3} />
        <HStack spacing={2}>
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} height="24px" width="80px" borderRadius="full" />
          ))}
        </HStack>
      </Box>
    </VStack>
  );
}

function getGenreColor(index: number): string {
  const colors = ['green', 'blue', 'cyan', 'teal', 'orange', 'pink', 'purple', 'yellow'];
  return colors[index % colors.length];
}
