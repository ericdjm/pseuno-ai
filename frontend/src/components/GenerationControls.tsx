/**
 * Generation Controls Component
 * Sliders, presets, and theme input for prompt generation
 */

import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  VStack,
  HStack,
  Button,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Select,
  Textarea,
  FormControl,
  FormLabel,
  Tooltip,
  Icon,
} from '@chakra-ui/react';
import { FaMagic, FaInfoCircle } from 'react-icons/fa';

import { UserSettings, PRESET_OPTIONS } from '../types';

interface GenerationControlsProps {
  settings: UserSettings;
  onSettingsChange: (updates: Partial<UserSettings>) => void;
  theme: string;
  onThemeChange: (theme: string) => void;
  onGenerate: () => void;
  generating: boolean;
  disabled: boolean;
}

export function GenerationControls({
  settings,
  onSettingsChange,
  theme,
  onThemeChange,
  onGenerate,
  generating,
  disabled,
}: GenerationControlsProps) {
  return (
    <Card bg="gray.800" borderColor="gray.700" variant="outline">
      <CardHeader pb={2}>
        <Heading size="md">Generation Controls</Heading>
        <Text color="gray.400" fontSize="sm" mt={1}>
          Fine-tune the style and mood of your generated prompt
        </Text>
      </CardHeader>
      
      <CardBody pt={4}>
        <VStack spacing={6} align="stretch">
          {/* Preset Selector */}
          <FormControl>
            <FormLabel fontSize="sm" color="gray.300">
              Genre Preset
            </FormLabel>
            <Select
              value={settings.preset || ''}
              onChange={(e) => onSettingsChange({ preset: e.target.value || null })}
              bg="gray.700"
              borderColor="gray.600"
            >
              {PRESET_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </FormControl>
          
          {/* Sliders */}
          <HStack spacing={6} align="start" wrap="wrap">
            <SliderControl
              label="Energy"
              tooltip="From calm and serene to explosive and high-energy"
              value={settings.energy}
              onChange={(val) => onSettingsChange({ energy: val })}
              lowLabel="Calm"
              highLabel="Intense"
            />
            
            <SliderControl
              label="Rhythm Complexity"
              tooltip="From simple, steady beats to complex polyrhythmic patterns"
              value={settings.rhythmComplexity}
              onChange={(val) => onSettingsChange({ rhythmComplexity: val })}
              lowLabel="Simple"
              highLabel="Complex"
            />
            
            <SliderControl
              label="Darkness"
              tooltip="From bright and uplifting to dark and melancholic"
              value={settings.darkness}
              onChange={(val) => onSettingsChange({ darkness: val })}
              lowLabel="Light"
              highLabel="Dark"
            />
          </HStack>
          
          {/* Theme Input */}
          <FormControl>
            <FormLabel fontSize="sm" color="gray.300">
              Theme / Story Idea (optional)
            </FormLabel>
            <Textarea
              value={theme}
              onChange={(e) => onThemeChange(e.target.value)}
              placeholder="e.g., A journey through the city at night, finding hope after loss..."
              bg="gray.700"
              borderColor="gray.600"
              rows={3}
              maxLength={200}
              resize="none"
            />
            <Text fontSize="xs" color="gray.500" mt={1}>
              {theme.length}/200 characters
            </Text>
          </FormControl>
          
          {/* Generate Button */}
          <Button
            leftIcon={<FaMagic />}
            variant="spotify"
            size="lg"
            onClick={onGenerate}
            isLoading={generating}
            loadingText="Generating..."
            isDisabled={disabled}
            w="full"
          >
            Generate Prompt + Lyrics
          </Button>
        </VStack>
      </CardBody>
    </Card>
  );
}

interface SliderControlProps {
  label: string;
  tooltip: string;
  value: number;
  onChange: (value: number) => void;
  lowLabel: string;
  highLabel: string;
}

function SliderControl({
  label,
  tooltip,
  value,
  onChange,
  lowLabel,
  highLabel,
}: SliderControlProps) {
  return (
    <Box flex="1" minW="200px">
      <HStack mb={2} spacing={1}>
        <Text fontSize="sm" color="gray.300">
          {label}
        </Text>
        <Tooltip label={tooltip} placement="top">
          <Box as="span" color="gray.500" cursor="help">
            <Icon as={FaInfoCircle} boxSize={3} />
          </Box>
        </Tooltip>
        <Text fontSize="sm" color="brand.400" ml="auto">
          {value}
        </Text>
      </HStack>
      <Slider
        value={value}
        onChange={onChange}
        min={0}
        max={100}
        step={5}
        colorScheme="brand"
      >
        <SliderTrack bg="gray.600">
          <SliderFilledTrack />
        </SliderTrack>
        <SliderThumb boxSize={4} />
      </Slider>
      <HStack justify="space-between" mt={1}>
        <Text fontSize="xs" color="gray.500">
          {lowLabel}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {highLabel}
        </Text>
      </HStack>
    </Box>
  );
}
