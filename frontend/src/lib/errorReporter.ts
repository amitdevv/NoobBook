/**
 * Browser-error reporter.
 *
 * Hooks `window.onerror` and `window.onunhandledrejection` and forwards
 * reports to the backend's `/logs/client` endpoint, where they're written
 * into the same rotating log file as backend errors. Admins can then
 * download the support bundle and see client + server events
 * interleaved.
 *
 * Design notes:
 *   - Throttled to one POST per second so a runaway-error loop can't
 *     pummel the backend.
 *   - Drops if the buffer hits 50 pending — we'd rather lose later
 *     events than block the page.
 *   - All POST failures are swallowed; reporting an error must never
 *     itself throw.
 *   - Idempotent install — calling install() twice doesn't double-hook.
 */
import { logsAPI, type ClientErrorPayload } from './api/logs';

const MAX_BUFFER = 50;
const POST_INTERVAL_MS = 1000;

let installed = false;
const buffer: ClientErrorPayload[] = [];
let flushScheduled = false;

function scheduleFlush() {
  if (flushScheduled) return;
  flushScheduled = true;
  setTimeout(async () => {
    flushScheduled = false;
    while (buffer.length > 0) {
      const next = buffer.shift()!;
      await logsAPI.reportClientError(next);
      if (buffer.length > 0) {
        await new Promise((r) => setTimeout(r, POST_INTERVAL_MS));
      }
    }
  }, 0);
}

function enqueue(payload: ClientErrorPayload) {
  if (buffer.length >= MAX_BUFFER) return;
  buffer.push({
    ...payload,
    url: payload.url ?? window.location.href,
    userAgent: payload.userAgent ?? navigator.userAgent,
    timestamp: payload.timestamp ?? new Date().toISOString(),
  });
  scheduleFlush();
}

function handleError(event: ErrorEvent) {
  enqueue({
    message: event.message || 'window.onerror with empty message',
    stack: event.error?.stack ?? `at ${event.filename}:${event.lineno}:${event.colno}`,
  });
}

function extractRequestId(reason: unknown): string | undefined {
  // AxiosError shape — the request-id middleware echoes our X-Request-Id
  // back as a response header. With this in the rejection report, an admin
  // can grep the same req_id in backend.log via the Logs viewer and find
  // the matching server-side trace line.
  const r = reason as
    | { response?: { headers?: Record<string, string> }; config?: { headers?: Record<string, string> } }
    | undefined;
  const fromResponse = r?.response?.headers?.['x-request-id'];
  if (typeof fromResponse === 'string' && fromResponse) return fromResponse;
  const fromRequest = r?.config?.headers?.['X-Request-Id'];
  if (typeof fromRequest === 'string' && fromRequest) return fromRequest;
  return undefined;
}

function handleRejection(event: PromiseRejectionEvent) {
  const reason = event.reason;
  let message = 'unhandledrejection';
  let stack: string | undefined;
  if (reason instanceof Error) {
    message = reason.message || message;
    stack = reason.stack;
  } else if (typeof reason === 'string') {
    message = reason;
  } else {
    try {
      message = JSON.stringify(reason);
    } catch {
      // leave default
    }
  }
  const reqId = extractRequestId(reason);
  if (reqId) {
    // Tag the message body so the backend log line carries it through
    // /logs/client without needing a payload-schema change.
    message = `[req:${reqId}] ${message}`;
  }
  enqueue({ message, stack });
}

export const errorReporter = {
  install() {
    if (installed) return;
    installed = true;
    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleRejection);
  },

  /** Manual report path — use from React error boundaries or anywhere
   * the global handlers can't see (e.g. caught-then-handled errors that
   * are still worth telemetry). */
  report(message: string, error?: unknown) {
    enqueue({
      message,
      stack: error instanceof Error ? error.stack : undefined,
    });
  },
};
