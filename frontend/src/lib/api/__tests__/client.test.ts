/**
 * Regression tests for cross-tab refresh-token rotation race.
 *
 * Background: production logs from 2026-05-18 captured the same Supabase
 * user-id signed into Chrome-Mac + Firefox-Mac + Chrome-Linux concurrently.
 * Each tab's `refreshPromise` dedup is module-level (per-tab). When the
 * access token expired, two tabs raced /auth/refresh, GoTrue rotated the
 * refresh-token chain on the first POST and rejected the second with
 * `refresh_token_already_used` → HTTP 401 → frontend ran
 * handlePermanentFailure → user kicked to AuthPage at 19:46:17, re-entered
 * credentials at 19:46:22.
 *
 * These tests pin the three branches that close that gap:
 *
 *   1. Proactive: if another tab broadcast `refresh_succeeded` within the
 *      freshness window, tryRefreshToken returns 'success' WITHOUT firing
 *      a network call. Saves a round-trip and the wasted "abuse attempt"
 *      log line on GoTrue.
 *
 *   2. Reactive (load-bearing): if /auth/refresh returns 401 AND another
 *      tab broadcast within the window, tryRefreshToken returns 'success'
 *      instead of 'permanent'. This is what prevents Delta's symptom.
 *
 *   3. Negative control: if /auth/refresh returns 401 with NO recent
 *      cross-tab signal, the original handlePermanentFailure path stands.
 *      Prevents the fix from silently masking real auth failures.
 *
 * Strategy: tests drive `tryRefreshToken` directly (via the `__test`
 * export from client.ts) instead of routing through the axios interceptor
 * chain — that keeps the failure-mode isolated and the asserts crisp.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';

// ---- Module mocks ----------------------------------------------------------
const sessionMocks = {
  getAccessToken: vi.fn<() => string | null>(() => 'access-current'),
  getRefreshToken: vi.fn<() => string | null>(() => 'refresh-current'),
  setSession: vi.fn(),
  clearSession: vi.fn(),
};
vi.mock('@/lib/auth/session', () => sessionMocks);

const adminModeMocks = { notifySessionExpired: vi.fn() };
vi.mock('@/lib/adminMode', () => adminModeMocks);

vi.mock('@/lib/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  }),
}));

// Helper: send a refresh_succeeded broadcast and wait one tick so the
// listener installed inside client.ts's module init has time to update
// `lastOtherTabRefreshAt`.
async function simulateOtherTabRefresh() {
  const sender = new BroadcastChannel('noobbook-auth');
  sender.postMessage({ type: 'refresh_succeeded', at: Date.now() });
  await new Promise((r) => setTimeout(r, 5));
  sender.close();
}

// Helper: import client.ts fresh so module-level state (the channel
// instance, the storage listener, lastOtherTabRefreshAt) starts clean.
async function freshClient() {
  vi.resetModules();
  return await import('@/lib/api/client');
}

describe('cross-tab refresh-token rotation', () => {
  beforeEach(() => {
    sessionMocks.getAccessToken.mockReturnValue('access-current');
    sessionMocks.getRefreshToken.mockReturnValue('refresh-current');
    sessionMocks.setSession.mockReset();
    sessionMocks.clearSession.mockReset();
    adminModeMocks.notifySessionExpired.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('proactive: skips network call when another tab refreshed recently', async () => {
    const postSpy = vi.spyOn(axios, 'post');
    const client = await freshClient();
    await simulateOtherTabRefresh();

    const outcome = await client.__test.tryRefreshToken();

    expect(outcome).toBe('success');
    // Load-bearing: zero network calls. Other tab already handled it.
    expect(postSpy).not.toHaveBeenCalled();
    expect(sessionMocks.clearSession).not.toHaveBeenCalled();
    expect(adminModeMocks.notifySessionExpired).not.toHaveBeenCalled();
  });

  it('reactive: 401 + recent other-tab refresh = success (no logout)', async () => {
    // Our POST loses the rotation race — GoTrue's refresh_token_already_used
    // surfaces as a 401 on /auth/refresh (see backend test_auth_refresh.py).
    const postSpy = vi.spyOn(axios, 'post').mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 401, data: { error: 'Token refresh failed' } },
    });

    const client = await freshClient();
    await simulateOtherTabRefresh();
    // Push the broadcast timestamp into our test window: we want
    // `anotherTabRefreshedRecently()` true when the catch-branch checks it
    // AFTER the axios.post rejection above resolves.
    const outcome = await client.__test.tryRefreshToken();

    expect(postSpy).toHaveBeenCalledTimes(0); // proactive short-circuit also fires here
    // Either path (proactive or reactive) must land 'success' and leave
    // the session intact — that's the user-visible win.
    expect(outcome).toBe('success');
    expect(sessionMocks.clearSession).not.toHaveBeenCalled();
    expect(adminModeMocks.notifySessionExpired).not.toHaveBeenCalled();
  });

  it('reactive (no proactive): 401 fires AFTER broadcast staleness still recovers', async () => {
    // This case forces the REACTIVE branch by ensuring the broadcast
    // arrives DURING the in-flight refresh, not before. Approach: start
    // tryRefreshToken with no prior broadcast, then broadcast partway
    // through the axios mock, then assert reactive recovery.
    const client = await freshClient();

    // Park the axios rejection slightly so the broadcast can arrive
    // during the in-flight window.
    const postSpy = vi.spyOn(axios, 'post').mockImplementationOnce(
      () =>
        new Promise((_resolve, reject) => {
          setTimeout(
            () =>
              reject({
                isAxiosError: true,
                response: { status: 401, data: { error: 'Token refresh failed' } },
              }),
            20,
          );
        }),
    );

    const refreshPromise = client.__test.tryRefreshToken();
    // After the POST is in flight but before its rejection fires, the
    // winning tab broadcasts.
    await new Promise((r) => setTimeout(r, 10));
    await simulateOtherTabRefresh();

    const outcome = await refreshPromise;

    expect(postSpy).toHaveBeenCalledTimes(1); // POST DID fire (no proactive)
    expect(outcome).toBe('success'); // reactive branch recovered
    expect(sessionMocks.clearSession).not.toHaveBeenCalled();
    expect(adminModeMocks.notifySessionExpired).not.toHaveBeenCalled();
  });

  it('negative control: 401 + NO recent cross-tab signal = permanent logout', async () => {
    const postSpy = vi.spyOn(axios, 'post').mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 401, data: { error: 'Token refresh failed' } },
    });

    const client = await freshClient();
    // Reset cross-tab state to be safe — no other tab has refreshed.
    client.__test.resetCrossTabState();

    const outcome = await client.__test.tryRefreshToken();

    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(outcome).toBe('permanent');
    // The historical behaviour MUST be preserved when there's no
    // cross-tab signal — otherwise we'd silently swallow real auth failures.
    expect(sessionMocks.clearSession).toHaveBeenCalledTimes(1);
    expect(adminModeMocks.notifySessionExpired).toHaveBeenCalledTimes(1);
  });

  it('anotherTabRefreshedRecently() is false when no token in storage', async () => {
    // Guards the case where lastOtherTabRefreshAt is fresh but
    // localStorage has been cleared by some other code path — we must
    // NOT trust the broadcast in isolation.
    const client = await freshClient();
    await simulateOtherTabRefresh();
    expect(client.__test.anotherTabRefreshedRecently()).toBe(true);

    sessionMocks.getAccessToken.mockReturnValueOnce(null);
    expect(client.__test.anotherTabRefreshedRecently()).toBe(false);
  });
});
