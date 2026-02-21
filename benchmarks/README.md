# Benchmarks

This directory stores timestamped results from `/test-quality` and `/test-perf` skill runs. Each file captures a snapshot so we can detect regressions over time.

## File naming

- `perf-YYYY-MM-DD.md` — latency benchmarks
- `quality-YYYY-MM-DD.md` — generation quality assessments

## How to add a result

After running `/test-quality` or `/test-perf`, save the report here with today's date. If multiple runs happen on the same day, append a suffix (e.g., `perf-2026-02-21-b.md`).

## What to track

### Performance (`perf-*.md`)
- `/generate/input-concept` latency (5 calls, min/max/avg)
- `/generate/advanced` latency (3 calls, min/max/avg)
- `/generate/refine` latency (3 calls, min/max/avg)
- Git commit hash or branch name

### Quality (`quality-*.md`)
- Number of songs generated
- Banned word appearances (count and which words)
- Chorus repetition issues (count)
- Empty/bad `concept_title` count
- Missing section tags count
- Stage directions in lyrics count
- Lines ending in periods count
- Git commit hash or branch name
