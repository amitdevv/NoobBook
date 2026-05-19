/**
 * API Client Configuration
 * Educational Note: We create an axios instance with base configuration
 * to avoid repeating the base URL and headers in every request.
 * This is the single source of truth for API communication.
 */

import axios, { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { getAccessToken, getRefreshToken, setSession, clearSession } from '../auth/session';
import { notifySessionExpired } from '@/lib/adminMode';
import { createLogger } from '@/lib/logger';

const log = createLogger('api-client');

// Base host URL (without /api/v1 path) - used for file URLs, static assets.
// When VITE_API_HOST is set to "" (Docker via nginx proxy), same-origin requests
// are used. When unset (local dev), falls back to localhost:5001.
const envHost = import.meta.env.VITE_API_HOST;
export const API_HOST = envHost !== undefined ? envHost : 'http://localhost:5001';

// Full API URL (with /api/v1 path) - used for API requests
const envApiUrl = import.meta.env.VITE_API_URL;
const API_BASE_URL = envApiUrl !== undefined ? envApiUrl : `${API_HOST}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Per-request correlation ID. The backend stamps every log record with this
// (see app/utils/logger.py:_RequestIdFilter), and echoes it back in the
// X-Request-Id response header. When the user reports "I was logged out at
// 14:32", the req_id printed alongside any failed-request log in DevTools
// is the single grep key the support engineer needs in backend.log.
function _newRequestId(): string {
  // crypto.randomUUID is available in all browsers we ship to; the fallback
  // covers older WebView environments (e.g. embedded Slack browser) so we
  // never throw at request time.
  try {
    return (globalThis.crypto?.randomUUID?.() || '').replace(/-/g, '').slice(0, 16)
      || Math.random().toString(36).slice(2, 18);
  } catch {
    return Math.random().toString(36).slice(2, 18);
  }
}

const attachAuthHeader = (config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Attach a fresh req_id per request so every retry / refresh gets its own.
  // If a caller has already set one (e.g. a tracing wrapper) we honour it.
  config.headers = config.headers || {};
  if (!config.headers['X-Request-Id']) {
    config.headers['X-Request-Id'] = _newRequestId();
  }
  return config;
};

// Attach auth header to all requests
api.interceptors.request.use(
  (config) => {
    return attachAuthHeader(config);
  },
  (error) => {
    log.error({ err: error }, 'request interceptor error');
    return Promise.reject(error);
  }
);

// Ensure global axios requests (non-api instance) include auth header too
axios.interceptors.request.use(attachAuthHeader);

// ---------- Auto-refresh on 401 ----------
// When the access token expires, API calls return 401. We intercept the 401,
// use the stored refresh_token to get a new token pair, then transparently
// retry the original request. A shared `refreshPromise` ensures concurrent
// 401s trigger only one refresh call.
//
// Failure modes are NOT all equivalent:
//   - permanent: refresh token is genuinely invalid (401/403 from /auth/refresh
//     or 200-with-malformed-body) → clear session, surface a toast, send the
//     user back to the auth page.
//   - transient: network blip, GoTrue restart, 5xx, browser-offline → keep
//     the session intact and let the next API call try again. Logging the
//     user out for a 30-second connectivity hiccup was the original cause
//     of the "frequent logouts" reports.

type RefreshOutcome = 'success' | 'transient' | 'permanent';

let refreshPromise: Promise<RefreshOutcome> | null = null;

// ---------- Cross-tab refresh coordination ----------
// The `refreshPromise` above dedups concurrent refreshes WITHIN a single tab.
// When the same user is signed into NoobBook from multiple tabs / browsers
// (production logs from 2026-05-18 captured Chrome-Mac + Firefox-Mac +
// Chrome-Linux on the same Supabase user-id), each tab's `refreshPromise`
// is independent. They race each other on the same refresh-token chain,
// GoTrue rotates on whichever POST arrives first, and the loser gets
// `refresh_token_already_used` → HTTP 401. Without cross-tab coordination
// the loser then runs handlePermanentFailure → user kicked to login.
//
// Coordination strategy:
//   - PROACTIVE: before firing /auth/refresh, check whether another tab
//     just refreshed within `CROSS_TAB_FRESHNESS_MS`. If yes, skip the
//     POST entirely — localStorage already has fresh tokens.
//   - REACTIVE (load-bearing): if our /auth/refresh returns 401/403, check
//     the same window. If yes, the 401 is a rotation-race loss, not a
//     real auth failure — return 'success' (the winning tab's tokens are
//     in localStorage) instead of 'permanent' (logout).
//
// Transport: BroadcastChannel('noobbook-auth') primary, `storage` event
// fallback (Safari < 15.4 lacks BroadcastChannel). Both update the same
// module-level timestamp.

type AuthBroadcastMessage = { type: 'refresh_succeeded'; at: number };

const AUTH_BROADCAST_CHANNEL = 'noobbook-auth';
// Picked so the window covers: typical /auth/refresh round-trips are
// 120–150 ms in production; we want comfortable margin for slow
// connections without trusting hour-old refreshes from hibernated tabs.
const CROSS_TAB_FRESHNESS_MS = 2_000;

let lastOtherTabRefreshAt = 0;

const authChannel: BroadcastChannel | null =
  typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel(AUTH_BROADCAST_CHANNEL)
    : null;

if (authChannel) {
  authChannel.addEventListener('message', (ev) => {
    const msg = ev.data as AuthBroadcastMessage | undefined;
    if (msg?.type === 'refresh_succeeded') {
      lastOtherTabRefreshAt = msg.at;
    }
  });
}

// Storage-event fallback. Browsers fire `storage` on every tab EXCEPT the
// one that performed the setItem — exactly the cross-tab notification
// semantics we want, and the path Safari < 15.4 takes since it lacks
// BroadcastChannel.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (ev) => {
    if (ev.key === 'noobbook.access_token' && ev.newValue) {
      lastOtherTabRefreshAt = Date.now();
    }
  });
}

function broadcastRefreshSucceeded(): void {
  if (!authChannel) return;
  authChannel.postMessage({
    type: 'refresh_succeeded',
    at: Date.now(),
  } satisfies AuthBroadcastMessage);
}

function anotherTabRefreshedRecently(): boolean {
  return (
    Date.now() - lastOtherTabRefreshAt < CROSS_TAB_FRESHNESS_MS &&
    !!getAccessToken()
  );
}

async function tryRefreshToken(): Promise<RefreshOutcome> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    // No refresh token = permanent. Fire the side effects here too so
    // first-load callers get the same behavior as mid-session expiry.
    handlePermanentFailure();
    return 'permanent';
  }

  // Proactive cross-tab dedup. Another tab broadcast a successful refresh
  // within the last CROSS_TAB_FRESHNESS_MS — trust it and skip the
  // network call entirely. localStorage already has the new tokens.
  if (anotherTabRefreshedRecently()) {
    log.info('refresh: skipping POST — another tab refreshed recently');
    return 'success';
  }

  try {
    const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    if (data?.success && data.session?.access_token) {
      setSession(data.session.access_token, data.session.refresh_token);
      broadcastRefreshSucceeded();
      return 'success';
    }
    // 200 OK but no usable session in the body — treat as permanent. The
    // server told us refresh "worked" but didn't hand back a token, and
    // retrying will produce the same shape.
    log.error({ data }, 'refresh returned malformed body');
    handlePermanentFailure();
    return 'permanent';
  } catch (err) {
    const status = (err as AxiosError).response?.status;
    if (status === 401 || status === 403) {
      // Reactive cross-tab dedup — the load-bearing fix.
      // GoTrue's rotation is "first POST wins". If our POST lost to
      // another tab, the response is 401 with error_code
      // refresh_token_already_used. But the winning tab has already
      // written fresh tokens to localStorage, so we are NOT actually
      // de-authenticated — adopt their tokens instead of bouncing the
      // user to the login screen.
      if (anotherTabRefreshedRecently()) {
        log.warn(
          { status },
          'refresh: lost rotation race against another tab — using their tokens',
        );
        return 'success';
      }
      log.warn({ status }, 'refresh token rejected — session expired');
      handlePermanentFailure();
      return 'permanent';
    }
    // Network error, timeout, 5xx, 408, 502, 504 — keep session intact.
    log.warn({ err, status }, 'transient refresh failure — keeping session');
    return 'transient';
  }
}

/**
 * Fire session-cleanup side-effects exactly once per refresh-failure
 * window. Lives inside `tryRefreshToken` so concurrent 401s sharing the
 * same `refreshPromise` only emit one `noobbook:session-expired` event
 * and one `clearSession()` call between them — without this, 5 parallel
 * requests against an expired refresh token would surface 5 duplicate
 * "session expired" toasts and trigger 5 simultaneous `refreshAuth()`
 * calls.
 */
function handlePermanentFailure(): void {
  clearSession();
  notifySessionExpired();
}

// Shared 401 error handler used by both the `api` instance and global `axios` interceptors.
// Educational Note: axios.create() instances have separate interceptor chains, so registering
// on both the `api` instance AND the global `axios` default won't double-fire for `api` requests.
// The shared `refreshPromise` correctly deduplicates concurrent refresh attempts across both.
async function handle401Error(error: AxiosError, retryWith: typeof api | typeof axios): Promise<unknown> {
  const status = error.response?.status;
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retried?: boolean };

  // Skip refresh for auth routes (avoid infinite loop) and already-retried requests
  const isAuthRoute = originalRequest?.url?.includes('/auth/');
  if (status === 401 && originalRequest && !originalRequest._retried && !isAuthRoute) {
    // Deduplicate concurrent refresh attempts
    if (!refreshPromise) {
      refreshPromise = tryRefreshToken().finally(() => { refreshPromise = null; });
    }

    const outcome = await refreshPromise;
    if (outcome === 'success') {
      originalRequest._retried = true;
      // Update the header with the fresh token and retry
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers.Authorization = `Bearer ${getAccessToken()}`;
      return retryWith(originalRequest);
    }
    // outcome === 'permanent' — session-cleanup side effects already
    // fired inside `tryRefreshToken` exactly once for this dedup window.
    // The auth gate in App.tsx routes to AuthPage on next render.
    //
    // outcome === 'transient' — keep the session, let the original
    // request reject with its own error so the caller's UI shows the
    // normal API-error toast (not a "you're logged out" experience).
  }

  // req_id from the response header (or the request header if the server
  // never replied). With this on the error line, a support engineer can grep
  // it directly in backend.log via the admin Logs viewer.
  const reqId =
    (error.response?.headers as Record<string, string> | undefined)?.['x-request-id']
    || (originalRequest?.headers?.['X-Request-Id'] as string | undefined)
    || '-';
  log.error({ status, reqId, data: error.response?.data }, 'API response error');
  return Promise.reject(error);
}

// Response interceptor: auto-refresh expired tokens, log other errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => handle401Error(error, api)
);

// Also cover the 22+ files that use the global `axios` instance directly
// (studio APIs, chats, sources, settings, etc.)
axios.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => handle401Error(error, axios)
);

/**
 * Build an authenticated URL for browser elements that can't send Authorization headers.
 *
 * Educational Note: Elements like <img>, <video>, <audio>, and <iframe> make their own
 * HTTP requests without axios interceptors. We append the JWT as a query parameter
 * so the backend auth middleware can validate it. The backend checks ?token= as a
 * fallback when no Authorization header is present.
 *
 * @param url - Absolute URL or path starting with /api/. If it's a full URL (starts with http),
 *              the token is appended directly. If it's a path, API_HOST is prepended first.
 */
export function getAuthUrl(url: string): string {
  const token = getAccessToken();
  const fullUrl = url.startsWith('http') ? url : `${API_HOST}${url}`;
  if (!token) return fullUrl;
  const separator = fullUrl.includes('?') ? '&' : '?';
  return `${fullUrl}${separator}token=${token}`;
}

export { API_BASE_URL };


/**
 * Pull a user-facing message out of an API error, preferring the server's
 * `error` / `message` field when present. Falls back to the given default.
 *
 * Use this at toast call-sites that currently look like
 *     errorWithLogs('Failed to send message')
 * — replace with
 *     errorWithLogs(extractServerError(err, 'Failed to send message'))
 * so the user sees the actual reason ("Database unreachable — check the
 * connection URI", "Claude rate limit reached", etc.) when the backend
 * supplies one.
 */
// Test-only exports. Bundlers tree-shake unused exports in production
// builds, so leaving this unguarded keeps the test surface stable across
// dev/test/prod without conditional logic. Only consumed by
// `src/lib/api/__tests__/client.test.ts`.
export const __test = {
  tryRefreshToken,
  anotherTabRefreshedRecently,
  resetCrossTabState: () => {
    lastOtherTabRefreshAt = 0;
  },
};


export function extractServerError(err: unknown, fallback: string): string {
  if (!err) return fallback;
  // Axios shape
  const axiosErr = err as AxiosError<{ error?: string; message?: string }>;
  const fromAxios = axiosErr.response?.data?.error || axiosErr.response?.data?.message;
  if (typeof fromAxios === 'string' && fromAxios.trim()) return fromAxios.trim();
  // Fetch / generic Error shape
  if (err instanceof Error && err.message && err.message !== 'Network Error') return err.message;
  return fallback;
}
