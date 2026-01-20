"""
Trait definitions and scoring utilities for lyrics topic routing.

Traits describe lyrical characteristics that help match user context to topic banks.
This module provides the vocabulary of traits and the math for scoring bank matches.
"""

from typing import Dict, List
import math


# =============================================================================
# TRAIT VOCABULARY
# =============================================================================

# All valid trait IDs with descriptions (for documentation/embedding)
TRAIT_DEFINITIONS: Dict[str, str] = {
    # Emotional register
    "emotional_intensity": "How emotionally charged the topic is (0=subtle, 1=intense)",
    "melancholic": "Sadness, loss, longing",
    "uplifting": "Hope, joy, triumph",
    "dark": "Darkness, edge, shadow, menace",
    "playful": "Humor, wit, lightness",
    # Relationship dynamics
    "romantic": "Love, attraction, partnership",
    "confessional": "First-person vulnerability, direct admission",
    "obsessive": "Fixation, addiction, can't-let-go energy",
    "devotional": "Loyalty, commitment, ride-or-die",
    # Self/Identity
    "introspective": "Self-examination, inner world",
    "self_destructive": "Bad choices, spiraling, the edge",
    "empowering": "Strength, growth, overcoming",
    "identity_seeking": "Becoming, evolution, finding yourself",
    # Setting/Imagery
    "urban": "City life, nightlife, concrete, neon",
    "pastoral": "Nature, rural, organic, earth",
    "coastal": "Ocean, beach, California vibes, saltwater",
    "road": "Travel, motion, transit, highways",
    "domestic": "Home, everyday intimacy, kitchen, bedroom",
    "suburban": "Quiet desperation, manicured lawns, 2am",
    # Voice/Delivery
    "braggadocio": "Flex, confidence, arrogance",
    "vulnerable": "Soft, exposed, tender",
    "aggressive": "Anger, rage, confrontation",
    "surreal": "Dreamlike, strange, abstract, symbolic",
    "narrative": "Story-driven, plot, characters",
    # Situation/Theme
    "party": "Nightlife, excess, hedonism",
    "grief": "Loss of someone specific, mourning",
    "forbidden": "Taboo, shouldn't-want, secrets",
    "political": "System critique, protest, collective anger",
    "spiritual": "Existential, meaning-seeking, faith",
    "horror": "Creepy, gothic, supernatural",
    "absurdist": "Comedy, satire, weird",
    # Genre affinity hints
    "hip_hop_friendly": "Works well with hip-hop/rap delivery",
    "rock_friendly": "Works well with rock energy",
    "electronic_friendly": "Works well with electronic/dance",
    "folk_friendly": "Works well with acoustic/folk",
    "pop_friendly": "Works well with mainstream pop",
    "metal_friendly": "Works well with metal intensity",
    "rnb_friendly": "Works well with R&B sensuality",
    "prog_rock_friendly": "Works well with progressive rock - conceptual, philosophical, epic",
    "prog_metal_friendly": "Works well with progressive metal - metaphysical, intense, technical",
}


# =============================================================================
# GENRE -> TRAIT MAPPINGS
# =============================================================================

