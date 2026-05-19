/**
 * useLogsState — shared state + handlers for the diagnostic-logs viewer.
 *
 * Powers both `LogsModal` (chat-header dialog) and `LogsSection`
 * (settings tab). Centralizes the fetch lifecycle, level filter,
 * clipboard copy, bundle download, and clear-with-confirm flow so the
 * two surfaces are guaranteed to behave identically.
 *
 * The two callers differ only in chrome (Dialog vs settings page
 * layout) — every interaction is delegated here.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { logsAPI, type LogLine } from '@/lib/api/logs';
import { copyToClipboard } from '@/lib/clipboard';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('logs-state');

export type LevelFilter = 'errors' | 'warnings' | 'all';

export const LEVEL_FILTERS: { id: LevelFilter; label: string }[] = [
  { id: 'errors', label: 'Errors' },
  { id: 'warnings', label: 'Errors + warnings' },
  { id: 'all', label: 'All levels' },
];

interface UseLogsStateOpts {
  /** When false (modal closed), the hook skips the initial fetch. */
  active?: boolean;
}

export function useLogsState({ active = true }: UseLogsStateOpts = {}) {
  const { toasts, dismissToast, success, error } = useToast();
  const [lines, setLines] = useState<LogLine[]>([]);
  const [filter, setFilter] = useState<LevelFilter>('errors');
  const [loading, setLoading] = useState(false);
  const [logFilePresent, setLogFilePresent] = useState(true);
  const [confirmingClear, setConfirmingClear] = useState(false);

  // Download-bundle confirmation dialog state. Lives in this hook (not
  // in LogsModal/LogsSection) so both surfaces share the same flow.
  const [downloadDialogOpen, setDownloadDialogOpen] = useState(false);
  const [deleteAfterDownload, setDeleteAfterDownload] = useState(false);
  // Snapshot of the persisted value so we only PUT when the user changed it.
  const persistedDeleteAfterDownload = useRef<boolean>(false);

  const loadLines = useCallback(async () => {
    setLoading(true);
    try {
      const res = await logsAPI.getRecent(200, filter);
      setLines(res.lines);
      setLogFilePresent(res.log_file_present);
    } catch (e) {
      log.error({ err: e }, 'failed to load logs');
      error('Could not load logs');
    } finally {
      setLoading(false);
    }
  }, [filter, error]);

  // Refetch whenever the surface activates or the filter changes.
  useEffect(() => {
    if (!active) return;
    loadLines();
  }, [active, loadLines]);

  // Load the user's "auto-delete on download" preference once the
  // surface activates so the checkbox is pre-set the first time the
  // download dialog opens.
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    (async () => {
      try {
        const prefs = await logsAPI.getPreferences();
        if (cancelled) return;
        persistedDeleteAfterDownload.current = prefs.auto_delete_on_download;
        setDeleteAfterDownload(prefs.auto_delete_on_download);
      } catch (e) {
        // Non-fatal — checkbox just stays unchecked.
        log.warn({ err: e }, 'failed to load log preferences');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [active]);

  const formatLines = useMemo(
    () =>
      lines
        .map((l) => `${l.ts} [${l.level}] ${l.logger}: ${l.message}`)
        .join('\n'),
    [lines],
  );

  const handleCopy = useCallback(async () => {
    if (!lines.length) {
      error('Nothing to copy yet');
      return;
    }
    const ok = await copyToClipboard(formatLines);
    if (ok) success(`Copied ${lines.length} lines`);
    else error('Could not copy. Select the text manually.');
  }, [lines, formatLines, success, error]);

  /**
   * Open the download confirmation dialog instead of starting the
   * download immediately. The actual download + (optional) clear runs in
   * `confirmDownload` once the user clicks the dialog's Download button.
   */
  const handleDownload = useCallback(() => {
    setDownloadDialogOpen(true);
  }, []);

  const confirmDownload = useCallback(async () => {
    setDownloadDialogOpen(false);

    // Start the browser download via anchor (JWT in the query string).
    const a = document.createElement('a');
    a.href = logsAPI.bundleUrl();
    a.rel = 'noopener';
    a.click();

    // Persist the checkbox state if it changed. Fire-and-forget — a
    // preference write failure shouldn't block the bundle download.
    if (deleteAfterDownload !== persistedDeleteAfterDownload.current) {
      logsAPI
        .setPreferences({ auto_delete_on_download: deleteAfterDownload })
        .then(() => {
          persistedDeleteAfterDownload.current = deleteAfterDownload;
        })
        .catch((e) => {
          log.warn({ err: e }, 'failed to persist log preference');
        });
    }

    // If the user opted in, wait briefly so the browser has time to
    // begin streaming the ZIP, then clear the server-side logs.
    if (deleteAfterDownload) {
      window.setTimeout(async () => {
        try {
          await logsAPI.clear();
          success('Logs cleared from server');
          await loadLines();
        } catch (e) {
          log.error({ err: e }, 'failed to clear logs after download');
          error('Could not clear logs after download');
        }
      }, 1500);
    }
  }, [deleteAfterDownload, loadLines, success, error]);

  const handleClear = useCallback(async () => {
    if (!confirmingClear) {
      setConfirmingClear(true);
      // Reset the confirm state if the user walks away.
      setTimeout(() => setConfirmingClear(false), 4000);
      return;
    }
    setConfirmingClear(false);
    setLoading(true);
    try {
      await logsAPI.clear();
      success('Logs cleared');
      await loadLines();
    } catch (e) {
      log.error({ err: e }, 'failed to clear logs');
      error('Could not clear logs');
    } finally {
      setLoading(false);
    }
  }, [confirmingClear, loadLines, success, error]);

  return {
    lines,
    filter,
    setFilter,
    loading,
    logFilePresent,
    confirmingClear,
    loadLines,
    handleCopy,
    handleDownload,
    handleClear,
    // Download confirmation dialog state.
    downloadDialogOpen,
    setDownloadDialogOpen,
    deleteAfterDownload,
    setDeleteAfterDownload,
    confirmDownload,
    // Toast plumbing — the consumer mounts <ToastContainer /> with these.
    toasts,
    dismissToast,
  };
}
