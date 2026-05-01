/**
 * LogsSection — settings-page variant of the diagnostic logs viewer.
 *
 * Same console aesthetic as `LogsModal` but reflows for the settings
 * content area: full-width panel, no Dialog chrome, prose-style intro
 * paragraph that explains what the bundle contains so the admin knows
 * what they're sharing.
 *
 * Behavior + content all come from `useLogsState` and `LogConsole` so
 * the modal and this section can never drift out of sync.
 */
import React from 'react';
import { LogConsole } from '@/components/project/LogConsole';
import { useLogsState } from '@/components/project/useLogsState';

export const LogsSection: React.FC = () => {
  const state = useLogsState({ active: true });

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

      <LogConsole
        variant="page"
        panelMaxHeightClassName="max-h-[58vh]"
        lines={state.lines}
        filter={state.filter}
        onFilterChange={state.setFilter}
        loading={state.loading}
        logFilePresent={state.logFilePresent}
        confirmingClear={state.confirmingClear}
        onRefresh={state.loadLines}
        onCopy={state.handleCopy}
        onDownload={state.handleDownload}
        onClear={state.handleClear}
      />
    </div>
  );
};