GENRE_TRAIT_MAP: Dict[str, Dict[str, float]] = {
    # Hip-hop / Rap (note: "hip-hop" and "hip hop" both map here via normalization)
    "hip-hop": {"hip_hop_friendly": 0.9, "braggadocio": 0.5, "urban": 0.6},
    "rap": {"hip_hop_friendly": 0.9, "braggadocio": 0.6, "urban": 0.6},
    "trap": {"hip_hop_friendly": 0.8, "dark": 0.5, "urban": 0.7, "party": 0.4},
    "drill": {"hip_hop_friendly": 0.8, "aggressive": 0.7, "dark": 0.6, "urban": 0.8},
    "conscious rap": {
        "hip_hop_friendly": 0.8,
        "political": 0.7,
        "introspective": 0.6,
        "narrative": 0.5,
    },
    "boom bap": {
        "hip_hop_friendly": 0.9,
        "narrative": 0.6,
        "urban": 0.7,
        "introspective": 0.5,
    },
    "gangsta rap": {
        "hip_hop_friendly": 0.8,
        "aggressive": 0.6,
        "urban": 0.8,
        "dark": 0.5,
    },
    # Hip-hop subgenres with distinct lyrical styles
    "mumble rap": {
        "hip_hop_friendly": 0.8,
        "party": 0.6,
        "braggadocio": 0.6,
        "urban": 0.5,
    },
    "melodic rap": {
        "hip_hop_friendly": 0.7,
        "romantic": 0.5,
        "vulnerable": 0.4,
        "emotional_intensity": 0.5,
    },
    "emo rap": {
        "hip_hop_friendly": 0.7,
        "melancholic": 0.8,
        "vulnerable": 0.7,
        "self_destructive": 0.6,
        "confessional": 0.6,
    },
    "sad rap": {
        "hip_hop_friendly": 0.7,
        "melancholic": 0.8,
        "vulnerable": 0.6,
        "confessional": 0.5,
    },
    "cloud rap": {
        "hip_hop_friendly": 0.7,
        "surreal": 0.7,
        "melancholic": 0.5,
        "urban": 0.4,
    },
    "lyrical rap": {
        "hip_hop_friendly": 0.9,
        "narrative": 0.7,
        "introspective": 0.6,
        "braggadocio": 0.4,
    },
    "underground hip-hop": {
        "hip_hop_friendly": 0.8,
        "introspective": 0.6,
        "narrative": 0.5,
        "dark": 0.4,
    },
    "alternative hip-hop": {
        "hip_hop_friendly": 0.7,
        "introspective": 0.6,
        "surreal": 0.4,
        "playful": 0.3,
    },
    "horrorcore": {
        "hip_hop_friendly": 0.7,
        "horror": 0.8,
        "dark": 0.9,
        "aggressive": 0.6,
    },
    "dirty south": {
        "hip_hop_friendly": 0.8,
        "party": 0.6,
        "braggadocio": 0.5,
        "urban": 0.6,
    },
    "southern rap": {
        "hip_hop_friendly": 0.8,
        "party": 0.5,
        "narrative": 0.4,
        "urban": 0.5,
    },
    "crunk": {
        "hip_hop_friendly": 0.8,
        "party": 0.8,
        "aggressive": 0.5,
        "urban": 0.5,
    },
    "g-funk": {
        "hip_hop_friendly": 0.8,
        "party": 0.5,
        "urban": 0.6,
        "playful": 0.3,
    },
    # Rock variants
    "rock": {"rock_friendly": 0.9, "emotional_intensity": 0.6},
    "rock and roll": {
        "rock_friendly": 0.9,
        "emotional_intensity": 0.6,
        "uplifting": 0.4,
    },
    "indie rock": {"rock_friendly": 0.7, "introspective": 0.6, "melancholic": 0.5},
    "alternative": {"rock_friendly": 0.8, "introspective": 0.5},
    "progressive rock": {
        "prog_rock_friendly": 0.9,
        "rock_friendly": 0.7,
        "introspective": 0.7,
        "narrative": 0.7,
        "spiritual": 0.5,
        "surreal": 0.4,
    },
    "prog": {
        "prog_rock_friendly": 0.8,
        "prog_metal_friendly": 0.6,
        "introspective": 0.7,
        "narrative": 0.6,
        "spiritual": 0.4,
    },
    "art rock": {
        "prog_rock_friendly": 0.7,
        "rock_friendly": 0.6,
        "surreal": 0.6,
        "introspective": 0.6,
        "narrative": 0.5,
    },
    "classic rock": {"rock_friendly": 0.9, "empowering": 0.5, "road": 0.4},
    "hard rock": {"rock_friendly": 0.9, "aggressive": 0.5, "empowering": 0.5},
    "punk": {"rock_friendly": 0.8, "aggressive": 0.6, "dark": 0.4},
    "post-punk": {"rock_friendly": 0.7, "dark": 0.6, "introspective": 0.5},
    "grunge": {"rock_friendly": 0.8, "dark": 0.6, "self_destructive": 0.5},
    "garage rock": {"rock_friendly": 0.8, "aggressive": 0.4, "playful": 0.3},
    # More rock subgenres
    "stoner rock": {"rock_friendly": 0.8, "surreal": 0.5, "dark": 0.4, "road": 0.4},
    "southern rock": {
        "rock_friendly": 0.8,
        "pastoral": 0.4,
        "road": 0.5,
        "uplifting": 0.3,
    },
    "blues rock": {
        "rock_friendly": 0.8,
        "melancholic": 0.5,
        "emotional_intensity": 0.5,
    },
    "psychedelic rock": {"rock_friendly": 0.7, "surreal": 0.8, "spiritual": 0.4},
    "psych rock": {"rock_friendly": 0.7, "surreal": 0.8, "spiritual": 0.4},
    "space rock": {
        "rock_friendly": 0.7,
        "surreal": 0.8,
        "spiritual": 0.5,
        "prog_rock_friendly": 0.4,
    },
    "noise rock": {
        "rock_friendly": 0.7,
        "aggressive": 0.7,
        "surreal": 0.5,
        "dark": 0.5,
    },
    "emo": {
        "rock_friendly": 0.7,
        "melancholic": 0.8,
        "vulnerable": 0.7,
        "confessional": 0.6,
    },
    "pop punk": {
        "rock_friendly": 0.7,
        "pop_friendly": 0.5,
        "playful": 0.4,
        "uplifting": 0.3,
    },
    "hardcore": {
        "rock_friendly": 0.7,
        "aggressive": 0.9,
        "dark": 0.5,
        "political": 0.4,
    },
    "hardcore punk": {
        "rock_friendly": 0.7,
        "aggressive": 0.9,
        "dark": 0.5,
        "political": 0.4,
    },
    "screamo": {
        "rock_friendly": 0.6,
        "aggressive": 0.8,
        "emotional_intensity": 0.9,
        "vulnerable": 0.5,
    },
    "post-rock": {
        "rock_friendly": 0.6,
        "introspective": 0.7,
        "surreal": 0.6,
        "melancholic": 0.5,
    },
    "math rock": {
        "rock_friendly": 0.7,
        "surreal": 0.5,
        "playful": 0.4,
        "prog_rock_friendly": 0.4,
    },
    "surf rock": {
        "rock_friendly": 0.8,
        "coastal": 0.7,
        "playful": 0.5,
        "uplifting": 0.4,
    },
    "britpop": {
        "rock_friendly": 0.7,
        "pop_friendly": 0.5,
        "playful": 0.4,
        "urban": 0.3,
    },
    "new wave": {
        "rock_friendly": 0.6,
        "electronic_friendly": 0.5,
        "dark": 0.4,
        "playful": 0.3,
    },
    "glam rock": {
        "rock_friendly": 0.8,
        "party": 0.5,
        "playful": 0.5,
        "braggadocio": 0.4,
    },
    "funk rock": {
        "rock_friendly": 0.7,
        "rnb_friendly": 0.5,
        "party": 0.5,
        "playful": 0.5,
        "coastal": 0.3,
    },
    "arena rock": {
        "rock_friendly": 0.9,
        "empowering": 0.7,
        "uplifting": 0.5,
        "emotional_intensity": 0.6,
    },
    # Metal
    "metal": {
        "metal_friendly": 0.9,
        "aggressive": 0.8,
        "dark": 0.7,
        "emotional_intensity": 0.8,
    },
    "heavy metal": {"metal_friendly": 0.9, "aggressive": 0.8, "dark": 0.7},
    "death metal": {
        "metal_friendly": 0.9,
        "aggressive": 0.9,
        "dark": 0.9,
        "horror": 0.6,
    },
    "black metal": {
        "metal_friendly": 0.9,
        "dark": 0.95,
        "spiritual": 0.4,
        "horror": 0.5,
    },
    "nu metal": {"metal_friendly": 0.8, "aggressive": 0.7, "emotional_intensity": 0.7},
    "glam metal": {
        "metal_friendly": 0.7,
        "party": 0.7,
        "playful": 0.5,
        "braggadocio": 0.5,
        "romantic": 0.4,
    },
    "thrash metal": {"metal_friendly": 0.9, "aggressive": 0.9, "dark": 0.6},
    "power metal": {
        "metal_friendly": 0.8,
        "empowering": 0.7,
        "uplifting": 0.5,
        "narrative": 0.5,
    },
    "doom metal": {"metal_friendly": 0.8, "dark": 0.9, "melancholic": 0.6},
    "progressive metal": {
        "prog_metal_friendly": 0.9,
        "metal_friendly": 0.7,
        "introspective": 0.8,
        "spiritual": 0.6,
        "surreal": 0.5,
        "narrative": 0.5,
    },
    "djent": {
        "prog_metal_friendly": 0.7,
        "metal_friendly": 0.8,
        "introspective": 0.5,
        "aggressive": 0.5,
    },
    "avant-garde metal": {
        "prog_metal_friendly": 0.7,
        "metal_friendly": 0.6,
        "surreal": 0.7,
        "absurdist": 0.4,
    },
    "math metal": {"prog_metal_friendly": 0.6, "metal_friendly": 0.7, "surreal": 0.5},
    "post-metal": {
        "prog_metal_friendly": 0.5,
        "metal_friendly": 0.6,
        "introspective": 0.7,
        "melancholic": 0.5,
        "spiritual": 0.4,
    },
    "sludge metal": {
        "metal_friendly": 0.8,
        "aggressive": 0.7,
        "dark": 0.8,
        "self_destructive": 0.5,
    },
    "stoner metal": {"metal_friendly": 0.7, "surreal": 0.5, "dark": 0.5, "road": 0.3},
    # More metal subgenres
    "symphonic metal": {
        "metal_friendly": 0.8,
        "emotional_intensity": 0.7,
        "narrative": 0.6,
        "uplifting": 0.4,
    },
    "folk metal": {
        "metal_friendly": 0.7,
        "folk_friendly": 0.5,
        "narrative": 0.5,
        "pastoral": 0.4,
    },
    "viking metal": {
        "metal_friendly": 0.8,
        "narrative": 0.6,
        "aggressive": 0.6,
        "spiritual": 0.3,
    },
    "industrial metal": {
        "metal_friendly": 0.8,
        "electronic_friendly": 0.4,
        "aggressive": 0.7,
        "dark": 0.6,
    },
    "groove metal": {"metal_friendly": 0.9, "aggressive": 0.7, "party": 0.3},
    "melodic death metal": {
        "metal_friendly": 0.9,
        "aggressive": 0.7,
        "melancholic": 0.5,
        "dark": 0.7,
    },
    "deathcore": {"metal_friendly": 0.9, "aggressive": 0.9, "dark": 0.8, "horror": 0.4},
    "metalcore": {
        "metal_friendly": 0.8,
        "aggressive": 0.7,
        "emotional_intensity": 0.6,
        "vulnerable": 0.3,
    },
    "pirate metal": {
        "metal_friendly": 0.7,
        "playful": 0.6,
        "narrative": 0.5,
        "party": 0.4,
    },
    "speed metal": {"metal_friendly": 0.9, "aggressive": 0.8, "empowering": 0.4},
    "gothic metal": {
        "metal_friendly": 0.8,
        "dark": 0.8,
        "romantic": 0.5,
        "melancholic": 0.5,
    },
    # Electronic
    "electronic": {"electronic_friendly": 0.9, "surreal": 0.4},
    "edm": {"electronic_friendly": 0.9, "party": 0.7, "uplifting": 0.5},
    "house": {"electronic_friendly": 0.9, "party": 0.6, "urban": 0.4},
    "techno": {"electronic_friendly": 0.9, "dark": 0.4, "urban": 0.5},
    "trance": {"electronic_friendly": 0.9, "uplifting": 0.6, "surreal": 0.5},
    "drum and bass": {"electronic_friendly": 0.8, "urban": 0.6, "aggressive": 0.4},
    "dubstep": {"electronic_friendly": 0.8, "aggressive": 0.5, "dark": 0.4},
    "synthwave": {
        "electronic_friendly": 0.8,
        "surreal": 0.6,
        "urban": 0.5,
        "road": 0.4,
    },
    "synthpop": {"electronic_friendly": 0.8, "pop_friendly": 0.7, "romantic": 0.4},
    # Electronic subgenres
    "future bass": {
        "electronic_friendly": 0.9,
        "uplifting": 0.6,
        "emotional_intensity": 0.5,
    },
    "lo-fi": {"electronic_friendly": 0.6, "introspective": 0.6, "melancholic": 0.4},
    "lofi": {"electronic_friendly": 0.6, "introspective": 0.6, "melancholic": 0.4},
    "chillhop": {
        "electronic_friendly": 0.6,
        "hip_hop_friendly": 0.4,
        "introspective": 0.5,
    },
    "breakbeat": {"electronic_friendly": 0.8, "aggressive": 0.4, "urban": 0.5},
    "hardstyle": {"electronic_friendly": 0.9, "aggressive": 0.7, "party": 0.6},
    "hardcore electronic": {"electronic_friendly": 0.9, "aggressive": 0.8, "dark": 0.5},
    "psytrance": {"electronic_friendly": 0.9, "surreal": 0.8, "spiritual": 0.5},
    "progressive house": {"electronic_friendly": 0.9, "uplifting": 0.5, "party": 0.4},
    "deep house": {"electronic_friendly": 0.9, "urban": 0.5, "romantic": 0.3},
    "electro house": {"electronic_friendly": 0.9, "party": 0.7, "aggressive": 0.3},
    "idm": {"electronic_friendly": 0.8, "surreal": 0.7, "introspective": 0.5},
    "downtempo": {"electronic_friendly": 0.7, "introspective": 0.6, "melancholic": 0.4},
    "chillout": {"electronic_friendly": 0.7, "introspective": 0.5, "surreal": 0.4},
    "trip-hop": {
        "electronic_friendly": 0.7,
        "dark": 0.5,
        "urban": 0.5,
        "introspective": 0.5,
    },
    "vaporwave": {
        "electronic_friendly": 0.7,
        "surreal": 0.8,
        "melancholic": 0.4,
        "playful": 0.3,
    },
    "witch house": {
        "electronic_friendly": 0.7,
        "dark": 0.9,
        "horror": 0.5,
        "surreal": 0.6,
    },
    "industrial": {"electronic_friendly": 0.6, "aggressive": 0.7, "dark": 0.7},
    "jungle": {"electronic_friendly": 0.8, "urban": 0.6, "aggressive": 0.4},
    "uk garage": {"electronic_friendly": 0.8, "urban": 0.6, "party": 0.5},
    "future garage": {"electronic_friendly": 0.8, "melancholic": 0.5, "urban": 0.5},
    "minimal techno": {"electronic_friendly": 0.9, "dark": 0.4, "introspective": 0.4},
    "acid house": {"electronic_friendly": 0.9, "surreal": 0.5, "party": 0.6},
    # Dream/Shoegaze
    "dream pop": {"surreal": 0.8, "melancholic": 0.5, "romantic": 0.5},
    "shoegaze": {"surreal": 0.9, "melancholic": 0.6, "introspective": 0.5},
    "ambient": {"surreal": 0.7, "introspective": 0.6},
    "ethereal": {"surreal": 0.8, "spiritual": 0.4},
    # Folk/Acoustic
    "folk": {
        "folk_friendly": 0.9,
        "pastoral": 0.6,
        "introspective": 0.5,
        "narrative": 0.5,
    },
    "indie folk": {"folk_friendly": 0.8, "introspective": 0.6, "melancholic": 0.4},
    "americana": {"folk_friendly": 0.8, "pastoral": 0.5, "road": 0.5, "narrative": 0.5},
    "bluegrass": {"folk_friendly": 0.8, "pastoral": 0.6, "uplifting": 0.3},
    "acoustic": {"folk_friendly": 0.7, "vulnerable": 0.5, "domestic": 0.4},
    # Country
    "country": {
        "folk_friendly": 0.7,
        "pastoral": 0.5,
        "romantic": 0.4,
        "narrative": 0.5,
    },
    "country rock": {"folk_friendly": 0.6, "rock_friendly": 0.5, "road": 0.4},
    "outlaw country": {"folk_friendly": 0.6, "dark": 0.4, "road": 0.5},
    # More country subgenres
    "bro country": {
        "folk_friendly": 0.5,
        "party": 0.6,
        "braggadocio": 0.4,
        "romantic": 0.3,
    },
    "alt country": {
        "folk_friendly": 0.7,
        "rock_friendly": 0.4,
        "melancholic": 0.4,
        "introspective": 0.4,
    },
    "country pop": {
        "folk_friendly": 0.5,
        "pop_friendly": 0.6,
        "romantic": 0.5,
        "uplifting": 0.3,
    },
    "honky tonk": {
        "folk_friendly": 0.7,
        "party": 0.5,
        "melancholic": 0.4,
        "narrative": 0.4,
    },
    "western": {"folk_friendly": 0.6, "narrative": 0.5, "pastoral": 0.5, "road": 0.4},
    "texas country": {
        "folk_friendly": 0.7,
        "narrative": 0.5,
        "pastoral": 0.4,
        "road": 0.4,
    },
    "red dirt": {
        "folk_friendly": 0.7,
        "rock_friendly": 0.4,
        "road": 0.5,
        "narrative": 0.4,
    },
    "cowpunk": {
        "folk_friendly": 0.5,
        "rock_friendly": 0.6,
        "aggressive": 0.4,
        "playful": 0.4,
    },
    # More folk subgenres
    "celtic": {
        "folk_friendly": 0.8,
        "pastoral": 0.5,
        "narrative": 0.5,
        "spiritual": 0.3,
    },
    "freak folk": {"folk_friendly": 0.7, "surreal": 0.6, "playful": 0.4},
    "neofolk": {"folk_friendly": 0.7, "dark": 0.5, "spiritual": 0.4, "narrative": 0.4},
    "chamber folk": {"folk_friendly": 0.8, "introspective": 0.6, "melancholic": 0.4},
    "anti-folk": {"folk_friendly": 0.6, "playful": 0.5, "absurdist": 0.4},
    # Pop
    "pop": {"pop_friendly": 0.9, "uplifting": 0.4, "romantic": 0.4},
    "indie pop": {"pop_friendly": 0.7, "introspective": 0.5, "playful": 0.4},
    "art pop": {"pop_friendly": 0.6, "surreal": 0.5, "introspective": 0.4},
    "dance pop": {"pop_friendly": 0.8, "party": 0.6, "uplifting": 0.5},
    "dark pop": {"pop_friendly": 0.7, "dark": 0.7, "surreal": 0.5, "vulnerable": 0.5},
    "electropop": {"pop_friendly": 0.8, "electronic_friendly": 0.7, "party": 0.4},
    "hyperpop": {
        "pop_friendly": 0.6,
        "electronic_friendly": 0.7,
        "surreal": 0.6,
        "playful": 0.5,
    },
    # More pop subgenres
    "k-pop": {"pop_friendly": 0.9, "party": 0.5, "romantic": 0.4, "uplifting": 0.4},
    "kpop": {"pop_friendly": 0.9, "party": 0.5, "romantic": 0.4, "uplifting": 0.4},
    "j-pop": {"pop_friendly": 0.9, "playful": 0.5, "romantic": 0.4, "uplifting": 0.4},
    "jpop": {"pop_friendly": 0.9, "playful": 0.5, "romantic": 0.4, "uplifting": 0.4},
    "bubblegum pop": {
        "pop_friendly": 0.9,
        "playful": 0.7,
        "uplifting": 0.6,
        "romantic": 0.4,
    },
    "teen pop": {"pop_friendly": 0.9, "romantic": 0.6, "uplifting": 0.5},
    "bedroom pop": {
        "pop_friendly": 0.7,
        "introspective": 0.6,
        "vulnerable": 0.5,
        "melancholic": 0.3,
    },
    "chamber pop": {
        "pop_friendly": 0.6,
        "introspective": 0.5,
        "emotional_intensity": 0.5,
    },
    "city pop": {"pop_friendly": 0.7, "urban": 0.6, "romantic": 0.5, "uplifting": 0.4},
    "sophisti-pop": {"pop_friendly": 0.7, "romantic": 0.5, "urban": 0.4},
    "baroque pop": {
        "pop_friendly": 0.6,
        "surreal": 0.4,
        "narrative": 0.4,
        "emotional_intensity": 0.4,
    },
    # R&B / Soul
    "r&b": {"rnb_friendly": 0.9, "romantic": 0.7, "vulnerable": 0.5},
    "soul": {"rnb_friendly": 0.8, "emotional_intensity": 0.6, "vulnerable": 0.5},
    "neo soul": {"rnb_friendly": 0.8, "introspective": 0.5, "spiritual": 0.3},
    "funk": {"rnb_friendly": 0.7, "party": 0.5, "playful": 0.5},
    # More R&B subgenres
    "quiet storm": {"rnb_friendly": 0.9, "romantic": 0.8, "vulnerable": 0.5},
    "new jack swing": {"rnb_friendly": 0.8, "hip_hop_friendly": 0.5, "party": 0.5},
    "alternative r&b": {
        "rnb_friendly": 0.8,
        "introspective": 0.5,
        "surreal": 0.4,
        "dark": 0.3,
    },
    "alt r&b": {"rnb_friendly": 0.8, "introspective": 0.5, "surreal": 0.4, "dark": 0.3},
    "contemporary r&b": {"rnb_friendly": 0.9, "romantic": 0.6, "vulnerable": 0.4},
    "pbr&b": {"rnb_friendly": 0.8, "introspective": 0.5, "melancholic": 0.4},
    # Jazz
    "jazz": {"introspective": 0.5, "romantic": 0.4, "urban": 0.4},
    "smooth jazz": {"romantic": 0.5, "urban": 0.3},
    # Other
    "disco": {"party": 0.7, "uplifting": 0.5, "urban": 0.4},
    "reggae": {"uplifting": 0.4, "spiritual": 0.4, "playful": 0.3},
    "ska": {"playful": 0.6, "uplifting": 0.4},
    "gospel": {"spiritual": 0.8, "uplifting": 0.6, "emotional_intensity": 0.6},
    "classical": {"emotional_intensity": 0.5, "introspective": 0.4},
    # Latin / Regional Mexican
    "latin": {"romantic": 0.5, "party": 0.5},
    "reggaeton": {"hip_hop_friendly": 0.5, "party": 0.7, "urban": 0.5, "romantic": 0.4},
    "latin trap": {"hip_hop_friendly": 0.7, "dark": 0.4, "urban": 0.6, "party": 0.4},
    "latin pop": {"pop_friendly": 0.7, "romantic": 0.6, "party": 0.4},
    "bachata": {"romantic": 0.8, "melancholic": 0.4, "vulnerable": 0.4},
    "salsa": {"party": 0.6, "romantic": 0.5, "uplifting": 0.4},
    "cumbia": {"party": 0.6, "uplifting": 0.4, "playful": 0.4},
    "norteño": {"folk_friendly": 0.5, "narrative": 0.5, "romantic": 0.4},
    "banda": {"party": 0.5, "romantic": 0.5, "uplifting": 0.3},
    "corrido": {"narrative": 0.8, "folk_friendly": 0.5, "dark": 0.4},
    "regional mexican": {"folk_friendly": 0.5, "narrative": 0.4, "romantic": 0.4},
    "bossa nova": {"romantic": 0.6, "introspective": 0.5, "coastal": 0.4},
    "samba": {"party": 0.6, "uplifting": 0.5, "playful": 0.4},
    # Caribbean / African
    "dancehall": {"hip_hop_friendly": 0.5, "party": 0.7, "braggadocio": 0.4},
    "afrobeat": {"party": 0.5, "political": 0.4, "uplifting": 0.4, "spiritual": 0.3},
    "afrobeats": {"party": 0.6, "romantic": 0.4, "uplifting": 0.4},
    "soca": {"party": 0.8, "uplifting": 0.5, "playful": 0.4},
    "zouk": {"romantic": 0.7, "party": 0.4},
    # UK / Grime
    "grime": {
        "hip_hop_friendly": 0.7,
        "aggressive": 0.6,
        "urban": 0.8,
        "braggadocio": 0.5,
    },
    "uk drill": {"hip_hop_friendly": 0.8, "aggressive": 0.7, "dark": 0.7, "urban": 0.9},
    "garage": {"electronic_friendly": 0.7, "urban": 0.6, "party": 0.5},
    "2-step": {"electronic_friendly": 0.7, "urban": 0.5, "romantic": 0.4},
    # Jazz extended
    "bebop": {"introspective": 0.5, "urban": 0.4},
    "free jazz": {"surreal": 0.6, "aggressive": 0.4, "introspective": 0.4},
    "jazz fusion": {"introspective": 0.5, "prog_rock_friendly": 0.3},
    "acid jazz": {"urban": 0.5, "party": 0.4, "rnb_friendly": 0.3},
    # World / Misc
    "world music": {"spiritual": 0.4, "narrative": 0.4, "pastoral": 0.3},
    "flamenco": {"emotional_intensity": 0.7, "romantic": 0.5, "melancholic": 0.4},
    "fado": {"melancholic": 0.8, "romantic": 0.5, "vulnerable": 0.5},
    "klezmer": {"playful": 0.5, "melancholic": 0.4, "emotional_intensity": 0.4},
    "polka": {"playful": 0.6, "party": 0.5, "uplifting": 0.4},
    "mariachi": {"romantic": 0.6, "emotional_intensity": 0.5, "narrative": 0.4},
}


