import { useEffect, useRef } from 'react';
import { Textarea, type TextareaProps } from '@chakra-ui/react';

type AutoGrowTextareaProps = Omit<TextareaProps, 'rows' | 'resize'> & {
  minRows?: number;
  maxRows?: number;
};

function getNumericCssPx(value: string | null): number {
  if (!value) return 0;
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export default function AutoGrowTextarea({
  minRows = 1,
  maxRows = 4,
  value,
  ...props
}: AutoGrowTextareaProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Reset first so scrollHeight reflects current content.
    el.style.height = 'auto';

    const styles = window.getComputedStyle(el);
    const lineHeight = getNumericCssPx(styles.lineHeight) || 20;
    const paddingTop = getNumericCssPx(styles.paddingTop);
    const paddingBottom = getNumericCssPx(styles.paddingBottom);

    const minHeight = lineHeight * minRows + paddingTop + paddingBottom;
    const maxHeight = lineHeight * maxRows + paddingTop + paddingBottom;
    const nextHeight = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);

    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  }, [value, minRows, maxRows]);

  return (
    <Textarea
      ref={ref}
      value={value}
      resize="none"
      overflowY="hidden"
      bg="gray.800"
      borderColor="gray.700"
      borderRadius="lg"
      px={4}
      py={3}
      _hover={{ borderColor: 'gray.600' }}
      _focus={{ borderColor: 'gray.500', boxShadow: 'none' }}
      {...props}
    />
  );
}


