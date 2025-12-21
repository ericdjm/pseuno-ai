/**
 * Privacy Note Component
 */

import { Box, Text, HStack, Icon } from '@chakra-ui/react';
import { FaLock } from 'react-icons/fa';

export function PrivacyNote() {
  return (
    <Box
      p={4}
      bg="gray.800"
      borderRadius="md"
      borderColor="gray.700"
      borderWidth="1px"
    >
      <HStack spacing={3} align="start">
        <Icon as={FaLock} color="gray.500" mt={1} />
        <Text fontSize="sm" color="gray.400">
          <Text as="span" fontWeight="semibold" color="gray.300">
            Privacy:
          </Text>{' '}
          We only read your top artists and tracks to personalize prompts. Your
          data is not stored permanently and you can disconnect anytime from your{' '}
          <Text
            as="a"
            href="https://www.spotify.com/account/apps/"
            target="_blank"
            rel="noopener noreferrer"
            color="brand.400"
            _hover={{ textDecoration: 'underline' }}
          >
            Spotify account settings
          </Text>
          .
        </Text>
      </HStack>
    </Box>
  );
}
