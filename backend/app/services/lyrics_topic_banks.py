"""
Lyrics topic banks.

Each bank is a curated set of short "lyrics about" prompts plus a trait vector
used for routing. Bank selection is probabilistic and should feel diverse while
remaining on-theme for the user's tags and (async) style classifier signal.

IMPORTANT: Avoid em/en dashes in prompts. They read as AI-ish in this UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


@dataclass(frozen=True)
class TopicBank:
    id: str
    name: str
    description: str
    traits: Mapping[str, float]
    prompts: Tuple[str, ...]


TOPIC_BANKS: Dict[str, TopicBank] = {}


def _register_bank(bank: TopicBank) -> None:
    if bank.id in TOPIC_BANKS:
        raise ValueError(f"Duplicate bank id: {bank.id}")
    TOPIC_BANKS[bank.id] = bank


# =============================================================================
# CORE HUMAN THEMES (broad coverage, high quality, no dash punctuation)
# =============================================================================

_register_bank(
    TopicBank(
        id="confessional_heartbreak",
        name="Confessional Heartbreak",
        description="Raw breakup confession, longing, regret, late-night thoughts.",
        traits={
            "romantic": 0.9,
            "melancholic": 0.85,
            "confessional": 0.9,
            "vulnerable": 0.7,
            "rnb_friendly": 0.5,
            "pop_friendly": 0.5,
        },
        prompts=(
            "Reading our old texts like scripture, trying to find the exact moment we started losing each other",
            "I keep rehearsing the apology I will never get to say, and it keeps changing but it never fixes anything",
            "Watching their life move on without me, and pretending I am happy for them while I fall apart quietly",
            "The room feels too big now, like the echo of their absence is louder than anything I can play",
            "I keep running into them in dreams and waking up to the same empty side of the bed",
            "I miss the person I was when I thought we were forever",
            "Trying to delete them from my life while every song keeps spelling their name",
            "I thought time would soften this, but it just taught me new ways to miss you",
            "I keep catching myself saving stories I will never tell them",
            "Seeing their smile in a stranger for half a second, and feeling my chest cave in",
        ),
    )
)

_register_bank(
    TopicBank(
        id="domestic_quiet",
        name="Domestic Quiet",
        description="Small, intimate moments at home, comfort, routine, subtle emotions.",
        traits={
            "domestic": 0.9,
            "romantic": 0.55,
            "introspective": 0.4,
            "uplifting": 0.45,
            "folk_friendly": 0.5,
            "pop_friendly": 0.4,
        },
        prompts=(
            "Keys dropping in the bowl, shoes by the door, the small sounds that mean someone is home and the house is full again",
            "The dishwasher humming while we talk about nothing important, and realizing this is what peace feels like",
            "Folding laundry in silence and feeling loved anyway, like the room is warm even without words",
            "A cup of tea going cold on the counter because the conversation mattered more than the drink",
            "We learned each other's habits so well that the day runs smoother just because we exist in it together",
            "The light from the fridge at midnight, both of us searching for comfort we already have",
            "Cooking the same meal we always cook, and still feeling like it is a celebration",
            "The old couch, the shared blanket, the tiny world we keep building with ordinary days",
            "I used to chase fireworks, now I crave a steady lamp in the dark",
            "A quiet morning where nothing changes, and that is exactly why it is beautiful",
        ),
    )
)

_register_bank(
    TopicBank(
        id="new_love_electricity",
        name="New Love Electricity",
        description="First sparks, butterflies, thrilling uncertainty, playful flirtation.",
        traits={
            "romantic": 0.95,
            "uplifting": 0.75,
            "playful": 0.6,
            "pop_friendly": 0.6,
            "rnb_friendly": 0.5,
        },
        prompts=(
            "The first time our hands touched and I felt my whole week rearrange itself",
            "Every notification feels like a little lightning strike because it might be them",
            "I keep smiling at nothing, like my face is giving away a secret before I am ready",
            "Learning the geography of a new face, the way light catches their eyes and turns my thoughts into poetry",
            "I am trying to play it cool, but my heart is doing laps around my ribs",
            "The moment you realize you want to tell them everything, even the parts you keep hidden",
            "Two people circling the same truth, pretending it is not obvious yet",
            "I am afraid to hope, but I am hoping anyway",
            "We keep finding excuses to talk, and none of them are believable",
            "A future building itself in my head, and I do not even know their favorite color yet",
        ),
    )
)

_register_bank(
    TopicBank(
        id="post_breakup_liberation",
        name="Post Breakup Liberation",
        description="Relief, self-reclamation, rebuilding identity, glowing up after loss.",
        traits={
            "empowering": 0.85,
            "uplifting": 0.7,
            "pop_friendly": 0.55,
            "rnb_friendly": 0.45,
            "rock_friendly": 0.4,
        },
        prompts=(
            "First weekend in months where the time is mine, no compromises, no eggshells, just air in my lungs",
            "I found my hobbies again, like buried treasure under years of shrinking myself",
            "I am learning that peace is not boring, it is a form of freedom",
            "Turns out the problem was never me, it just took distance to see it clearly",
            "I kept calling it love, but it was just fear with a pretty name",
            "I cut my hair, changed my routine, and watched my life start listening to me",
            "I am not healing in a straight line, but I am moving forward and that counts",
            "I used to beg for crumbs, now I am baking my own bread",
            "I do not need closure from them, I am building closure out of my own choices",
            "Somewhere between the tears, I remembered my worth and decided to keep it",
        ),
    )
)

_register_bank(
    TopicBank(
        id="melancholy_stillness",
        name="Melancholy and Stillness",
        description="Soft sadness, quiet reflection, gentle imagery, slow time.",
        traits={
            "melancholic": 0.9,
            "vulnerable": 0.6,
            "folk_friendly": 0.5,
            "pop_friendly": 0.4,
            "rnb_friendly": 0.35,
        },
        prompts=(
            "Watching rain trace paths down the window and feeling like my thoughts are doing the same",
            "Homesick for a place I have never been, missing a version of life that only exists in my head",
            "Sitting in a parked car with the engine off, letting the silence say what I cannot",
            "Time moves differently when you are alone with your own memories",
            "I keep thinking about the people I used to be and wondering where they went",
            "A slow morning where the only sound is my breath and the clock trying to be helpful",
            "The kind of sadness that does not scream, it just settles in like dust",
            "I am tired in a way sleep cannot fix",
            "Standing in the grocery aisle, forgetting what I came for, remembering what I lost instead",
            "A quiet grief that feels like carrying water in my hands, always leaking but never empty",
        ),
    )
)

_register_bank(
    TopicBank(
        id="spiritual_existential",
        name="Spiritual and Existential",
        description="Meaning, mortality, awe, faith, cosmic questions, self and universe.",
        traits={
            "spiritual": 0.9,
            "introspective": 0.7,
            "emotional_intensity": 0.5,
            "surreal": 0.4,
        },
        prompts=(
            "The terror and wonder of infinite space hitting at the same time, too big to hold but impossible to ignore",
            "I keep asking the sky for answers and it keeps answering with silence that sounds like truth",
            "What if the point is not to win, but to become someone who can love without fear",
            "I feel small in the best way, like a single note inside a much larger song",
            "I am trying to forgive the universe for being indifferent, and myself for needing it to care",
            "If I am made of stardust, why do I still feel so heavy",
            "Praying without a religion, just talking to the dark like it can hear me",
            "I keep looking for signs, but maybe I am the one who has to make meaning",
            "Some nights I feel like a visitor in my own life, passing through",
            "The idea of forever is beautiful until you realize you have to live inside it",
        ),
    )
)

# =============================================================================
# EDGE, POWER, CONFLICT
# =============================================================================

_register_bank(
    TopicBank(
        id="rebellion_defiance",
        name="Rebellion and Defiance",
        description="Anti-authority, refusing control, breaking rules, self-determination.",
        traits={
            "aggressive": 0.7,
            "empowering": 0.75,
            "emotional_intensity": 0.5,  # Overlap with defaults
            "rock_friendly": 0.7,
            "metal_friendly": 0.5,
            "hip_hop_friendly": 0.5,
            "dark": 0.4,
        },
        prompts=(
            "I am done asking permission, my life is not a committee decision",
            "They built a cage and called it safety, I learned the lock and swallowed the key",
            "If the rules are made to keep me small, I will outgrow the room on purpose",
            "I would rather be hated for who I am than loved for who I pretend to be",
            "I learned to smile while plotting my escape, and now the door is open",
            "Let them talk, I am busy becoming ungovernable in the quietest ways",
            "I am not a project to fix, I am a fire to respect",
            "They want obedience, I want truth",
            "I am choosing myself even if it looks like betrayal to people who benefited from my silence",
            "Some bridges are meant to burn because the shore behind you is not home anymore",
        ),
    )
)

_register_bank(
    TopicBank(
        id="political_systems_critique",
        name="Political and Systems Critique",
        description="Power, propaganda, surveillance, exploitation, modern societal critique.",
        traits={
            "political": 0.95,
            "dark": 0.5,
            "introspective": 0.35,  # Overlap with defaults
            "aggressive": 0.4,
            "hip_hop_friendly": 0.5,
            "rock_friendly": 0.5,
        },
        prompts=(
            "A world where truth is a subscription and empathy is treated like a weakness",
            "They sell us fear and call it news, they sell us hope and call it a product",
            "Cameras on every corner and still no one sees the people sleeping outside",
            "The machine keeps running because we keep feeding it our time and calling that normal",
            "We traded privacy for convenience and now convenience is holding the receipt",
            "The city shines bright while the people inside it fade",
            "They promised progress, but it feels like a slower kind of collapse",
            "Everything is branded, even the rebellion",
            "The loudest voices get richer and the quietest lives get harder",
            "We keep scrolling past tragedy because the algorithm trained our grief to be brief",
        ),
    )
)

# =============================================================================
# ABSTRACT / CONCEPTUAL (prog-friendly)
# =============================================================================

_register_bank(
    TopicBank(
        id="consciousness_metaphysical",
        name="Consciousness and Metaphysical",
        description="Identity layers, perception, reality as metaphor, inner worlds.",
        traits={
            "surreal": 0.8,
            "introspective": 0.6,
            "prog_rock_friendly": 0.6,
            "prog_metal_friendly": 0.5,
        },
        prompts=(
            "Spiraling through layers of self, each one revealing a mask I did not know I was wearing",
            "If I am the observer, who is the one being observed inside my own mind",
            "Reality feels like a dream that forgot it was a dream",
            "I keep waking up inside the same day, but as different versions of me",
            "My thoughts echo like a cavern, and I am trying to find the exit by listening",
            "Memory edits itself, and I cannot tell which parts are mine and which parts I borrowed",
            "What if my identity is just a story I keep retelling until it feels true",
            "I feel like a signal drifting between stations, almost clear but never fully tuned",
            "I keep chasing clarity and finding deeper questions instead",
            "The mind is a mirror that changes shape depending on who is looking",
        ),
    )
)

_register_bank(
    TopicBank(
        id="scifi_dystopia_philosophy",
        name="Sci Fi Dystopia and Philosophy",
        description="Futurism, collapse, AI, simulation, ethics, identity in a broken future.",
        traits={
            "dark": 0.7,
            "surreal": 0.6,
            "political": 0.5,
            "electronic_friendly": 0.5,
            "prog_metal_friendly": 0.4,
        },
        prompts=(
            "Dystopia arrived gradually, we decorated it and called it progress",
            "A city of neon promises and quiet despair, where everything is rented including hope",
            "The bots learned our habits, then learned our weaknesses, then learned to sell them back to us",
            "If my memories can be edited, am I still responsible for what I did when I believed them",
            "A future where love is an app setting and grief is an error message",
            "We outsourced thinking and now we cannot tell when we are being thought for",
            "The sky is full of satellites and none of them can find my missing peace",
            "In the simulation, the only real thing left is the ache in my chest",
            "A civilization that measures everything except meaning",
            "I found a human heart in a machine and it was still lonely",
        ),
    )
)

_register_bank(
    TopicBank(
        id="mythology_allegory",
        name="Mythology and Allegory",
        description="Modern myths, archetypes, gods as metaphors, symbolic storytelling.",
        traits={
            "narrative": 0.85,
            "surreal": 0.5,
            "prog_rock_friendly": 0.5,
            "metal_friendly": 0.4,
            "folk_friendly": 0.4,
        },
        prompts=(
            "A modern Icarus with a smartphone, flying too close to fame and burning anyway",
            "Orpheus looking back, not from doubt but from longing that refuses to be rational",
            "A god of small failures, worshiped in messy rooms and unfinished promises",
            "The hero returns home and realizes home has changed, or maybe the hero did",
            "A dragon made of debt, guarding nothing but shame",
            "I keep making offerings to the wrong altar, then acting surprised when nothing heals",
            "A prophecy written in notifications and missed calls",
            "I am the monster in someone else's story, and I am trying to learn why",
            "A labyrinth built from choices, and the thread is just patience",
            "A crown that feels heavy because it is made of expectations, not gold",
        ),
    )
)

# =============================================================================
# ALTERED STATE (metaphor-first, no explicit drug mentions)
# =============================================================================

_register_bank(
    TopicBank(
        id="psychedelic_perception",
        name="Psychedelic Perception",
        description="Synesthesia, wonder, ego-dissolve metaphors, kaleidoscopic imagery.",
        traits={
            "surreal": 0.9,
            "spiritual": 0.5,
            "rock_friendly": 0.5,
            "electronic_friendly": 0.5,
            "uplifting": 0.35,
        },
        prompts=(
            "Colors have opinions today, and they keep arguing in the corners of my vision",
            "The room is breathing with me, like the walls learned compassion",
            "Every thought becomes a pattern, and every pattern feels like a message",
            "Time stretches like taffy and I can taste the minutes",
            "I dissolved into the night sky and came back carrying a strange kind of gratitude",
            "The streetlights look like tiny suns, and I feel like I am orbiting my own life",
            "My name feels optional, like I can set it down and still be here",
            "I am seeing the same thing from a hundred angles at once, and it is all true somehow",
            "Laughter keeps arriving in waves, like the universe is telling a gentle joke",
            "I touched a memory and it turned into music in my hands",
        ),
    )
)

_register_bank(
    TopicBank(
        id="manic_velocity",
        name="Manic Velocity",
        description="Speed, confidence spikes, racing mind, bright edges, restless motion.",
        traits={
            "emotional_intensity": 0.8,
            "uplifting": 0.5,
            "electronic_friendly": 0.5,
            "rock_friendly": 0.4,
            "aggressive": 0.35,
        },
        prompts=(
            "My thoughts are sprinting ahead of my mouth, and I am trying to keep up",
            "I feel invincible until I blink, and then I remember gravity",
            "I am building a castle out of momentum, hoping it does not notice the cracks",
            "Everything is possible right now, and that is terrifying and beautiful",
            "I am talking too fast because silence feels like a trapdoor",
            "A thousand ideas at once, and every one of them feels like destiny",
            "I keep laughing because the world is too bright to take seriously",
            "I am tired but I cannot slow down, like my engine forgot how to stop",
            "I am writing my future in permanent marker, even though I only own tomorrow",
            "I can feel the sunrise before it happens, like my body is ahead of the clock",
        ),
    )
)

# =============================================================================
# NATURE / STORYTELLING (folk friendly)
# =============================================================================

_register_bank(
    TopicBank(
        id="whimsical_nature_folk",
        name="Whimsical Nature and Folk",
        description="Gentle nature scenes, small-town warmth, whimsical storytelling, cozy imagery.",
        traits={
            "pastoral": 0.9,
            "folk_friendly": 0.85,
            "playful": 0.55,
            "uplifting": 0.55,
            "narrative": 0.45,
            "romantic": 0.3,
        },
        prompts=(
            "A porch light and a summer breeze, telling stories to the fireflies like they are old friends",
            "A creek that knows my secrets, carrying them downstream with leaves and laughter",
            "The woods feeling like a library, every tree holding a chapter of my life",
            "A small town where everyone waves, and the sky looks bigger than the worries",
            "Rain on a tin roof, turning the whole house into a drum that keeps me company",
            "Wildflowers growing through cracked pavement, refusing to be discouraged",
            "A road trip with the windows down, letting the wind edit my thoughts into something kinder",
            "Catching sunlight in a mason jar, pretending I can save a day for later",
            "A quiet lake reflecting the part of me that finally slowed down",
            "A night hike under a soft moon, feeling like the world is older and gentler than the news",
        ),
    )
)

_register_bank(
    TopicBank(
        id="coastal_mysticism",
        name="Coastal Mysticism",
        description="Ocean imagery, fog, salt air, liminal shorelines, quiet mythic vibe.",
        traits={
            "coastal": 0.9,
            "melancholic": 0.5,
            "romantic": 0.4,
            "introspective": 0.45,
            "surreal": 0.4,
            "folk_friendly": 0.4,
        },
        prompts=(
            "Fog rolling in like a verdict, like the coast deciding what I am allowed to see today",
            "Salt on my lips, old stories in the tide pools, and the feeling that the ocean remembers everything",
            "A lighthouse blinking its patience into the dark, saying keep going even when you cannot tell where you are",
            "Waves writing and erasing the same sentence, and me trying to learn what it means",
            "I came to the shoreline to think, but the horizon keeps interrupting me with bigger questions",
            "Seagulls arguing overhead like they know the truth and refuse to share it politely",
            "Night driving along the coast, headlights cutting through mist like I am chasing a secret",
            "A storm at sea and a calm face, both hiding the same depth",
            "Driftwood on the sand, evidence that something survived a long journey",
            "Standing at the edge of land, feeling like the world is about to turn a page",
        ),
    )
)

_register_bank(
    TopicBank(
        id="body_groove",
        name="Body and Groove",
        description="Rhythm-forward themes, swagger, movement, heat, playful confidence.",
        traits={
            "party": 0.8,
            "playful": 0.7,
            "uplifting": 0.6,
            "rnb_friendly": 0.6,
            "hip_hop_friendly": 0.5,
            "electronic_friendly": 0.5,
        },
        prompts=(
            "The beat feels like a second heartbeat, and I finally trust my body to lead",
            "A dance floor confession, saying everything with shoulders and smiles instead of words",
            "Confidence building with every step, like the room is clapping just because I exist",
            "Sweat, bass, and the kind of joy that does not need permission",
            "I came in quiet and left like fireworks, all rhythm and bright edges",
            "Flirting with the mirror, learning that self love can be loud",
            "A summer night with windows down, letting the groove fix my mood",
            "Two people moving closer without deciding, letting the music do the negotiating",
            "I do not need to be understood, I need to be felt",
            "Turning a bad week into a good chorus, one dance at a time",
        ),
    )
)

_register_bank(
    TopicBank(
        id="warm_numbness",
        name="Warm Numbness",
        description="Soft dissociation, emotional buffering, cozy but hollow comfort.",
        traits={
            "melancholic": 0.7,
            "vulnerable": 0.6,
            "confessional": 0.55,
            "electronic_friendly": 0.4,
            "pop_friendly": 0.4,
        },
        prompts=(
            "I am wrapped in comfort like a blanket, but I cannot feel the warmth the way I used to",
            "Laughing at the right moments, doing all the right things, and still feeling like a ghost in my own life",
            "The day goes by in soft focus, like the world turned the volume down without asking me",
            "I keep choosing the easy distraction because the real feeling is too sharp",
            "I am calm on the outside, and I do not know if that is healing or hiding",
            "A slow drift through familiar streets, trying to remember what used to matter here",
            "I want to cry but the tears keep getting lost on the way to my eyes",
            "Comfort food and comfort silence, both filling space but not fixing the emptiness",
            "I miss being moved by things, and I do not know how to come back",
            "I keep telling myself I am fine until it starts sounding like a spell",
        ),
    )
)

_register_bank(
    TopicBank(
        id="absurdist_comedy",
        name="Absurdist Comedy",
        description="Weird humor, surreal everyday observations, playful nonsense with heart.",
        traits={
            "absurdist": 0.95,
            "playful": 0.85,
            "surreal": 0.5,
            "uplifting": 0.4,
            "pop_friendly": 0.4,
        },
        prompts=(
            "My brain is a group chat with no moderator, and everyone is typing at once",
            "I tried to romanticize my life but the receipts keep interrupting the poetry",
            "The universe keeps giving me character development when I asked for a nap",
            "I am doing my best, which is funny because my best is also a mess",
            "I lost my keys and found an existential crisis instead",
            "I am spiritually a houseplant, please water me and do not speak to me loudly",
            "I keep pretending I have a plan, and the plan keeps laughing at me",
            "I am the main character in a story the editor forgot to proofread",
            "I asked for a sign and got a billboard that just says good luck",
            "If overthinking was cardio, I would be an athlete",
        ),
    )
)

_register_bank(
    TopicBank(
        id="emo_rap_vulnerability",
        name="Emo Rap and Vulnerability",
        description="Modern confessional pain, loneliness, self doubt, soft darkness.",
        traits={
            "hip_hop_friendly": 0.8,
            "melancholic": 0.75,
            "confessional": 0.8,
            "vulnerable": 0.7,
            "dark": 0.5,
            "self_destructive": 0.4,
        },
        prompts=(
            "I keep joking about being okay because the truth is too heavy to say out loud",
            "Fame in my feed, emptiness in my chest, and nobody notices because I keep performing",
            "I text people first then regret it, like I am allergic to needing anyone",
            "I am tired of being strong, but I do not know how to be soft without breaking",
            "I keep scrolling for a reason to stay, and finding reasons to dissociate instead",
            "I miss someone who is still alive, and that feels like a special kind of grief",
            "I keep replaying mistakes until they sound like identity",
            "I want love but I flinch when it gets close",
            "I keep writing goodbye letters and calling them songs",
            "My heart feels like a cracked screen, still working but never clear",
        ),
    )
)


__all__ = ["TopicBank", "TOPIC_BANKS"]
