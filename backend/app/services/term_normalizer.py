"""
Term normalization utilities for Phase 0.

Provides deterministic normalization of terms (genres, moods, descriptors)
to canonical snake_case format. No fuzzy matching in Phase 0 — that comes
later via explicit alias mappings in Phase 1.
"""

import re
from typing import List, Tuple


def normalize_term(s: str) -> str:
    """
    Normalize a term to lowercase_snake_case format.

    Examples:
        "Classic rock" → "classic_rock"
        "classic-rock" → "classic_rock"
        "Lo-Fi Tape" → "lo_fi_tape"
        "80's Synth Pop!" → "80s_synth_pop"

    Returns empty string if input is empty or normalizes to nothing.
    """
    if not s:
        return ""

    # Lowercase
    normalized = s.lower().strip()

    # Replace common separators with underscores
    normalized = re.sub(r"[\s\-–—]+", "_", normalized)

    # Remove apostrophes in common patterns (80's → 80s)
    normalized = re.sub(r"'s\b", "s", normalized)
    normalized = re.sub(r"'", "", normalized)

    # Remove all non-alphanumeric except underscores
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)

    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


def normalize_artist(artist: str) -> str:
    """
    Normalize an artist name to a canonical key format.

    Similar to normalize_term but more conservative:
    - Preserves some structure for disambiguation
    - Returns empty string if input is empty

    Examples:
        "Rush" → "rush"
        "The Beatles" → "the_beatles"
        "will.i.am" → "william"
    """
    if not artist:
        return ""

    # Lowercase
    normalized = artist.lower().strip()

    # Replace periods with nothing (will.i.am → william)
    normalized = re.sub(r"\.", "", normalized)

    # Replace spaces and hyphens with underscores
    normalized = re.sub(r"[\s\-–—]+", "_", normalized)

    # Remove all non-alphanumeric except underscores
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)

    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

    return normalized


def dedupe_terms(terms: List[str]) -> List[str]:
    """
    Deduplicate a list of terms by their normalized form.

    Preserves order (first occurrence wins).
    Does NOT do fuzzy matching — only exact normalized matches are deduped.

    Args:
        terms: List of already-normalized terms (or raw terms to normalize first)

    Returns:
        Deduplicated list preserving original order
    """
    seen: set = set()
    result: List[str] = []

    for term in terms:
        # Normalize if not already (idempotent)
        normalized = normalize_term(term)
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def normalize_and_dedupe_terms(raw_terms: List[str]) -> List[str]:
    """
    Convenience function: normalize all terms and dedupe.

    Args:
        raw_terms: List of raw term strings

    Returns:
        List of normalized, deduplicated terms
    """
    normalized = [normalize_term(t) for t in raw_terms]
    return dedupe_terms(normalized)


def normalize_artists_with_display(
    artists: List[str],
) -> List[Tuple[str, str]]:
    """
    Normalize artist names while preserving display strings.

    Returns list of (normalized_key, display_name) tuples.
    Deduplicates by normalized key (first occurrence wins).

    Args:
        artists: List of artist display names

    Returns:
        List of (normalized_key, display_name) tuples
    """
    seen: set = set()
    result: List[Tuple[str, str]] = []

    for artist in artists:
        display = artist.strip()
        if not display:
            continue
        normalized = normalize_artist(display)
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append((normalized, display))

    return result


def normalize_tags(tags: List[str]) -> List[str]:
    """
    Normalize user-provided tags to canonical format.

    Same as normalize_and_dedupe_terms but semantically for tags.
    """
    return normalize_and_dedupe_terms(tags)

