import { expect, type Page, type Route } from '@playwright/test';
import zlib from 'node:zlib';

export type CapturedPostHogEvent = {
  event: string;
  properties?: Record<string, unknown>;
  distinct_id?: string;
};

function base64ToBuffer(b64: string): Buffer {
  // Support URL-safe base64 variants
  const normalized = b64.replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(normalized, 'base64');
}

function tryParseJson<T>(s: string): T | null {
  try {
    return JSON.parse(s) as T;
  } catch {
    return null;
  }
}

function decodePostHogBatchFromEEndpoint(postData: string | null, url: string): CapturedPostHogEvent[] {
  // posthog-js can send batch data either in POST body or as a query param.

  // posthog-js typically POSTs to /i/v0/e/ with JSON body like:
  // {"data":"<base64-gzipped-json>","compression":"gzip-js"} (or sometimes form-encoded)
  let dataB64: string | null = null;

  if (postData) {
    if (postData.trim().startsWith('{')) {
      const parsed = tryParseJson<{ data?: string }>(postData);
      dataB64 = parsed?.data ?? null;
    } else {
      const params = new URLSearchParams(postData);
      dataB64 = params.get('data');
    }
  }

  if (!dataB64) {
    try {
      const u = new URL(url);
      dataB64 = u.searchParams.get('data');
    } catch {
      // ignore
    }
  }

  if (!dataB64) return [];

  let payload: unknown = null;
  // The "gzip-js" output is standard gzip bytes; Node can gunzip it.
  try {
    const unzipped = zlib.gunzipSync(base64ToBuffer(dataB64)).toString('utf8');
    payload = tryParseJson<unknown>(unzipped);
  } catch {
    // Sometimes it's plain JSON (urlencoded) or uncompressed.
    try {
      payload = tryParseJson<unknown>(decodeURIComponent(dataB64));
    } catch {
      payload = tryParseJson<unknown>(dataB64);
    }
  }

  // Payload shapes vary; the common case is an array of event objects.
  if (Array.isArray(payload)) {
    return payload.filter((x): x is CapturedPostHogEvent => typeof x === 'object' && x !== null && 'event' in x);
  }

  // Some versions wrap in { batch: [...] }
  if (payload && typeof payload === 'object' && 'batch' in payload) {
    const batch = (payload as any).batch;
    if (Array.isArray(batch)) {
      return batch.filter((x): x is CapturedPostHogEvent => typeof x === 'object' && x !== null && 'event' in x);
    }
  }

  return [];
}

export async function installPostHogCaptureCollector(page: Page) {
  const captured: CapturedPostHogEvent[] = [];
  const posthogRequestUrls: string[] = [];
  const posthogRequestSamples: Array<{ url: string; postData: string | null }> = [];

  // posthog-js prefers navigator.sendBeacon when available, which is harder to
  // intercept consistently. Force XHR/fetch transport so `page.route` can see it.
  await page.addInitScript(() => {
    try {
      // @ts-expect-error - overriding for test only
      Object.defineProperty(navigator, 'sendBeacon', { value: undefined });
    } catch {
      // ignore
    }
  });

  // Capture events at the source by wrapping `window.posthog.capture` (we expose
  // it in dev via frontend/src/main.tsx). This avoids depending on transport.
  await page.addInitScript(() => {
    const w = window as any;
    w.__pw_ph_captured = w.__pw_ph_captured || [];

    // Install a setter so when the app assigns window.posthog, we can wrap capture.
    try {
      Object.defineProperty(w, 'posthog', {
        configurable: true,
        get() {
          return w.__pw_ph_posthog;
        },
        set(ph) {
          w.__pw_ph_posthog = ph;
          if (!ph || typeof ph.capture !== 'function' || ph.__pw_wrapped) return;
          ph.__pw_wrapped = true;
          const orig = ph.capture.bind(ph);
          ph.capture = (eventName: string, props?: Record<string, unknown>) => {
            w.__pw_ph_captured.push({ event: eventName, properties: props || {} });
            return orig(eventName, props);
          };
        },
      });
    } catch {
      // ignore
    }
  });

  // Intercept PostHog ingestion endpoints and decode events.
  await page.route('**/*posthog.com/**', async (route: Route) => {
    const req = route.request();
    const url = req.url();
    posthogRequestUrls.push(url);
    if (posthogRequestSamples.length < 5) {
      posthogRequestSamples.push({ url, postData: req.postData() });
    }

    if (url.includes('/i/v0/e') || url.includes('/e')) {
      const events = decodePostHogBatchFromEEndpoint(req.postData(), url);
      captured.push(...events);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'Ok' }),
      });
      return;
    }

    if (url.includes('/capture')) {
      const body = req.postData();
      const parsed = body ? tryParseJson<CapturedPostHogEvent & { properties?: any }>(body) : null;
      if (parsed?.event) captured.push(parsed);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'Ok' }),
      });
      return;
    }

    // Let SDK config/assets/flags load normally.
    await route.continue();
  });

  // Avoid extra noise from identify/engage requests.
  await page.route('**/i/v0/engage/**', async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  function findEvents(name: string) {
    return captured.filter((e) => e.event === name);
  }

  async function expectEvent(
    name: string,
    predicate?: (e: CapturedPostHogEvent) => boolean
  ) {
    await expect
      .poll(
        async () => {
          // Pull in-browser captured events (source-of-truth for E2E)
          const inBrowser: CapturedPostHogEvent[] = await page.evaluate(() => {
            const w = window as any;
            return Array.isArray(w.__pw_ph_captured) ? w.__pw_ph_captured : [];
          });
          // Keep local mirror for debugging
          captured.splice(0, captured.length, ...inBrowser);

          const evs = findEvents(name);
          if (!predicate) return evs.length;
          return evs.some(predicate) ? 1 : 0;
        },
        { message: `Expected PostHog event ${name} to be captured`, timeout: 30_000 }
      )
      .toBeGreaterThan(0);
  }

  return {
    captured,
    posthogRequestUrls,
    posthogRequestSamples,
    expectEvent,
    findEvents,
  };
}