# =============================================================================
# MOOD -> TRAIT MAPPINGS
# =============================================================================

MOOD_TRAIT_MAP: Dict[str, Dict[str, float]] = {
    "dark": {"dark": 0.9, "melancholic": 0.4},
    "uplifting": {"uplifting": 0.9, "empowering": 0.4},
    "melancholic": {"melancholic": 0.9, "introspective": 0.3},
    "sad": {"melancholic": 0.8, "vulnerable": 0.4},
    "romantic": {"romantic": 0.9, "vulnerable": 0.3},
    "aggressive": {"aggressive": 0.9, "dark": 0.4, "emotional_intensity": 0.6},
    "angry": {"aggressive": 0.8, "dark": 0.3},
    "dreamy": {"surreal": 0.8, "romantic": 0.3},
    "ethereal": {"surreal": 0.7, "spiritual": 0.3},
    "playful": {"playful": 0.9, "uplifting": 0.3},
    "fun": {"playful": 0.7, "party": 0.4},
    "introspective": {"introspective": 0.9},
    "reflective": {"introspective": 0.7, "melancholic": 0.3},
    "nostalgic": {"melancholic": 0.5, "introspective": 0.4, "domestic": 0.3},
    "empowering": {"empowering": 0.9, "uplifting": 0.4},
    "confident": {"empowering": 0.6, "braggadocio": 0.5},
    "rebellious": {"aggressive": 0.5, "dark": 0.3, "empowering": 0.4},
    "sensual": {"romantic": 0.6, "rnb_friendly": 0.4},
    "intense": {"emotional_intensity": 0.9, "aggressive": 0.3},
    "chill": {"introspective": 0.4, "surreal": 0.3},
    "relaxed": {"introspective": 0.3, "pastoral": 0.3},
    "haunting": {"dark": 0.6, "surreal": 0.5, "melancholic": 0.4},
    "euphoric": {"uplifting": 0.8, "party": 0.5, "emotional_intensity": 0.5},
    "bittersweet": {"melancholic": 0.6, "romantic": 0.4},
    "vulnerable": {"vulnerable": 0.9, "confessional": 0.5},
    "raw": {"vulnerable": 0.6, "emotional_intensity": 0.6, "confessional": 0.4},
    # Comedy / Absurdist
    "comedy": {"absurdist": 0.9, "playful": 0.8},
    "funny": {"absurdist": 0.8, "playful": 0.7},
    "parody": {"absurdist": 0.9, "playful": 0.6},
    "satirical": {"absurdist": 0.8, "political": 0.4, "playful": 0.5},
    "absurd": {"absurdist": 0.95, "playful": 0.5},
    "weird": {"absurdist": 0.7, "surreal": 0.6},
    "quirky": {"absurdist": 0.5, "playful": 0.6},
    # Additional moods
    "epic": {"emotional_intensity": 0.8, "empowering": 0.6, "narrative": 0.5},
    "cinematic": {"emotional_intensity": 0.7, "narrative": 0.6, "surreal": 0.3},
    "anthemic": {"empowering": 0.8, "uplifting": 0.6, "emotional_intensity": 0.6},
    "gritty": {"dark": 0.6, "urban": 0.5, "aggressive": 0.4},
    "moody": {"dark": 0.5, "introspective": 0.6, "melancholic": 0.4},
    "groovy": {"party": 0.6, "playful": 0.5, "rnb_friendly": 0.4},
    "trippy": {"surreal": 0.9, "spiritual": 0.4, "dark": 0.2},
    "psychedelic": {"surreal": 0.9, "spiritual": 0.5, "introspective": 0.4},
    "spooky": {"horror": 0.8, "dark": 0.6},
    "creepy": {"horror": 0.9, "dark": 0.7},
    # Altered states
    "manic": {"emotional_intensity": 0.9, "aggressive": 0.4, "self_destructive": 0.5},
    "frantic": {"emotional_intensity": 0.8, "aggressive": 0.5},
    "numb": {
        "melancholic": 0.6,
        "self_destructive": 0.6,
        "vulnerable": 0.5,
        "dark": 0.4,
    },
    "dissociative": {
        "surreal": 0.7,
        "introspective": 0.6,
        "vulnerable": 0.5,
        "dark": 0.4,
    },
    "detached": {"surreal": 0.5, "introspective": 0.6, "melancholic": 0.4},
    "hazy": {"surreal": 0.6, "melancholic": 0.5, "introspective": 0.4},
    "foggy": {"surreal": 0.5, "melancholic": 0.4, "introspective": 0.4},
    "wired": {"emotional_intensity": 0.7, "aggressive": 0.4, "urban": 0.3},
    # Whimsical / storytelling
    "whimsical": {
        "playful": 0.8,
        "folk_friendly": 0.5,
        "narrative": 0.5,
        "pastoral": 0.4,
    },
    "folksy": {"folk_friendly": 0.9, "pastoral": 0.6, "narrative": 0.5, "playful": 0.3},
    "storytelling": {"narrative": 0.9, "folk_friendly": 0.5},
    "charming": {"playful": 0.6, "folk_friendly": 0.4, "romantic": 0.3},
    "rustic": {"pastoral": 0.8, "folk_friendly": 0.7, "domestic": 0.4},
}


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================


