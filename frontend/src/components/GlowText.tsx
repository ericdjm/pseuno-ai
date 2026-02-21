import { Text, type TextProps } from '@chakra-ui/react';
import { keyframes } from '@emotion/react';

const glowSweep = keyframes`
  0% { background-position: -150% center; }
  100% { background-position: 250% center; }
`;

/**
 * Text with a left-to-right glow sweep animation.
 * A brighter highlight moves across the characters continuously.
 */
export function GlowText({ children, ...props }: TextProps) {
  return (
    <Text
      {...props}
      as="span"
      sx={{
        background:
          'linear-gradient(90deg, currentColor 0%, currentColor 35%, rgba(255,255,255,0.95) 50%, currentColor 65%, currentColor 100%)',
        backgroundSize: '200% 100%',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        animation: `${glowSweep} 2s ease-in-out infinite`,
      }}
    >
      {children}
    </Text>
  );
}
