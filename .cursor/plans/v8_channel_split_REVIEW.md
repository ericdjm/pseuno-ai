# V8 Channel Split Plan - Review & Improvements

## Executive Summary

The plan is well-structured and addresses a real problem (vocalist leakage). Here are key improvements to consider:

1. **MusicBrainz API Library**: The linked JS/TS library won't work for Python backend
2. **V8 Parsing Robustness**: Need clearer fallback strategy and edge case handling
3. **V9 Database Schema**: Missing cache table design details
4. **Testing Strategy**: Could be more explicit about validation approach
5. **Rate Limiting**: MusicBrainz requires careful rate limiting (1 req/sec)

---

## 1. MusicBrainz API Integration (V9) - Critical Fix

### Issue
The plan links to `https://github.com/Borewit/musicbrainz-api` which is a **JavaScript/TypeScript** library, but your backend is **Python**. This won't work.

### Recommendation

**Option A: Use `python-musicbrainzngs` (Recommended)**
- Mature, well-maintained Python library
- Handles rate limiting, User-Agent requirements
- Clean API for artist lookups
- Install: `pip install musicbrainzngs`

**Option B: Raw `httpx` (as mentioned in plan)**
- More control, but you'll need to implement:
  - Rate limiting (1 req/sec per MusicBrainz policy)
  - User-Agent header (required)
  - XML parsing (MusicBrainz returns XML)
  - Error handling for 503 (rate limit) responses

### Suggested V9 Implementation Details

```python
# backend/app/services/musicbrainz_client.py
import asyncio
import hashlib
from typing import Optional, Dict
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from app.db.models import MusicBrainzCache  # New model

class MusicBrainzClient:
    """Async MusicBrainz API client with caching and rate limiting."""
    
    BASE_URL = "https://musicbrainz.org/ws/2"
    RATE_LIMIT_SECONDS = 1.0  # 1 req/sec per MusicBrainz policy
    USER_AGENT = "PseunoAI/1.0 (https://pseuno.ai)"  # Required
    
    def __init__(self, http_client: httpx.AsyncClient, db: Session):
        self.http_client = http_client
        self.db = db
        self._last_request_time = 0
        self._rate_limit_lock = asyncio.Lock()
    
    async def _rate_limit(self):
        """Enforce 1 req/sec rate limit."""
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self.RATE_LIMIT_SECONDS:
                await asyncio.sleep(self.RATE_LIMIT_SECONDS - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def lookup_artist_vocal_info(
        self, 
        artist_name: str,
        spotify_artist_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Lookup artist vocal characteristics (gender, vocal range).
        Returns dict with keys: 'gender', 'vocal_range', 'vocal_type' (if available).
        """
        # Check cache first
        cache_key = self._make_cache_key(artist_name, spotify_artist_id)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        # Rate limit before request
        await self._rate_limit()
        
        # Search MusicBrainz
        # Implementation here...
        
        # Cache result
        # Save to DB...
        
        return result
```

### Database Schema Addition

```python
# Add to backend/app/db/models.py
class MusicBrainzCache(Base):
    __tablename__ = "musicbrainz_cache"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Cache key components
    artist_name_normalized: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    spotify_artist_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    
    # Cached data (JSON)
    vocal_gender: Mapped[Optional[str]] = mapped_column(String(50))  # male, female, non-binary, unknown
    vocal_range: Mapped[Optional[str]] = mapped_column(String(100))  # tenor, alto, etc.
    vocal_type: Mapped[Optional[str]] = mapped_column(String(100))  # additional descriptors
    
    # Metadata
    musicbrainz_artist_id: Mapped[Optional[str]] = mapped_column(String(36))  # MBID
    cache_hit_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        UniqueConstraint(
            "artist_name_normalized",
            "spotify_artist_id",
            name="uq_mb_cache_artist",
        ),
    )
```

**Migration needed**: Create Alembic migration for `musicbrainz_cache` table.

---

## 2. V8 Parsing Robustness - Improvements

### Current Plan Gaps

The plan mentions "deterministic parsing rules" but doesn't specify:
- What happens when parsing is ambiguous?
- How to handle multiple vocalist references?
- How to normalize artist names before matching?

### Suggested Enhanced Parsing Logic