def score_bank_match(
    request_traits: Dict[str, float],
    bank_traits: Dict[str, float],
) -> float:
    """
    Score how well a bank matches a request's trait profile.

    Uses dot product of overlapping traits.

    Args:
        request_traits: What the user wants (trait_id -> weight)
        bank_traits: What the bank provides (trait_id -> weight)

    Returns:
        Match score (higher = better match)
    """
    score = 0.0
    for trait_id, request_weight in request_traits.items():
        bank_weight = bank_traits.get(trait_id, 0.0)
        score += request_weight * bank_weight
    return score


def scores_to_probabilities(
    scores: Dict[str, float],
    temperature: float = 1.0,
    min_score_threshold: float = 0.3,
) -> Dict[str, float]:
    """
    Convert bank scores to selection probabilities via softmax.

    Args:
        scores: bank_id -> match score
        temperature: Controls randomness (lower = more deterministic)
        min_score_threshold: Banks scoring below this get filtered out

    Returns:
        bank_id -> selection probability
    """
    if not scores:
        return {}

    # Filter out very low scores
    filtered_scores = {k: v for k, v in scores.items() if v >= min_score_threshold}

    # If all filtered out, use original scores
    if not filtered_scores:
        filtered_scores = scores

    # Apply temperature and compute exp (subtract max for numerical stability)
    max_score = max(filtered_scores.values())
    exp_scores = {
        k: math.exp((v - max_score) / temperature) for k, v in filtered_scores.items()
    }

    total = sum(exp_scores.values())
    if total == 0:
        # Fallback to uniform
        n = len(filtered_scores)
        return {k: 1.0 / n for k in filtered_scores}

    return {k: v / total for k, v in exp_scores.items()}


