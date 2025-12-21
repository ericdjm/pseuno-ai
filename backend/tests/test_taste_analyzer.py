"""
Tests for taste analyzer
"""

import pytest
from app.services.taste_analyzer import build_taste_profile
from app.models import SpotifyArtist, SpotifyTrack


def create_mock_artists(count: int = 5) -> list[SpotifyArtist]:
    """Create mock artist data for testing"""
    artists = [
        SpotifyArtist(
            name="Artist One",
            genres=["indie rock", "alternative rock", "rock"],
            popularity=65,
            image_url="https://example.com/1.jpg"
        ),
        SpotifyArtist(
            name="Artist Two",
            genres=["electronic", "synth-pop", "dance"],
            popularity=72,
            image_url="https://example.com/2.jpg"
        ),
        SpotifyArtist(
            name="Artist Three",
            genres=["hip hop", "rap", "trap"],
            popularity=80,
            image_url="https://example.com/3.jpg"
        ),
        SpotifyArtist(
            name="Artist Four",
            genres=["indie rock", "dream pop", "shoegaze"],
            popularity=45,
            image_url="https://example.com/4.jpg"
        ),
        SpotifyArtist(
            name="Artist Five",
            genres=["folk", "singer-songwriter", "acoustic"],
            popularity=55,
            image_url="https://example.com/5.jpg"
        ),
    ]
    return artists[:count]


def create_mock_tracks(count: int = 5) -> list[SpotifyTrack]:
    """Create mock track data for testing"""
    tracks = [
        SpotifyTrack(
            name="Track One",
            artists=["Artist One"],
            album_name="Album One",
            album_image_url="https://example.com/album1.jpg",
            popularity=70
        ),
        SpotifyTrack(
            name="Track Two",
            artists=["Artist Two", "Featured Artist"],
            album_name="Album Two",
            album_image_url="https://example.com/album2.jpg",
            popularity=85
        ),
        SpotifyTrack(
            name="Track Three",
            artists=["Artist Three"],
            album_name="Album Three",
            album_image_url="https://example.com/album3.jpg",
            popularity=90
        ),
        SpotifyTrack(
            name="Track Four",
            artists=["Artist Four"],
            album_name="Album Four",
            album_image_url="https://example.com/album4.jpg",
            popularity=40
        ),
        SpotifyTrack(
            name="Track Five",
            artists=["Artist Five"],
            album_name="Album Five",
            album_image_url="https://example.com/album5.jpg",
            popularity=60
        ),
    ]
    return tracks[:count]


class TestBuildTasteProfile:
    """Tests for build_taste_profile function"""
    
    def test_returns_taste_profile(self):
        """Should return a TasteProfile object"""
        artists = create_mock_artists()
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert profile is not None
        assert hasattr(profile, 'top_genres')
        assert hasattr(profile, 'mood_tags')
        assert hasattr(profile, 'summary_sentence')
        assert hasattr(profile, 'banned_references')
    
    def test_extracts_top_genres(self):
        """Should extract and rank genres from artists"""
        artists = create_mock_artists()
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert len(profile.top_genres) > 0
        # indie rock appears twice, should be highly ranked
        assert "indie rock" in profile.top_genres[:3]
    
    def test_banned_references_contains_artist_names(self):
        """Should include artist names in banned references"""
        artists = create_mock_artists()
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert "Artist One" in profile.banned_references
        assert "Artist Two" in profile.banned_references
    
    def test_generates_summary_sentence(self):
        """Should generate a non-empty summary sentence"""
        artists = create_mock_artists()
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert len(profile.summary_sentence) > 0
        assert "Your" in profile.summary_sentence or "your" in profile.summary_sentence.lower()
    
    def test_derives_mood_tags(self):
        """Should derive mood tags from genres"""
        artists = create_mock_artists()
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert len(profile.mood_tags) > 0
    
    def test_handles_empty_artists(self):
        """Should handle empty artist list gracefully"""
        artists = []
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert profile is not None
        assert len(profile.top_genres) == 0
        # Should still have default moods
        assert len(profile.mood_tags) > 0
    
    def test_handles_empty_tracks(self):
        """Should handle empty track list gracefully"""
        artists = create_mock_artists()
        tracks = []
        
        profile = build_taste_profile(artists, tracks)
        
        assert profile is not None
        assert len(profile.top_genres) > 0
    
    def test_handles_artists_without_genres(self):
        """Should handle artists with no genres"""
        artists = [
            SpotifyArtist(name="No Genre Artist", genres=[], popularity=50)
        ]
        tracks = create_mock_tracks()
        
        profile = build_taste_profile(artists, tracks)
        
        assert profile is not None
        assert len(profile.top_genres) == 0
    
    def test_high_popularity_adds_mainstream_mood(self):
        """Should add mainstream mood tag for high popularity artists"""
        artists = [
            SpotifyArtist(name="Pop Star", genres=["pop"], popularity=95),
            SpotifyArtist(name="Pop Star 2", genres=["pop"], popularity=90),
        ]
        tracks = []
        
        profile = build_taste_profile(artists, tracks)
        
        # High avg popularity should add mainstream tag
        assert "mainstream" in profile.mood_tags or "catchy" in profile.mood_tags
    
    def test_low_popularity_adds_underground_mood(self):
        """Should add underground mood tag for low popularity artists"""
        artists = [
            SpotifyArtist(name="Underground Artist", genres=["experimental"], popularity=20),
            SpotifyArtist(name="Indie Artist", genres=["indie"], popularity=25),
        ]
        tracks = []
        
        profile = build_taste_profile(artists, tracks)
        
        # Low avg popularity should add underground/indie tag
        assert "underground" in profile.mood_tags or "indie" in profile.mood_tags