```python
# In agent_prompt_graph.py
def _parse_vocal_music_split(self, style_request: str, selected_artists: List[str]) -> Dict[str, Any]:
    """
    V8-only: Parse style_request to split vocal reference from music target.
    
    Returns:
        {
            'vocal_reference_artist': Optional[str],
            'music_target_artist': Optional[str],
            'vocal_patterns': List[str],  # Detected patterns for debugging
            'confidence': float  # 0.0-1.0
        }
    """
    patterns = [
        # High confidence patterns
        (r"lead\s+singer\s+of\s+(\w+(?:\s+\w+)*)\s+singing\s+(?:for|over|with)\s+(\w+(?:\s+\w+)*)", "vocal", "music"),
        (r"singer\s+of\s+(\w+(?:\s+\w+)*)\s+for\s+(\w+(?:\s+\w+)*)", "vocal", "music"),
        (r"(\w+(?:\s+\w+)*)\s+vocals\s+(?:with|over|for)\s+(\w+(?:\s+\w+)*)\s+instrumentation", "vocal", "music"),
        
        # Medium confidence
        (r"vocals\s+like\s+(\w+(?:\s+\w+)*)\s+over\s+(\w+(?:\s+\w+)*)", "vocal", "music"),
        (r"(\w+(?:\s+\w+)*)\s+singing\s+for\s+(\w+(?:\s+\w+)*)", "vocal", "music"),
    ]
    
    # Try patterns in order
    for pattern, vocal_group, music_group in patterns:
        match = re.search(pattern, style_request, re.IGNORECASE)
        if match:
            vocal_artist = match.group(1).strip()
            music_artist = match.group(2).strip()
            
            # Validate against selected_artists if provided
            if selected_artists:
                vocal_match = self._fuzzy_match_artist(vocal_artist, selected_artists)
                music_match = self._fuzzy_match_artist(music_artist, selected_artists)
                if vocal_match and music_match:
                    return {
                        'vocal_reference_artist': vocal_match,
                        'music_target_artist': music_match,
                        'vocal_patterns': [pattern],
                        'confidence': 0.9
                    }
    
    # Fallback: no split detected
    return {
        'vocal_reference_artist': None,
        'music_target_artist': None,
        'vocal_patterns': [],
        'confidence': 0.0
    }
```

### Fallback Strategy

When parsing fails (confidence < 0.5):
1. **Log the failure** in debug trace for analysis
2. **Use V6 behavior** (no split, all artists treated equally)
3. **Still run genre disambiguation** but don't route by role

This ensures V8 never breaks existing functionality.

---

## 3. V8 Style Context Formatting - Clarification

### Current Plan Ambiguity

The plan says "route genre disambiguation output by role" but doesn't specify the exact format.

### Suggested Format

```python
def _format_style_context_v8(
    self, 
    context_pack: Dict[str, Any],
    split_result: Dict[str, Any],
    genre_data: Optional[Dict[str, Any]]
) -> str:
    """V8-only: Format style context with explicit MUSIC_TARGET vs VOCAL_REFERENCE blocks."""
    
    lines = [
        "Generate SUNO PROMPT, EXCLUDE, WEIRDNESS, and STYLE INFLUENCE for:",
    ]
    
    # MUSIC_TARGET block (genre/instruments/arrangement)
    if split_result['music_target_artist']:
        lines.append("")
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("MUSIC_TARGET (Genre/Instrumentation/Arrangement Authority)")
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append(f"  Primary artist: {split_result['music_target_artist']}")
        if genre_data and split_result['music_target_artist'] in genre_data.get('artists', {}):
            artist_genre_info = genre_data['artists'][split_result['music_target_artist']]
            lines.append(f"  Genres: {', '.join(artist_genre_info.get('genres', []))}")
            lines.append(f"  Not genres: {', '.join(artist_genre_info.get('not_genres', []))}")
        lines.append("")
        lines.append("CRITICAL: Use this artist's instrumentation, genre, and arrangement style.")
        lines.append("Do NOT borrow vocal characteristics from this artist.")
    
    # VOCAL_REFERENCE block (voice-only)
    if split_result['vocal_reference_artist']:
        lines.append("")
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append("VOCAL_REFERENCE (Voice-Only Guidance)")
        lines.append("═══════════════════════════════════════════════════════════════")
        lines.append(f"  Vocalist artist: {split_result['vocal_reference_artist']}")
        lines.append("")
        lines.append("CRITICAL: Use ONLY this artist's vocal characteristics:")
        lines.append("  - Vocal timbre/tone")
        lines.append("  - Vocal range (tenor/alto/etc)")
        lines.append("  - Delivery style (breathy, aggressive, etc)")
        lines.append("")
        lines.append("DO NOT borrow this artist's:")
        lines.append("  - Genre")
        lines.append("  - Instrumentation")
        lines.append("  - Arrangement style")
        lines.append("  - Production aesthetic")
    
    # Fallback: standard format if no split detected
    if not split_result['vocal_reference_artist'] and not split_result['music_target_artist']:
        lines.append(f"  style_request: {context_pack.get('user_style_request', '')}")
        lines.append(f"  reference_artists: {context_pack.get('selected_artists', [])}")
    
    lines.append(f"  tags: {context_pack.get('tags', [])}")
    
    return "\n".join(lines)
```

---

## 4. MAX Mode Removal - Testing Considerations

### Current Plan
Remove MAX headers for V5/V6/V7/V8. Good, but add:

### Additional Considerations

1. **Update validation logic**: Remove the check at line 1243 in `agent_prompt_graph.py` that complains about "MAX headers but missing structured format" - this will be obsolete.

2. **Update prompt specs**: Change `SUNO_PROMPT_SPEC_V5` to reflect 500-char limit (not 400).

3. **Backward compatibility**: Consider if any saved prompts rely on MAX headers. Probably fine since they're prepended automatically.

