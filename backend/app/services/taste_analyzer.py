"""
Taste Profile Analyzer
Derives music taste insights from Spotify data
"""

from collections import Counter
from typing import List

from app.schemas.spotify import SpotifyArtist, SpotifyTrack, TasteProfile


# Genre to mood mapping (heuristic)
GENRE_MOOD_MAP = {
    # Energetic
    "edm": ["energetic", "uplifting"],
    "dance": ["energetic", "groovy"],
    "electronic": ["atmospheric", "modern"],
    "house": ["groovy", "energetic"],
    "techno": ["hypnotic", "dark"],
    "drum and bass": ["intense", "energetic"],
    
    # Rock variants
    "rock": ["powerful", "raw"],
    "indie rock": ["introspective", "authentic"],
    "alternative rock": ["moody", "experimental"],
    "punk": ["rebellious", "raw"],
    "metal": ["intense", "powerful"],
    "grunge": ["melancholic", "raw"],
    
    # Chill/Ambient
    "ambient": ["ethereal", "dreamy"],
    "chill": ["relaxed", "smooth"],
    "lo-fi": ["nostalgic", "mellow"],
    "dream pop": ["ethereal", "hazy"],
    "shoegaze": ["atmospheric", "dreamy"],
    
    # Hip-hop/R&B
    "hip hop": ["confident", "rhythmic"],
    "rap": ["confident", "bold"],
    "r&b": ["soulful", "smooth"],
    "soul": ["emotional", "warm"],
    "trap": ["dark", "hard-hitting"],
    
    # Pop
    "pop": ["catchy", "uplifting"],
    "indie pop": ["whimsical", "fresh"],
    "synth-pop": ["retro", "atmospheric"],
    "art pop": ["experimental", "theatrical"],
    
    # Folk/Acoustic
    "folk": ["earthy", "storytelling"],
    "acoustic": ["intimate", "raw"],
    "singer-songwriter": ["personal", "emotional"],
    "americana": ["nostalgic", "earthy"],
    
    # Jazz/Blues
    "jazz": ["sophisticated", "improvisational"],
    "blues": ["soulful", "melancholic"],
    "neo-soul": ["smooth", "contemporary"],
    
    # Classical/Orchestral
    "classical": ["grand", "emotional"],
    "orchestral": ["cinematic", "dramatic"],
    "soundtrack": ["cinematic", "evocative"],
    
    # World/Latin
    "latin": ["passionate", "rhythmic"],
    "reggaeton": ["energetic", "tropical"],
    "afrobeat": ["groovy", "joyful"],
    
    # Other
    "experimental": ["avant-garde", "unpredictable"],
    "psychedelic": ["trippy", "expansive"],
    "post-punk": ["angular", "dark"],
    "emo": ["emotional", "intense"],
}


def build_taste_profile(
    top_artists: List[SpotifyArtist],
    top_tracks: List[SpotifyTrack]
) -> TasteProfile:
    """
    Analyze user's music taste and build a profile
    
    Args:
        top_artists: List of user's top artists
        top_tracks: List of user's top tracks
    
    Returns:
        TasteProfile with genres, moods, summary, and banned references
    """
    # Count genres from artists
    genre_counter = Counter()
    for artist in top_artists:
        for genre in artist.genres:
            genre_counter[genre] += 1
    
    # Get ranked genres
    top_genres = [genre for genre, _ in genre_counter.most_common(10)]
    
    # Derive mood tags from genres
    mood_counter = Counter()
    for genre in top_genres[:7]:  # Top 7 genres
        genre_lower = genre.lower()
        # Try exact match first
        if genre_lower in GENRE_MOOD_MAP:
            for mood in GENRE_MOOD_MAP[genre_lower]:
                mood_counter[mood] += 1
        else:
            # Try partial match
            for key, moods in GENRE_MOOD_MAP.items():
                if key in genre_lower or genre_lower in key:
                    for mood in moods:
                        mood_counter[mood] += 1
                    break
    
    # Calculate average popularity
    avg_popularity = 0
    if top_artists:
        avg_popularity = sum(a.popularity for a in top_artists) / len(top_artists)
    
    # Add popularity-based moods
    if avg_popularity > 70:
        mood_counter["mainstream"] += 2
    elif avg_popularity < 40:
        mood_counter["underground"] += 2
        mood_counter["indie"] += 1
    
    # Get top moods
    mood_tags = [mood for mood, _ in mood_counter.most_common(5)]
    
    # If no moods found, add defaults
    if not mood_tags:
        mood_tags = ["eclectic", "diverse"]
    
    # Generate summary sentence
    summary_sentence = _generate_summary(top_genres, mood_tags, avg_popularity)
    
    # Banned references (artist names to avoid in prompts)
    banned_references = [artist.name for artist in top_artists[:15]]
    
    return TasteProfile(
        top_genres=top_genres,
        mood_tags=mood_tags,
        summary_sentence=summary_sentence,
        banned_references=banned_references
    )


def _generate_summary(
    genres: List[str],
    moods: List[str],
    avg_popularity: float
) -> str:
    """Generate a summary sentence about the user's taste"""
    
    if not genres:
        return "Your music taste is diverse and eclectic, spanning many genres."
    
    # Main genre description
    main_genres = genres[:3]
    genre_text = ", ".join(main_genres[:2])
    if len(main_genres) > 2:
        genre_text += f", and {main_genres[2]}"
    
    # Mood description
    mood_text = ""
    if moods:
        if len(moods) >= 2:
            mood_text = f" with {moods[0]} and {moods[1]} vibes"
        else:
            mood_text = f" with {moods[0]} vibes"
    
    # Popularity description
    popularity_text = ""
    if avg_popularity > 75:
        popularity_text = " You gravitate towards popular hits and chart-toppers."
    elif avg_popularity < 35:
        popularity_text = " You have a taste for underground and lesser-known artists."
    elif avg_popularity < 50:
        popularity_text = " You enjoy a mix of indie and alternative sounds."
    
    return f"Your sound leans heavily into {genre_text}{mood_text}.{popularity_text}".strip()