def infer_traits_from_tags(tags: List[str]) -> Dict[str, float]:
    """
    Infer trait weights from user-provided tags (genres, moods, artists).

    This is the fast heuristic path - no LLM, just keyword matching.
    Uses max-pooling when multiple tags contribute to the same trait.

    Args:
        tags: List of user-provided tags (genres, moods, etc.)

    Returns:
        Dict of trait_id -> weight
    """
    # Alias normalization: map common variants to canonical forms
    GENRE_ALIASES: Dict[str, str] = {
        "hip hop": "hip-hop",
        "prog rock": "progressive rock",
        "prog metal": "progressive metal",
        "rnb": "r&b",
        "alt rock": "alternative",
        "hair metal": "glam metal",
        "synth pop": "synthpop",
        "lyrical hip-hop": "lyrical rap",
    }

    traits: Dict[str, float] = {}

    for tag in tags:
        tag_lower = tag.lower().strip()
        # Apply alias normalization
        tag_lower = GENRE_ALIASES.get(tag_lower, tag_lower)

        # Check genre mappings - prefer exact and longer matches
        best_genre_match = None
        best_genre_len = 0
        for genre in GENRE_TRAIT_MAP:
            # Exact match is best
            if genre == tag_lower:
                best_genre_match = genre
                break
            # Only match if genre is a substantial part of the tag
            # This prevents "punk" matching "Daft Punk" (artist name)
            if genre in tag_lower:
                # Genre must be at least 50% of the tag length to match
                if len(genre) >= len(tag_lower) * 0.5 and len(genre) > best_genre_len:
                    best_genre_match = genre
                    best_genre_len = len(genre)
            elif tag_lower in genre:
                if len(genre) > best_genre_len:
                    best_genre_match = genre
                    best_genre_len = len(genre)

        if best_genre_match:
            for trait_id, weight in GENRE_TRAIT_MAP[best_genre_match].items():
                traits[trait_id] = max(traits.get(trait_id, 0), weight)
            continue

        # Check mood mappings - prefer exact and longer matches
        best_mood_match = None
        best_mood_len = 0
        for mood in MOOD_TRAIT_MAP:
            # Exact match is best
            if mood == tag_lower:
                best_mood_match = mood
                break
            # Only match if mood is a substantial part of the tag
            if mood in tag_lower:
                # Mood must be at least 50% of the tag length to match
                if len(mood) >= len(tag_lower) * 0.5 and len(mood) > best_mood_len:
                    best_mood_match = mood
                    best_mood_len = len(mood)
            elif tag_lower in mood:
                if len(mood) > best_mood_len:
                    best_mood_match = mood
                    best_mood_len = len(mood)

        if best_mood_match:
            for trait_id, weight in MOOD_TRAIT_MAP[best_mood_match].items():
                traits[trait_id] = max(traits.get(trait_id, 0), weight)

    return traits


