import { test, expect } from '@playwright/test';
import { installPostHogCaptureCollector } from './posthog_helpers';

function json(body: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

test('New song flow emits key PostHog events (randomize + generate)', async ({ page }) => {
  const ph = await installPostHogCaptureCollector(page);

  // ---- Backend API stubs (make test deterministic; no real LLM calls) ----
  await page.route('**/auth/status', async (route) => {
    await route.fulfill(json({ authenticated: false }));
  });

  await page.route('**/generate/prompt-variants', async (route) => {
    await route.fulfill(
      json({
        variants: [
          {
            id: 'v8_channel_split',
            description: 'Test',
            is_default: true,
            prompt_length: 100,
            prompt_lengths: [100],
            prompt_lengths_breakdown: { style: 50, lyrics: 50 },
          },
        ],
      })
    );
  });

  await page.route('**/generate/models', async (route) => {
    await route.fulfill(
      json({
        models: [
          {
            id: 'gpt-4o-mini',
            name: 'GPT-4o mini',
            provider: 'openai',
            is_default: true,
            is_style_default: true,
            is_lyrics_default: true,
          },
        ],
        default_model: 'gpt-4o-mini',
        default_style_model: 'gpt-4o-mini',
        default_lyrics_model: 'gpt-4o-mini',
      })
    );
  });

  await page.route('**/generate/input-concept', async (route) => {
    await route.fulfill(
      json({
        concept: 'A shimmering synthwave anthem with neon-drenched energy.',
        chosen_genres: ['synthwave'],
        genres: ['synthwave'],
        artists: [],
        mood: 'uplifting',
      })
    );
  });

  await page.route('**/generate/lyrics-topic', async (route) => {
    await route.fulfill(
      json({
        topic: 'Escaping a cyberpunk city at midnight.',
        chosen_moods: ['mysterious'],
        reasoning: null,
      })
    );
  });

  const promptId = 999;
  const threadId = 555;

  await page.route('**/generate/advanced', async (route) => {
    await route.fulfill(
      json({
        generation_id: 'gen_test_1',
        concept_title: 'Neon Run',
        suno_prompt: 'Synthwave, arpeggiated bass, neon nights.',
        lyrics: 'Test lyrics',
        exclude: '',
        weirdness: 0.2,
        style_influence: 0.7,
        prompt_id: promptId,
        is_favorite: false,
        auto_tags: ['synthwave'],
      })
    );
  });

  // App post-generate followups
  await page.route(`**/prompts/${promptId}`, async (route) => {
    await route.fulfill(
      json({
        id: promptId,
        suno_prompt: 'Synthwave, arpeggiated bass, neon nights.',
        lyrics: 'Test lyrics',
        exclude: '',
        weirdness: 0.2,
        style_influence: 0.7,
        title: 'Neon Style',
        notes: null,
        is_favorite: false,
        auto_tags: ['synthwave'],
        generation_id: 'gen_test_1',
        visibility: 'private',
        share_id: 'share_test',
        parent_prompt_id: null,
        source_action: 'generate',
        threads_count: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    );
  });

  await page.route(`**/prompts/${promptId}/threads`, async (route) => {
    await route.fulfill(
      json([
        {
          id: threadId,
          title: 'Neon Run',
          source_action: 'generate',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ])
    );
  });

  await page.route(`**/lyrics-threads/${threadId}`, async (route) => {
    await route.fulfill(
      json({
        id: threadId,
        style_prompt_id: promptId,
        parent_thread_id: null,
        title: 'Neon Run',
        lyrics_text: 'Test lyrics',
        source_action: 'generate',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
    );
  });

  // Library list (avoid extra noise)
  await page.route('**/prompts?**', async (route) => {
    await route.fulfill(json({ prompts: [], total: 0 }));
  });

  // ---- UI flow ----
  await page.goto('/');

  // Expand Style + click dice
  await page.getByText('Style').first().click();
  await page.getByLabel('Surprise me').first().click();

  // Give React/state a moment to settle
  await page.waitForTimeout(300);

  // Sanity: PostHog should have attempted to send *something* over the wire.
  expect(ph.posthogRequestUrls.length).toBeGreaterThan(0);
  // Helpful debug if decoding fails in CI/local runs:
  // eslint-disable-next-line no-console
  console.log('[posthog] urls sample', ph.posthogRequestUrls.slice(0, 3));
  // eslint-disable-next-line no-console
  console.log('[posthog] captured events so far', Array.from(new Set(ph.captured.map((e) => e.event))).slice(0, 20));
  // eslint-disable-next-line no-console
  console.log('[posthog] request samples', ph.posthogRequestSamples.map((s) => ({ url: s.url, postDataPrefix: (s.postData || '').slice(0, 120) })));

  await ph.expectEvent('randomize_style_clicked');
  await ph.expectEvent('randomize_style_succeeded', (e) => typeof e.properties?.duration_ms === 'number');

  // Expand Lyrics + click dice (same aria-label; use nth)
  await page.getByText('Lyrics').first().click();
  await page.getByLabel('Surprise me').nth(1).click();

  await ph.expectEvent('randomize_lyrics_clicked');
  await ph.expectEvent('randomize_lyrics_succeeded', (e) => typeof e.properties?.duration_ms === 'number');

  // Generate (primary CTA is labeled "Create" in the UI)
  await page.getByRole('button', { name: 'Create' }).click();

  await ph.expectEvent('generate_clicked', (e) => typeof e.properties?.has_lyrics_input === 'boolean');
  await ph.expectEvent('generate_succeeded', (e) => typeof e.properties?.duration_ms === 'number');

  // App should track AI-set titles when loading generated prompt/thread
  await ph.expectEvent('style_title_changed', (e) => e.properties?.source === 'ai_generate');
  await ph.expectEvent('song_title_changed', (e) => e.properties?.source === 'ai_generate');

  // Sanity: we should not be posting real events to PostHog in tests (everything is mocked)
  expect(ph.captured.length).toBeGreaterThan(0);
});