4. **Testing checklist**:
   - [ ] V5 generation: verify 500 chars available (not 400)
   - [ ] V6 generation: verify no MAX headers prepended
   - [ ] V7 generation: verify no MAX headers prepended
   - [ ] Check debug trace shows correct prompt lengths

---

## 5. V9 Integration Points - Missing Details

### When to Call MusicBrainz

The plan says "best-effort grounding call for vocalist identity/gender" but doesn't specify:

**Suggested Flow**:
1. **V8 parsing detects** `vocal_reference_artist`
2. **V9 enhancement**: Before style generation, call MusicBrainz
3. **Cache result** in DB (keyed by normalized artist name + optional Spotify ID)
4. **Inject into style context**: Add vocal gender/range to VOCAL_REFERENCE block
5. **Fallback**: If MusicBrainz fails/timeouts, proceed without it (don't block generation)

### Error Handling

```python
# In agent_prompt_graph.py, style branch
if ctx.variant_id == "v9_musicbrainz_grounded":
    vocal_artist = split_result.get('vocal_reference_artist')
    if vocal_artist:
        try:
            mb_info = await musicbrainz_client.lookup_artist_vocal_info(
                artist_name=vocal_artist,
                spotify_artist_id=self._find_spotify_id(vocal_artist, context_pack)
            )
            if mb_info:
                # Enhance VOCAL_REFERENCE block with MB data
                style_context = self._enhance_vocal_reference_with_mb(
                    style_context, mb_info
                )
        except Exception as e:
            logger.warning(f"MusicBrainz lookup failed for {vocal_artist}: {e}")
            # Continue without MB data - don't block generation
```

---

## 6. Testing Strategy - Enhancements

### Suggested Test Cases

Add to plan:

```python
# Test cases for V8 parsing
test_cases = [
    {
        "input": "Lead singer of Steel Panther singing for TOOL",
        "expected": {
            "vocal_reference_artist": "Steel Panther",
            "music_target_artist": "TOOL",
            "confidence": 0.9
        }
    },
    {
        "input": "Flipturn vocals with Richy Mitch & The Coal Miners instrumentation",
        "expected": {
            "vocal_reference_artist": "Flipturn",
            "music_target_artist": "Richy Mitch & The Coal Miners",
            "confidence": 0.9
        }
    },
    {
        "input": "Taylor Swift style",  # No split pattern
        "expected": {
            "vocal_reference_artist": None,
            "music_target_artist": None,
            "confidence": 0.0
        }
    },
]
```

### Validation Approach

1. **Manual testing**: Use debug trace artifacts to verify:
   - Style context shows two blocks (MUSIC_TARGET, VOCAL_REFERENCE)
   - Final SUNO prompt doesn't leak instrumentation from vocalist
   
2. **Automated tests**: Add pytest tests for `_parse_vocal_music_split()` function

---

## 7. Implementation Order - Refinement

### Suggested Sequence

1. ✅ **Step 0**: Remove MAX mode (isolated, testable change)
2. ✅ **Step 1**: Create V8 variant file (V6-based)
3. ✅ **Step 2**: Implement parsing logic (unit testable)
4. ✅ **Step 3**: Implement V8 style context formatter
5. ✅ **Step 4**: Update schemas (backend + frontend)
6. ✅ **Step 5**: Manual validation with debug traces
7. ⏭️ **Step 6**: V9 - Add MusicBrainz client + cache table
8. ⏭️ **Step 7**: V9 - Integrate MB lookup into style branch
9. ⏭️ **Step 8**: V9 - Testing + validation

**Key insight**: V8 and V9 can be separate PRs. V8 doesn't require MusicBrainz.

---

## 8. Constants Updates - Missing

### Add to `constants.py`

```python
# V8 Channel Split
V8_PARSING_CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence to apply split

# V9 MusicBrainz
MUSICBRAINZ_RATE_LIMIT_SECONDS = 1.0
MUSICBRAINZ_CACHE_TTL_DAYS = 30  # How long to cache MB lookups
```

---

## 9. Documentation - Missing

### Add to Plan

- **API Documentation**: Document new V8 variant in `/generate/prompt-variants` response
- **User-facing**: Consider adding tooltip/help text explaining V8's "channel split" feature
- **Debug Trace**: Ensure V8 parsing results appear in debug trace artifacts for analysis

---

## Summary of Critical Changes Needed

1. ✅ **Fix MusicBrainz library reference** (use `python-musicbrainzngs` or raw `httpx`)
2. ✅ **Add database schema** for MusicBrainz cache table
3. ✅ **Clarify V8 parsing fallback** strategy
4. ✅ **Specify V8 style context format** more explicitly
5. ✅ **Add test cases** for parsing logic
6. ✅ **Clarify V9 integration points** (when/how to call MB)
7. ✅ **Update constants** with V8/V9 thresholds

---

## Questions to Resolve

1. **MusicBrainz User-Agent**: What should the User-Agent string be? (Required by MB policy)
2. **Cache invalidation**: How long should we cache MB lookups? (30 days? Forever?)
3. **V8 rollout**: Should V8 be the new default, or opt-in only?
4. **V9 rollout**: Should V9 require explicit opt-in, or be automatic for V8+?

