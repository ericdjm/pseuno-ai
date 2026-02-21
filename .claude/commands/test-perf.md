# Test Performance

Benchmark endpoint latency. Run this when making changes that could affect generation speed.

## Prerequisites

1. Verify dev stack is up: `curl -s localhost:8000/health`
2. If not running, run `make dev-up` and wait for health check to pass.

## Steps

### 1. Benchmark `/generate/input-concept`

Call 5 times and report min/max/avg latency. Target: <2s each.

```bash
for i in 1 2 3 4 5; do
  time curl -s -X POST localhost:8000/generate/input-concept \
    -H "Content-Type: application/json" \
    -d '{"raw_input": "upbeat pop song about summer"}' > /dev/null
done
```

### 2. Benchmark `/generate/advanced`

Call 3 times with different inputs. Target: <15s each.

```bash
curl -s -w "\n%{time_total}s\n" -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "indie rock with jangly guitars", "lyrics_about": "leaving home for the first time"}'

curl -s -w "\n%{time_total}s\n" -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "lo-fi hip hop beats", "lyrics_about": "late night studying"}'

curl -s -w "\n%{time_total}s\n" -X POST localhost:8000/generate/advanced \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "orchestral film score", "lyrics_about": ""}'
```

### 3. Benchmark `/generate/refine`

Call 3 times with `refine_target=lyrics`. Target: <15s each.

Use the full response from step 2 to build the refine request (the endpoint requires the current snapshot, not just a generation_id):
```bash
curl -s -w "\n%{time_total}s\n" -X POST localhost:8000/generate/refine \
  -H "Content-Type: application/json" \
  -d '{
    "suno_prompt": "<suno_prompt from step 2>",
    "lyrics": "<lyrics from step 2>",
    "exclude": "<exclude from step 2>",
    "title": "<concept_title from step 2>",
    "weirdness": <weirdness from step 2>,
    "change_request": "make it more emotional",
    "refine_target": "lyrics"
  }'
```

### 4. Compare (if testing a change)

If benchmarking before/after a code change:
1. Run steps 1-3 on the base branch, save results
2. Switch to feature branch, run again
3. Report the delta for each endpoint

### 5. Save results

Save the report to `benchmarks/perf-YYYY-MM-DD.md` (use today's date). Include the git branch/commit, per-call latencies, and min/max/avg for each endpoint. See `benchmarks/README.md` for the format.