def get_default_traits() -> Dict[str, float]:
    """
    Return default trait weights when no context is provided.

    Biased toward common, broadly appealing topics.
    """
    return {
        "introspective": 0.5,
        "romantic": 0.4,
        "melancholic": 0.4,
        "uplifting": 0.4,
        "emotional_intensity": 0.5,
    }


# =============================================================================
# STYLE PROMPT -> TRAIT EXTRACTION
# =============================================================================

# Keywords in style_prompt that map to traits
# Format: keyword -> {trait: weight_boost}
STYLE_PROMPT_KEYWORDS: Dict[str, Dict[str, float]] = {
    # Emotional/mood keywords
    "dark": {"dark": 0.7, "melancholic": 0.3},
    "darkness": {"dark": 0.7, "melancholic": 0.3},
    "light": {"uplifting": 0.5, "playful": 0.3},
    "bright": {"uplifting": 0.6, "playful": 0.3},
    "sad": {"melancholic": 0.7, "vulnerable": 0.4},
    "sadness": {"melancholic": 0.7, "vulnerable": 0.4},
    "melancholy": {"melancholic": 0.8, "introspective": 0.3},
    "melancholic": {"melancholic": 0.8, "introspective": 0.3},
    "happy": {"uplifting": 0.7, "playful": 0.4},
    "joyful": {"uplifting": 0.8, "playful": 0.4},
    "angry": {"aggressive": 0.7, "dark": 0.3},
    "rage": {"aggressive": 0.8, "dark": 0.4},
    "aggressive": {"aggressive": 0.8, "dark": 0.3},
    "intense": {"emotional_intensity": 0.8, "aggressive": 0.3},
    "emotional": {"emotional_intensity": 0.7, "vulnerable": 0.4},
    "vulnerable": {"vulnerable": 0.8, "confessional": 0.4},
    "raw": {"vulnerable": 0.6, "confessional": 0.5},
    "honest": {"confessional": 0.7, "vulnerable": 0.4},
    "haunting": {"dark": 0.6, "surreal": 0.5, "melancholic": 0.4},
    "ethereal": {"surreal": 0.7, "spiritual": 0.3},
    "dreamy": {"surreal": 0.7, "romantic": 0.3},
    "trippy": {"surreal": 0.8, "dark": 0.3},
    "psychedelic": {"surreal": 0.8, "spiritual": 0.3},
    "nostalgic": {"melancholic": 0.5, "introspective": 0.5},
    "longing": {"melancholic": 0.6, "romantic": 0.4},
    "yearning": {"melancholic": 0.6, "romantic": 0.5},
    "bittersweet": {"melancholic": 0.6, "romantic": 0.4},
    "hopeful": {"uplifting": 0.7, "empowering": 0.3},
    "hopeless": {"melancholic": 0.7, "dark": 0.4},
    "desperate": {"emotional_intensity": 0.7, "dark": 0.4},
    "euphoric": {"uplifting": 0.8, "party": 0.4},
    "manic": {"emotional_intensity": 0.7, "surreal": 0.4},
    "anxious": {"dark": 0.4, "introspective": 0.5},
    "peaceful": {"introspective": 0.5, "pastoral": 0.4},
    "serene": {"introspective": 0.5, "pastoral": 0.4},
    "chaotic": {"aggressive": 0.5, "surreal": 0.5},
    "wild": {"aggressive": 0.4, "party": 0.5},
    # Thematic keywords
    "love": {"romantic": 0.8},
    "romance": {"romantic": 0.8},
    "romantic": {"romantic": 0.8},
    "heartbreak": {"melancholic": 0.7, "romantic": 0.4, "vulnerable": 0.4},
    "breakup": {"melancholic": 0.6, "romantic": 0.3, "confessional": 0.4},
    "loss": {"melancholic": 0.7, "grief": 0.5},
    "grief": {"grief": 0.8, "melancholic": 0.5},
    "death": {"dark": 0.6, "grief": 0.5, "melancholic": 0.4},
    "dying": {"dark": 0.6, "grief": 0.4},
    "lonely": {"melancholic": 0.6, "introspective": 0.5},
    "loneliness": {"melancholic": 0.6, "introspective": 0.5},
    "isolation": {"melancholic": 0.5, "introspective": 0.6, "dark": 0.3},
    "alone": {"melancholic": 0.5, "introspective": 0.5},
    "party": {"party": 0.8, "uplifting": 0.3},
    "club": {"party": 0.7, "urban": 0.5},
    "dance": {"party": 0.6, "uplifting": 0.4},
    "night": {"urban": 0.4, "dark": 0.3},
    "city": {"urban": 0.7},
    "urban": {"urban": 0.8},
    "street": {"urban": 0.6, "hip_hop_friendly": 0.4},
    "nature": {"pastoral": 0.7, "spiritual": 0.3},
    "forest": {"pastoral": 0.6, "surreal": 0.3},
    "ocean": {"coastal": 0.7, "melancholic": 0.3},
    "sea": {"coastal": 0.6},
    "beach": {"coastal": 0.7, "uplifting": 0.3},
    "summer": {"uplifting": 0.5, "coastal": 0.4},
    "winter": {"melancholic": 0.5, "introspective": 0.4},
    "rain": {"melancholic": 0.5, "introspective": 0.4},
    "sun": {"uplifting": 0.5},
    "road": {"road": 0.7, "narrative": 0.3},
    "travel": {"road": 0.6, "narrative": 0.3},
    "journey": {"road": 0.5, "narrative": 0.5, "spiritual": 0.3},
    "home": {"domestic": 0.7, "nostalgic": 0.3},
    "childhood": {"nostalgic": 0.6, "introspective": 0.4},
    "memory": {"nostalgic": 0.5, "introspective": 0.5},
    "memories": {"nostalgic": 0.5, "introspective": 0.5},
    "past": {"nostalgic": 0.5, "melancholic": 0.3},
    "future": {"spiritual": 0.3, "empowering": 0.3},
    "spiritual": {"spiritual": 0.8},
    "religious": {"spiritual": 0.7},
    "god": {"spiritual": 0.6},
    "soul": {"spiritual": 0.5, "rnb_friendly": 0.3},
    "existential": {"spiritual": 0.5, "introspective": 0.6},
    "meaning": {"spiritual": 0.4, "introspective": 0.5},
    "political": {"political": 0.8},
    "protest": {"political": 0.7, "aggressive": 0.3},
    "revolution": {"political": 0.6, "aggressive": 0.4, "empowering": 0.3},
    "society": {"political": 0.5, "introspective": 0.3},
    "system": {"political": 0.5, "dark": 0.3},
    "war": {"political": 0.5, "dark": 0.5, "aggressive": 0.4},
    "power": {"empowering": 0.6, "political": 0.3},
    "freedom": {"empowering": 0.6, "political": 0.3},
    "rebellion": {"aggressive": 0.4, "empowering": 0.5},
    "fight": {"aggressive": 0.5, "empowering": 0.4},
    "horror": {"horror": 0.8, "dark": 0.5},
    "scary": {"horror": 0.6, "dark": 0.4},
    "creepy": {"horror": 0.6, "dark": 0.5},
    "gothic": {"dark": 0.6, "horror": 0.4, "romantic": 0.3},
    "supernatural": {"horror": 0.5, "surreal": 0.5},
    "weird": {"absurdist": 0.6, "surreal": 0.4},
    "absurd": {"absurdist": 0.7, "playful": 0.3},
    "funny": {"absurdist": 0.5, "playful": 0.6},
    "comedy": {"absurdist": 0.6, "playful": 0.5},
    "silly": {"playful": 0.7, "absurdist": 0.4},
    "playful": {"playful": 0.8},
    "fun": {"playful": 0.6, "party": 0.4},
    "sexy": {"romantic": 0.5, "rnb_friendly": 0.4},
    "sensual": {"romantic": 0.6, "rnb_friendly": 0.4},
    "lust": {"romantic": 0.5, "obsessive": 0.4},
    "obsession": {"obsessive": 0.7, "dark": 0.3},
    "obsessive": {"obsessive": 0.7, "dark": 0.3},
    "addiction": {"self_destructive": 0.6, "obsessive": 0.4},
    "toxic": {"obsessive": 0.5, "self_destructive": 0.4, "dark": 0.3},
    "drugs": {"self_destructive": 0.5, "surreal": 0.4},
    "drunk": {"self_destructive": 0.4, "party": 0.4},
    "high": {"surreal": 0.4, "self_destructive": 0.3},
    "escape": {"road": 0.4, "self_destructive": 0.3},
    "running": {"road": 0.5, "emotional_intensity": 0.3},
    "free": {"empowering": 0.5, "road": 0.3},
    "trapped": {"dark": 0.5, "melancholic": 0.4},
    "lost": {"melancholic": 0.5, "introspective": 0.4},
    "found": {"uplifting": 0.4, "empowering": 0.3},
    "growing": {"empowering": 0.5, "identity_seeking": 0.4},
    "becoming": {"identity_seeking": 0.6, "empowering": 0.3},
    "identity": {"identity_seeking": 0.7, "introspective": 0.4},
    "self": {"introspective": 0.6, "identity_seeking": 0.3},
    "confidence": {"braggadocio": 0.5, "empowering": 0.4},
    "flex": {"braggadocio": 0.7, "hip_hop_friendly": 0.3},
    "success": {"braggadocio": 0.5, "empowering": 0.4},
    "hustle": {"braggadocio": 0.4, "hip_hop_friendly": 0.5},
    "grind": {"braggadocio": 0.4, "hip_hop_friendly": 0.4},
    "money": {"braggadocio": 0.5, "urban": 0.3},
    "rich": {"braggadocio": 0.5},
    "fame": {"braggadocio": 0.4, "urban": 0.3},
    "story": {"narrative": 0.7},
    "storytelling": {"narrative": 0.8, "folk_friendly": 0.3},
    "tale": {"narrative": 0.6, "folk_friendly": 0.3},
    "epic": {"narrative": 0.5, "emotional_intensity": 0.4},
    # Sonic/production keywords that imply mood
    "heavy": {"aggressive": 0.5, "metal_friendly": 0.4},
    "loud": {"aggressive": 0.4, "rock_friendly": 0.3},
    "soft": {"vulnerable": 0.4, "introspective": 0.3},
    "quiet": {"introspective": 0.5, "vulnerable": 0.3},
    "distorted": {"aggressive": 0.4, "dark": 0.3},
    "ambient": {"surreal": 0.5, "introspective": 0.4},
    "atmospheric": {"surreal": 0.5, "melancholic": 0.3},
    "shoegaze": {"surreal": 0.6, "melancholic": 0.4},
    "hazy": {"surreal": 0.5, "melancholic": 0.3},
    "fuzzy": {"surreal": 0.4, "rock_friendly": 0.3},
    "clean": {"pop_friendly": 0.3},
    "polished": {"pop_friendly": 0.3},
    "lo-fi": {"introspective": 0.4, "melancholic": 0.3},
    "lofi": {"introspective": 0.4, "melancholic": 0.3},
    "chill": {"introspective": 0.4},
    "upbeat": {"uplifting": 0.6, "party": 0.3},
    "groovy": {"party": 0.4, "playful": 0.4},
    "funky": {"party": 0.4, "playful": 0.5, "rnb_friendly": 0.3},
    "soulful": {"rnb_friendly": 0.5, "emotional_intensity": 0.4},
    "bluesy": {"melancholic": 0.4, "rock_friendly": 0.3},
    "jazzy": {"introspective": 0.3, "romantic": 0.3},
}


