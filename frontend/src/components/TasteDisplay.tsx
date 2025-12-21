/**
 * Taste Display Component
 * Shows user's top artists, genres, and taste summary
 */

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
  Wrap,
  WrapItem,
  Skeleton,
  SkeletonCircle,
  RadioGroup,
  Radio,
  Stack,
  Tooltip,
  Avatar,
} from '@chakra-ui/react';

import { SpotifyProfileResponse, TimeRange } from '../api';
import { TIME_RANGE_LABELS } from '../types';

interface TasteDisplayProps {
  profile: SpotifyProfileResponse | null;
  loading: boolean;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
}

export function TasteDisplay({
  profile,
  loading,
  timeRange,
  onTimeRangeChange,
}: TasteDisplayProps) {
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
                {profile.taste_profile.top_genres.slice(0, 8).map((genre, idx) => (
                  <WrapItem key={idx}>
                    <Tag
                      size="md"
                      colorScheme={getGenreColor(idx)}
                      variant="subtle"
                      borderRadius="full"
                    >
                      {genre}
                    </Tag>
                  </WrapItem>
                ))}
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
