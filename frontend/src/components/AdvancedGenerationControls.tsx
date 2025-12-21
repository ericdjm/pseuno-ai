import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Input,
  Select,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Switch,
  FormControl,
  FormLabel,
  Badge,
  Wrap,
  WrapItem,
  IconButton,
  useToast,
} from '@chakra-ui/react';
import { AddIcon, DeleteIcon } from '@chakra-ui/icons';
import { useState } from 'react';
import { generateAdvanced, getAvailableModes, AdvancedGenerateRequest } from '../api';

interface AdvancedGenerationControlsProps {
  onGenerate: (result: any) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

export default function AdvancedGenerationControls({
  onGenerate,
  isLoading,
  setIsLoading,
}: AdvancedGenerationControlsProps) {
  const toast = useToast();
  
  // Vibe Intent
  const [primaryFeeling, setPrimaryFeeling] = useState('');
  const [sensoryGoals, setSensoryGoals] = useState<string[]>([]);
  const [newSensoryGoal, setNewSensoryGoal] = useState('');
  
  // Mode
  const [selectedMode, setSelectedMode] = useState('');
  const [availableModes, setAvailableModes] = useState<string[]>([]);
  
  // Vocal Controls
  const [vocalIntensity, setVocalIntensity] = useState('');
  const [vocalRange, setVocalRange] = useState('');
  const [vocalExperimental, setVocalExperimental] = useState<string[]>([]);
  const [newVocalExp, setNewVocalExp] = useState('');
  
  // Rhythm Controls
  const [rhythmComplexity, setRhythmComplexity] = useState('');
  const [rhythmDrops, setRhythmDrops] = useState('');
  const [rhythmAccents, setRhythmAccents] = useState<string[]>([]);
  const [newRhythmAccent, setNewRhythmAccent] = useState('');
  
  // Texture Controls
  const [organicVsSynthetic, setOrganicVsSynthetic] = useState(50);
  const [atmosphere, setAtmosphere] = useState<string[]>([]);
  const [newAtmosphere, setNewAtmosphere] = useState('');
  
  // Structure Controls
  const [fakeDrops, setFakeDrops] = useState(false);
  const [unresolved, setUnresolved] = useState(false);
  const [intentionalChaos, setIntentionalChaos] = useState(false);
  
  // Rule Breaking
  const [breakMelody, setBreakMelody] = useState(false);
  const [breakRhythm, setBreakRhythm] = useState(false);
  const [permissionToViolate, setPermissionToViolate] = useState<string[]>([]);
  const [newPermission, setNewPermission] = useState('');
  
  // Content Theme
  const [themeType, setThemeType] = useState('');
  const [specificTopic, setSpecificTopic] = useState('');
  const [repetitionStyle, setRepetitionStyle] = useState('');
  
  // Contrast Iteration
  const [referenceId, setReferenceId] = useState('');
  const [lessOf, setLessOf] = useState<string[]>([]);
  const [moreOf, setMoreOf] = useState<string[]>([]);
  const [pushDirection, setPushDirection] = useState('');
  const [newLessOf, setNewLessOf] = useState('');
  const [newMoreOf, setNewMoreOf] = useState('');
  
  // Lyric Density
  const [lyricDensity, setLyricDensity] = useState('');

  // Load available modes on mount
  useState(() => {
    getAvailableModes().then(modes => setAvailableModes(modes));
  });

  const addToList = (list: string[], setList: (items: string[]) => void, item: string, setItem: (val: string) => void) => {
    if (item.trim()) {
      setList([...list, item.trim()]);
      setItem('');
    }
  };

  const removeFromList = (list: string[], setList: (items: string[]) => void, index: number) => {
    setList(list.filter((_, i) => i !== index));
  };

  const handleGenerate = async () => {
    if (!primaryFeeling.trim()) {
      toast({
        title: 'Missing primary feeling',
        description: 'Please enter a primary feeling for your vibe intent',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsLoading(true);
    try {
      const request: AdvancedGenerateRequest = {
        vibe_intent: {
          primary_feeling: primaryFeeling,
          sensory_goals: sensoryGoals.length > 0 ? sensoryGoals : undefined,
        },
        mode: selectedMode || undefined,
        vocals: vocalIntensity || vocalRange || vocalExperimental.length > 0
          ? {
              intensity: vocalIntensity || undefined,
              range: vocalRange || undefined,
              experimental: vocalExperimental.length > 0 ? vocalExperimental : undefined,
            }
          : undefined,
        rhythm: rhythmComplexity || rhythmDrops || rhythmAccents.length > 0
          ? {
              complexity: rhythmComplexity || undefined,
              drops: rhythmDrops || undefined,
              accents: rhythmAccents.length > 0 ? rhythmAccents : undefined,
            }
          : undefined,
        texture: atmosphere.length > 0 || organicVsSynthetic !== 50
          ? {
              organic_vs_synthetic: organicVsSynthetic !== 50 ? organicVsSynthetic : undefined,
              atmosphere: atmosphere.length > 0 ? atmosphere : undefined,
            }
          : undefined,
        structure: fakeDrops || unresolved || intentionalChaos
          ? {
              fake_drops: fakeDrops || undefined,
              unresolved: unresolved || undefined,
              intentional_chaos: intentionalChaos || undefined,
            }
          : undefined,
        rule_breaking: breakMelody || breakRhythm || permissionToViolate.length > 0
          ? {
              break_melody: breakMelody || undefined,
              break_rhythm: breakRhythm || undefined,
              permission_to_violate: permissionToViolate.length > 0 ? permissionToViolate : undefined,
            }
          : undefined,
        content_theme: themeType || specificTopic || repetitionStyle
          ? {
              theme_type: themeType || undefined,
              specific_topic: specificTopic || undefined,
              repetition_style: repetitionStyle || undefined,
            }
          : undefined,
        contrast: referenceId || lessOf.length > 0 || moreOf.length > 0 || pushDirection
          ? {
              reference_id: referenceId || undefined,
              less_of: lessOf.length > 0 ? lessOf : undefined,
              more_of: moreOf.length > 0 ? moreOf : undefined,
              push_direction: pushDirection || undefined,
            }
          : undefined,
        lyric_density: lyricDensity || undefined,
      };

      const result = await generateAdvanced(request);
      onGenerate(result);
      
      toast({
        title: 'Generation complete',
        description: `Created: ${result.concept_title}`,
        status: 'success',
        duration: 5000,
      });
    } catch (error) {
      toast({
        title: 'Generation failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Box>
      <Tabs colorScheme="green" variant="enclosed">
        <TabList>
          <Tab>Vibe Intent</Tab>
          <Tab>Controls</Tab>
          <Tab>Structure</Tab>
          <Tab>Content</Tab>
          <Tab>Advanced</Tab>
        </TabList>

        <TabPanels>
          {/* Vibe Intent Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <FormControl isRequired>
                <FormLabel>Primary Feeling</FormLabel>
                <Input
                  placeholder="e.g., chills, focus, rage, peace, chaos"
                  value={primaryFeeling}
                  onChange={(e) => setPrimaryFeeling(e.target.value)}
                />
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Start with the emotional/sensory goal, not a genre
                </Text>
              </FormControl>

              <FormControl>
                <FormLabel>Mode Preset</FormLabel>
                <Select
                  placeholder="Choose a preset (optional)"
                  value={selectedMode}
                  onChange={(e) => setSelectedMode(e.target.value)}
                >
                  {availableModes.map(mode => (
                    <option key={mode} value={mode}>{mode}</option>
                  ))}
                </Select>
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Presets apply default control settings
                </Text>
              </FormControl>

              <FormControl>
                <FormLabel>Sensory Goals</FormLabel>
                <HStack>
                  <Input
                    placeholder="e.g., goosebumps, tension, release"
                    value={newSensoryGoal}
                    onChange={(e) => setNewSensoryGoal(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        addToList(sensoryGoals, setSensoryGoals, newSensoryGoal, setNewSensoryGoal);
                      }
                    }}
                  />
                  <IconButton
                    aria-label="Add sensory goal"
                    icon={<AddIcon />}
                    onClick={() => addToList(sensoryGoals, setSensoryGoals, newSensoryGoal, setNewSensoryGoal)}
                  />
                </HStack>
                <Wrap mt={2}>
                  {sensoryGoals.map((goal, i) => (
                    <WrapItem key={i}>
                      <Badge colorScheme="purple" display="flex" alignItems="center" gap={1}>
                        {goal}
                        <IconButton
                          aria-label="Remove"
                          icon={<DeleteIcon />}
                          size="xs"
                          variant="ghost"
                          onClick={() => removeFromList(sensoryGoals, setSensoryGoals, i)}
                        />
                      </Badge>
                    </WrapItem>
                  ))}
                </Wrap>
              </FormControl>
            </VStack>
          </TabPanel>

          {/* Controls Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              {/* Vocal Controls */}
              <Box>
                <Text fontWeight="bold" mb={2}>Vocals</Text>
                <VStack spacing={3} align="stretch">
                  <Select
                    placeholder="Vocal intensity"
                    value={vocalIntensity}
                    onChange={(e) => setVocalIntensity(e.target.value)}
                  >
                    <option value="soft">Soft</option>
                    <option value="spoken">Spoken</option>
                    <option value="singing">Singing</option>
                    <option value="screaming">Screaming</option>
                    <option value="raw">Raw</option>
                  </Select>

                  <Select
                    placeholder="Vocal range"
                    value={vocalRange}
                    onChange={(e) => setVocalRange(e.target.value)}
                  >
                    <option value="narrow">Narrow</option>
                    <option value="wide">Wide</option>
                    <option value="extreme">Extreme</option>
                  </Select>

                  <HStack>
                    <Input
                      placeholder="Experimental vocal techniques"
                      value={newVocalExp}
                      onChange={(e) => setNewVocalExp(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addToList(vocalExperimental, setVocalExperimental, newVocalExp, setNewVocalExp);
                        }
                      }}
                    />
                    <IconButton
                      aria-label="Add vocal technique"
                      icon={<AddIcon />}
                      onClick={() => addToList(vocalExperimental, setVocalExperimental, newVocalExp, setNewVocalExp)}
                    />
                  </HStack>
                  <Wrap>
                    {vocalExperimental.map((tech, i) => (
                      <WrapItem key={i}>
                        <Badge colorScheme="blue">
                          {tech}
                          <IconButton
                            aria-label="Remove"
                            icon={<DeleteIcon />}
                            size="xs"
                            variant="ghost"
                            ml={1}
                            onClick={() => removeFromList(vocalExperimental, setVocalExperimental, i)}
                          />
                        </Badge>
                      </WrapItem>
                    ))}
                  </Wrap>
                </VStack>
              </Box>

              {/* Rhythm Controls */}
              <Box>
                <Text fontWeight="bold" mb={2}>Rhythm</Text>
                <VStack spacing={3} align="stretch">
                  <Select
                    placeholder="Rhythm complexity"
                    value={rhythmComplexity}
                    onChange={(e) => setRhythmComplexity(e.target.value)}
                  >
                    <option value="simple">Simple</option>
                    <option value="syncopated">Syncopated</option>
                    <option value="polyrhythmic">Polyrhythmic</option>
                    <option value="chaotic">Chaotic</option>
                  </Select>

                  <Select
                    placeholder="Drops"
                    value={rhythmDrops}
                    onChange={(e) => setRhythmDrops(e.target.value)}
                  >
                    <option value="none">None</option>
                    <option value="predictable">Predictable</option>
                    <option value="random">Random</option>
                  </Select>

                  <HStack>
                    <Input
                      placeholder="Rhythm accents (e.g., silence → slam)"
                      value={newRhythmAccent}
                      onChange={(e) => setNewRhythmAccent(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addToList(rhythmAccents, setRhythmAccents, newRhythmAccent, setNewRhythmAccent);
                        }
                      }}
                    />
                    <IconButton
                      aria-label="Add rhythm accent"
                      icon={<AddIcon />}
                      onClick={() => addToList(rhythmAccents, setRhythmAccents, newRhythmAccent, setNewRhythmAccent)}
                    />
                  </HStack>
                  <Wrap>
                    {rhythmAccents.map((accent, i) => (
                      <WrapItem key={i}>
                        <Badge colorScheme="orange">
                          {accent}
                          <IconButton
                            aria-label="Remove"
                            icon={<DeleteIcon />}
                            size="xs"
                            variant="ghost"
                            ml={1}
                            onClick={() => removeFromList(rhythmAccents, setRhythmAccents, i)}
                          />
                        </Badge>
                      </WrapItem>
                    ))}
                  </Wrap>
                </VStack>
              </Box>

              {/* Texture Controls */}
              <Box>
                <Text fontWeight="bold" mb={2}>Texture</Text>
                <VStack spacing={3} align="stretch">
                  <FormControl>
                    <FormLabel>Organic vs Synthetic: {organicVsSynthetic}%</FormLabel>
                    <HStack>
                      <Text fontSize="sm">Organic</Text>
                      <Slider
                        value={organicVsSynthetic}
                        onChange={setOrganicVsSynthetic}
                        min={0}
                        max={100}
                      >
                        <SliderTrack>
                          <SliderFilledTrack bg="green.400" />
                        </SliderTrack>
                        <SliderThumb />
                      </Slider>
                      <Text fontSize="sm">Synthetic</Text>
                    </HStack>
                  </FormControl>

                  <HStack>
                    <Input
                      placeholder="Atmosphere (e.g., industrial, cathedral)"
                      value={newAtmosphere}
                      onChange={(e) => setNewAtmosphere(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addToList(atmosphere, setAtmosphere, newAtmosphere, setNewAtmosphere);
                        }
                      }}
                    />
                    <IconButton
                      aria-label="Add atmosphere"
                      icon={<AddIcon />}
                      onClick={() => addToList(atmosphere, setAtmosphere, newAtmosphere, setNewAtmosphere)}
                    />
                  </HStack>
                  <Wrap>
                    {atmosphere.map((atm, i) => (
                      <WrapItem key={i}>
                        <Badge colorScheme="teal">
                          {atm}
                          <IconButton
                            aria-label="Remove"
                            icon={<DeleteIcon />}
                            size="xs"
                            variant="ghost"
                            ml={1}
                            onClick={() => removeFromList(atmosphere, setAtmosphere, i)}
                          />
                        </Badge>
                      </WrapItem>
                    ))}
                  </Wrap>
                </VStack>
              </Box>
            </VStack>
          </TabPanel>

          {/* Structure Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <FormControl display="flex" alignItems="center">
                <FormLabel mb={0}>Fake Drops</FormLabel>
                <Switch
                  isChecked={fakeDrops}
                  onChange={(e) => setFakeDrops(e.target.checked)}
                  colorScheme="green"
                />
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb={0}>Unresolved Endings</FormLabel>
                <Switch
                  isChecked={unresolved}
                  onChange={(e) => setUnresolved(e.target.checked)}
                  colorScheme="green"
                />
              </FormControl>

              <FormControl display="flex" alignItems="center">
                <FormLabel mb={0}>Intentional Chaos</FormLabel>
                <Switch
                  isChecked={intentionalChaos}
                  onChange={(e) => setIntentionalChaos(e.target.checked)}
                  colorScheme="green"
                />
              </FormControl>

              <Box>
                <Text fontWeight="bold" mb={2}>Rule Breaking</Text>
                <VStack spacing={3} align="stretch">
                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb={0}>Break Melody</FormLabel>
                    <Switch
                      isChecked={breakMelody}
                      onChange={(e) => setBreakMelody(e.target.checked)}
                      colorScheme="red"
                    />
                  </FormControl>

                  <FormControl display="flex" alignItems="center">
                    <FormLabel mb={0}>Break Rhythm</FormLabel>
                    <Switch
                      isChecked={breakRhythm}
                      onChange={(e) => setBreakRhythm(e.target.checked)}
                      colorScheme="red"
                    />
                  </FormControl>

                  <HStack>
                    <Input
                      placeholder="Permission to violate (e.g., use silence as structure)"
                      value={newPermission}
                      onChange={(e) => setNewPermission(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          addToList(permissionToViolate, setPermissionToViolate, newPermission, setNewPermission);
                        }
                      }}
                    />
                    <IconButton
                      aria-label="Add permission"
                      icon={<AddIcon />}
                      onClick={() => addToList(permissionToViolate, setPermissionToViolate, newPermission, setNewPermission)}
                    />
                  </HStack>
                  <Wrap>
                    {permissionToViolate.map((perm, i) => (
                      <WrapItem key={i}>
                        <Badge colorScheme="red">
                          {perm}
                          <IconButton
                            aria-label="Remove"
                            icon={<DeleteIcon />}
                            size="xs"
                            variant="ghost"
                            ml={1}
                            onClick={() => removeFromList(permissionToViolate, setPermissionToViolate, i)}
                          />
                        </Badge>
                      </WrapItem>
                    ))}
                  </Wrap>
                </VStack>
              </Box>
            </VStack>
          </TabPanel>

          {/* Content Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Theme Type</FormLabel>
                <Select
                  placeholder="Choose theme type"
                  value={themeType}
                  onChange={(e) => setThemeType(e.target.value)}
                >
                  <option value="work">Work</option>
                  <option value="grief">Grief</option>
                  <option value="ritual">Ritual</option>
                  <option value="transition">Transition</option>
                  <option value="hope">Hope</option>
                  <option value="threat">Threat</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Specific Topic</FormLabel>
                <Input
                  placeholder="e.g., debugging code, letting go, building tools"
                  value={specificTopic}
                  onChange={(e) => setSpecificTopic(e.target.value)}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Repetition Style</FormLabel>
                <Select
                  placeholder="Choose repetition style"
                  value={repetitionStyle}
                  onChange={(e) => setRepetitionStyle(e.target.value)}
                >
                  <option value="chant">Chant</option>
                  <option value="mantra">Mantra</option>
                  <option value="varied">Varied</option>
                  <option value="none">None</option>
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Lyric Density</FormLabel>
                <Select
                  placeholder="Auto-calculate based on intensity"
                  value={lyricDensity}
                  onChange={(e) => setLyricDensity(e.target.value)}
                >
                  <option value="minimal">Minimal (chants, repeats)</option>
                  <option value="moderate">Moderate (balanced)</option>
                  <option value="rich">Rich (detailed, narrative)</option>
                </Select>
                <Text fontSize="sm" color="gray.500" mt={1}>
                  Leave blank to auto-calculate: high intensity → minimal lyrics
                </Text>
              </FormControl>
            </VStack>
          </TabPanel>

          {/* Advanced Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <Text fontWeight="bold">Contrast Iteration</Text>
              <Text fontSize="sm" color="gray.500">
                Iterate by contrast, not correction
              </Text>

              <FormControl>
                <FormLabel>Reference ID</FormLabel>
                <Input
                  placeholder="Previous generation ID to iterate from"
                  value={referenceId}
                  onChange={(e) => setReferenceId(e.target.value)}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Less Of</FormLabel>
                <HStack>
                  <Input
                    placeholder="What to reduce (e.g., country, melody)"
                    value={newLessOf}
                    onChange={(e) => setNewLessOf(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        addToList(lessOf, setLessOf, newLessOf, setNewLessOf);
                      }
                    }}
                  />
                  <IconButton
                    aria-label="Add less of"
                    icon={<AddIcon />}
                    onClick={() => addToList(lessOf, setLessOf, newLessOf, setNewLessOf)}
                  />
                </HStack>
                <Wrap mt={2}>
                  {lessOf.map((item, i) => (
                    <WrapItem key={i}>
                      <Badge colorScheme="yellow">
                        -{item}
                        <IconButton
                          aria-label="Remove"
                          icon={<DeleteIcon />}
                          size="xs"
                          variant="ghost"
                          ml={1}
                          onClick={() => removeFromList(lessOf, setLessOf, i)}
                        />
                      </Badge>
                    </WrapItem>
                  ))}
                </Wrap>
              </FormControl>

              <FormControl>
                <FormLabel>More Of</FormLabel>
                <HStack>
                  <Input
                    placeholder="What to increase (e.g., drops, intensity)"
                    value={newMoreOf}
                    onChange={(e) => setNewMoreOf(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        addToList(moreOf, setMoreOf, newMoreOf, setNewMoreOf);
                      }
                    }}
                  />
                  <IconButton
                    aria-label="Add more of"
                    icon={<AddIcon />}
                    onClick={() => addToList(moreOf, setMoreOf, newMoreOf, setNewMoreOf)}
                  />
                </HStack>
                <Wrap mt={2}>
                  {moreOf.map((item, i) => (
                    <WrapItem key={i}>
                      <Badge colorScheme="cyan">
                        +{item}
                        <IconButton
                          aria-label="Remove"
                          icon={<DeleteIcon />}
                          size="xs"
                          variant="ghost"
                          ml={1}
                          onClick={() => removeFromList(moreOf, setMoreOf, i)}
                        />
                      </Badge>
                    </WrapItem>
                  ))}
                </Wrap>
              </FormControl>

              <FormControl>
                <FormLabel>Push Direction</FormLabel>
                <Select
                  placeholder="Overall directional push"
                  value={pushDirection}
                  onChange={(e) => setPushDirection(e.target.value)}
                >
                  <option value="harder">Harder</option>
                  <option value="softer">Softer</option>
                  <option value="weirder">Weirder</option>
                  <option value="cleaner">Cleaner</option>
                  <option value="darker">Darker</option>
                  <option value="lighter">Lighter</option>
                </Select>
              </FormControl>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>

      <Button
        colorScheme="green"
        size="lg"
        width="full"
        mt={6}
        onClick={handleGenerate}
        isLoading={isLoading}
        loadingText="Generating..."
      >
        Generate with Advanced Controls
      </Button>
    </Box>
  );
}
