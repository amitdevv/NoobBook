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
import { useCallback, useEffect, useMemo, useState } from 'react';
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

  const handleDownload = useCallback(() => {
    // Browser download via anchor; getAuthUrl puts the JWT in the query
    // string because <a download> can't set Authorization headers.
    const a = document.createElement('a');
    a.href = logsAPI.bundleUrl();
    a.rel = 'noopener';
    a.click();
  }, []);

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
    // Toast plumbing — the consumer mounts <ToastContainer /> with these.
    toasts,
    dismissToast,
  };
}
