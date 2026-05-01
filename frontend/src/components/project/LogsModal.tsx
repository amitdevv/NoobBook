/**
 * LogsModal — admin diagnostic logs viewer.
 *
 * Aesthetic direction: a small "operator's console" embedded inside the
 * warm cream chrome of the rest of the app. The dialog header and action
 * row stay in the project palette (stone / amber); the log viewer panel
 * itself flips dark (stone-900) with monospace text and color-coded
 * level pills, signalling "this is the under-the-hood view." The
 * contrast is the differentiator — it reads as a real terminal, not just
 * another card.
 *
 * Composition:
 *   ┌─ Header ─────────────────────────────────┐
 *   │ Diagnostic logs · 24KB · 3 archives      │
 *   ├──────────────────────────────────────────┤
 *   │ ┌─ stone-900 panel, monospace ───────┐  │
 *   │ │ 10:23:44  ERROR  module.path       │  │
 *   │ │   message line one                 │  │
 *   │ │   stack trace continuation         │  │
 *   │ │ 10:23:42  WARN   module.path       │  │
 *   │ └──────────────────────────────────────┘  │
 *   ├──────────────────────────────────────────┤
 *   │ [Clear] [Copy]        [Download bundle ↓]│
 *   └──────────────────────────────────────────┘
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import {
  ArrowsClockwise,
  Bug,
  CircleNotch,
  Copy,
  DownloadSimple,
  Trash,
  Warning,
  XCircle,
} from '@phosphor-icons/react';
import { useToast } from '../ui/use-toast';
import { ToastContainer } from '../ui/toast';
import { logsAPI, type LogLine } from '@/lib/api/logs';
import { copyToClipboard } from '@/lib/clipboard';
import { createLogger } from '@/lib/logger';

const log = createLogger('logs-modal');

interface LogsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type LevelFilter = 'errors' | 'warnings' | 'all';

const FILTERS: { id: LevelFilter; label: string }[] = [
  { id: 'errors', label: 'Errors' },
  { id: 'warnings', label: 'Errors + warnings' },
  { id: 'all', label: 'All levels' },
];

export const LogsModal: React.FC<LogsModalProps> = ({ open, onOpenChange }) => {
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

  useEffect(() => {
    if (open) loadLines();
  }, [open, loadLines]);

  const formatLines = useMemo(
    () =>
      lines
        .map((l) => `${l.ts} [${l.level}] ${l.logger}: ${l.message}`)
        .join('\n'),
    [lines],
  );

  const handleCopy = async () => {
    if (!lines.length) {
      error('Nothing to copy yet');
      return;
    }
    const ok = await copyToClipboard(formatLines);
    if (ok) success(`Copied ${lines.length} lines`);
    else error('Could not copy. Select the text manually.');
  };

  const handleDownload = () => {
    // Browser download with the JWT carried as query param — same pattern
    // as studio output downloads. <a download> can't set Authorization
    // headers, hence the helper.
    const a = document.createElement('a');
    a.href = logsAPI.bundleUrl();
    a.rel = 'noopener';
    a.click();
  };

  const handleClear = async () => {
    if (!confirmingClear) {
      setConfirmingClear(true);
      // Reset the confirm state if the admin walks away from the button.
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
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[760px] max-h-[88vh] p-0 overflow-hidden flex flex-col">
        {/* ── Header ─────────────────────────────────────── */}
        <div className="px-7 pt-6 pb-4 border-b flex-shrink-0">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-semibold pr-8">
              <Bug size={18} className="text-primary flex-shrink-0" />
              <span>Diagnostic logs</span>
            </DialogTitle>
            <DialogDescription className="text-xs leading-relaxed text-muted-foreground mt-1">
              Recent backend + frontend errors from this deployment. Download
              the bundle to share a complete snapshot with support — log files,
              env-var keys, and migration state are included.
            </DialogDescription>
          </DialogHeader>

          {/* Filter chips */}
          <div className="mt-4 flex items-center gap-2 flex-wrap">
            {FILTERS.map((f) => {
              const isActive = filter === f.id;
              return (
                <button
                  key={f.id}
                  onClick={() => setFilter(f.id)}
                  className={[
                    'px-3 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full border transition-colors',
                    isActive
                      ? 'border-primary/40 bg-primary/5 text-foreground'
                      : 'border-border/60 bg-background text-muted-foreground hover:text-foreground',
                  ].join(' ')}
                  aria-pressed={isActive}
                >
                  {f.label}
                </button>
              );
            })}
            <button
              onClick={loadLines}
              className="ml-auto inline-flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full text-muted-foreground hover:text-foreground"
              title="Refresh"
            >
              <ArrowsClockwise
                size={12}
                className={loading ? 'animate-spin' : ''}
              />
              Refresh
            </button>
          </div>
        </div>

        {/* ── Console panel ──────────────────────────────── */}
        <div className="flex-1 overflow-hidden bg-stone-50 px-7 py-5">
          <div className="h-full rounded-lg border border-stone-800/60 bg-stone-900 text-stone-100 font-mono text-[12px] leading-relaxed shadow-inner overflow-y-auto">
            {loading && lines.length === 0 ? (
              <div className="h-full flex items-center justify-center text-stone-400">
                <CircleNotch size={16} className="mr-2 animate-spin" />
                Loading logs…
              </div>
            ) : !logFilePresent ? (
              <div className="h-full flex flex-col items-center justify-center text-stone-400 px-6 py-10 text-center">
                <p className="text-stone-200">No log file on disk yet.</p>
                <p className="text-[11px] mt-1 max-w-sm">
                  The rotating handler creates the file on the first log line.
                  Trigger any action and refresh.
                </p>
              </div>
            ) : lines.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-stone-400 px-6 py-10 text-center">
                <p className="text-stone-200">All quiet.</p>
                <p className="text-[11px] mt-1">
                  No matching lines for this filter.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-stone-800/80">
                {lines.map((l, i) => (
                  <LogRow key={i} line={l} />
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* ── Action row ─────────────────────────────────── */}
        <div className="px-7 py-4 border-t flex items-center gap-2 flex-shrink-0 bg-background">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClear}
            disabled={loading}
            className={
              confirmingClear
                ? 'gap-2 text-rose-700 hover:text-rose-800'
                : 'gap-2 text-muted-foreground hover:text-foreground'
            }
          >
            <Trash size={14} />
            {confirmingClear ? 'Click again to clear' : 'Clear logs'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            disabled={loading || !lines.length}
            className="gap-2 text-muted-foreground hover:text-foreground"
          >
            <Copy size={14} />
            Copy view
          </Button>

          <div className="flex-1" />

          <Button
            variant="default"
            size="sm"
            onClick={handleDownload}
            className="gap-2"
          >
            <DownloadSimple size={14} weight="bold" />
            Download bundle (.zip)
          </Button>
        </div>

        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </DialogContent>
    </Dialog>
  );
};

/**
 * LogRow
 *
 * One log entry. The header line packs timestamp + level pill + module
 * path. The message body indents below — multi-line stack traces stay
 * vertically aligned with the message, not the timestamp, which keeps
 * the console scannable when several long traces stack up.
 */
const LogRow: React.FC<{ line: LogLine }> = ({ line }) => {
  const isError = line.level === 'ERROR' || line.level === 'CRITICAL';
  const isWarn = line.level === 'WARNING';

  return (
    <li className="px-4 py-2.5 hover:bg-stone-800/40 transition-colors">
      <div className="flex items-center gap-2 text-[11px] tracking-tight">
        <span className="text-stone-500 tabular-nums">{line.ts}</span>
        <span
          className={[
            'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm uppercase tracking-[0.06em] text-[10px] font-semibold',
            isError
              ? 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30'
              : isWarn
                ? 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30'
                : 'bg-stone-700/40 text-stone-400 ring-1 ring-stone-600/30',
          ].join(' ')}
        >
          {isError ? (
            <XCircle size={10} weight="fill" />
          ) : isWarn ? (
            <Warning size={10} weight="fill" />
          ) : null}
          {line.level}
        </span>
        <span className="text-stone-400 truncate" title={line.logger}>
          {line.logger}
        </span>
      </div>
      <pre className="mt-1 whitespace-pre-wrap break-words text-stone-100 text-[12px] leading-relaxed font-mono pl-[3px]">
        {line.message}
      </pre>
    </li>
  );
};