def extract_traits_from_style_prompt(style_prompt: str) -> Dict[str, float]:
    """
    Extract trait signals from a free-text style prompt.

    Scans for keywords that map to traits and aggregates them.
    Uses max-pooling when multiple keywords contribute to the same trait.

    Args:
        style_prompt: Free-text description of the desired style.

    Returns:
        Dict of trait_id -> weight (all weights are slightly reduced from
        tag-based extraction to avoid overpowering explicit tags).
    """
    if not style_prompt:
        return {}

    traits: Dict[str, float] = {}
    prompt_lower = style_prompt.lower()

    # Also try to extract genre/mood terms directly (scan for GENRE_TRAIT_MAP keys)
    for genre, genre_traits in GENRE_TRAIT_MAP.items():
        if genre in prompt_lower:
            for trait_id, weight in genre_traits.items():
                # Reduce weight slightly since it's from style_prompt not explicit tag
                adjusted = weight * 0.7
                traits[trait_id] = max(traits.get(trait_id, 0), adjusted)

    for mood, mood_traits in MOOD_TRAIT_MAP.items():
        if mood in prompt_lower:
            for trait_id, weight in mood_traits.items():
                adjusted = weight * 0.7
                traits[trait_id] = max(traits.get(trait_id, 0), adjusted)

    # Scan for style prompt keywords
    for keyword, keyword_traits in STYLE_PROMPT_KEYWORDS.items():
        # Word boundary check to avoid partial matches
        import re

        if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
            for trait_id, weight in keyword_traits.items():
                # Style prompt keywords get slightly lower weight than explicit tags
                adjusted = weight * 0.8
                traits[trait_id] = max(traits.get(trait_id, 0), adjusted)

    return traits


def merge_traits(
    *trait_dicts: Dict[str, float],
    strategy: str = "max",
) -> Dict[str, float]:
    """
    Merge multiple trait dictionaries.

    Args:
        *trait_dicts: Variable number of trait dictionaries to merge.
        strategy: How to combine overlapping traits.
            - "max": Take the maximum value (default)
            - "sum": Sum values (capped at 1.0)
            - "avg": Average values

    Returns:
        Merged trait dictionary.
    """
    result: Dict[str, float] = {}

    for traits in trait_dicts:
        for trait_id, weight in traits.items():
            if trait_id not in result:
                result[trait_id] = weight
            elif strategy == "max":
                result[trait_id] = max(result[trait_id], weight)
            elif strategy == "sum":
                result[trait_id] = min(1.0, result[trait_id] + weight)
            elif strategy == "avg":
                # Running average
                result[trait_id] = (result[trait_id] + weight) / 2

    return result
