/**
 * LogsSection — settings-page variant of the diagnostic logs viewer.
 *
 * Same console aesthetic as `LogsModal` but reflows for the settings
 * content area: full-width panel, no Dialog chrome, prose-style intro
 * paragraph that explains what the bundle contains so the admin knows
 * what they're sharing.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowsClockwise,
  CircleNotch,
  Copy,
  DownloadSimple,
  Trash,
  Warning,
  XCircle,
} from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { logsAPI, type LogLine } from '@/lib/api/logs';
import { copyToClipboard } from '@/lib/clipboard';
import { createLogger } from '@/lib/logger';

const log = createLogger('logs-section');

type LevelFilter = 'errors' | 'warnings' | 'all';

const FILTERS: { id: LevelFilter; label: string }[] = [
  { id: 'errors', label: 'Errors' },
  { id: 'warnings', label: 'Errors + warnings' },
  { id: 'all', label: 'All levels' },
];

export const LogsSection: React.FC = () => {
  const { success, error } = useToast();
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
    loadLines();
  }, [loadLines]);

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
    const a = document.createElement('a');
    a.href = logsAPI.bundleUrl();
    a.rel = 'noopener';
    a.click();
  };

  const handleClear = async () => {
    if (!confirmingClear) {
      setConfirmingClear(true);
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
    <div className="max-w-5xl space-y-6 pb-8">
      <header>
        <h2 className="text-lg font-semibold text-stone-900">Diagnostic logs</h2>
        <p className="mt-1 text-sm text-stone-600 max-w-prose leading-relaxed">
          Recent backend and frontend errors from this deployment. Download the{' '}
          <strong>support bundle</strong> to share a complete snapshot — the ZIP
          includes the rotating log files (with secrets scrubbed), env-var
          names, applied migrations, and deployment metadata.
        </p>
      </header>

      {/* Filter row */}
      <div className="flex items-center gap-2 flex-wrap">
        {FILTERS.map((f) => {
          const isActive = filter === f.id;
          return (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={[
                'px-3 py-1 text-[11px] uppercase tracking-[0.08em] rounded-full border transition-colors',
                isActive
                  ? 'border-amber-500/50 bg-amber-50 text-stone-900'
                  : 'border-stone-200 bg-white text-stone-500 hover:text-stone-900',
              ].join(' ')}
              aria-pressed={isActive}
            >
              {f.label}
            </button>
          );
        })}
        <button
          onClick={loadLines}
          className="ml-auto inline-flex items-center gap-1 px-2 py-1 text-[11px] uppercase tracking-[0.08em] text-stone-500 hover:text-stone-900"
          title="Refresh"
        >
          <ArrowsClockwise size={12} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Console panel */}
      <div className="rounded-lg border border-stone-800/60 bg-stone-900 text-stone-100 font-mono text-[12px] leading-relaxed shadow-inner overflow-hidden">
        <div className="max-h-[58vh] overflow-y-auto">
          {loading && lines.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-stone-400">
              <CircleNotch size={16} className="mr-2 animate-spin" />
              Loading logs…
            </div>
          ) : !logFilePresent ? (
            <div className="h-48 flex flex-col items-center justify-center text-stone-400 px-6 text-center">
              <p className="text-stone-200">No log file on disk yet.</p>
              <p className="text-[11px] mt-1 max-w-sm">
                The rotating handler creates the file on the first log line.
                Trigger any action and refresh.
              </p>
            </div>
          ) : lines.length === 0 ? (
            <div className="h-48 flex flex-col items-center justify-center text-stone-400 px-6 text-center">
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

      {/* Action row */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleClear}
          disabled={loading}
          className={
            confirmingClear
              ? 'gap-2 text-rose-700 hover:text-rose-800'
              : 'gap-2 text-stone-500 hover:text-stone-900'
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
          className="gap-2 text-stone-500 hover:text-stone-900"
        >
          <Copy size={14} />
          Copy view
        </Button>

        <div className="flex-1" />

        <Button variant="default" size="sm" onClick={handleDownload} className="gap-2">
          <DownloadSimple size={14} weight="bold" />
          Download bundle (.zip)
        </Button>
      </div>
    </div>
  );
};

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
