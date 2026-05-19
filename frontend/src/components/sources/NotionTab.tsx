/**
 * NotionTab Component
 *
 * Browse-and-pick UI for adding a Notion page or database as a source.
 * The shared NOTION_API_KEY drives this — no per-user OAuth. If the admin
 * hasn't configured the key, we show a passive "not configured" state
 * (mirroring GoogleDriveTab's pattern).
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CircleNotch,
  MagnifyingGlass,
  NotionLogo,
  Plus,
  FileText,
  Table,
} from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { sourcesAPI, type NotionPickerItem } from '../../lib/api/sources';
import { useToast } from '../ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('notion-tab');

interface NotionTabProps {
  projectId: string;
  isAtLimit: boolean;
  onAdded: () => void;
}

type FilterType = 'all' | 'page' | 'database';

export const NotionTab: React.FC<NotionTabProps> = ({ projectId, isAtLimit, onAdded }) => {
  const { error: toastError, success } = useToast();

  const [statusLoading, setStatusLoading] = useState(true);
  const [configured, setConfigured] = useState(false);

  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [results, setResults] = useState<NotionPickerItem[]>([]);
  const [searching, setSearching] = useState(false);

  // Track which row is currently being imported so we can disable just that
  // row's button (the rest stay clickable).
  const [importingId, setImportingId] = useState<string | null>(null);

  // Debounce the search box so we don't fire on every keystroke.
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await sourcesAPI.getNotionStatus();
        if (cancelled) return;
        setConfigured(status.configured);
      } finally {
        if (!cancelled) setStatusLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Initial + filter-change loads
  useEffect(() => {
    if (!configured) return;
    runSearch(query, filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configured, filter]);

  const runSearch = async (q: string, f: FilterType) => {
    setSearching(true);
    try {
      const items = await sourcesAPI.searchNotion(
        q || undefined,
        f === 'all' ? undefined : f,
        50
      );
      setResults(items);
    } catch (err) {
      log.error({ err }, 'notion search failed');
      toastError('Failed to search Notion');
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => runSearch(value, filter), 300);
  };

  const handlePick = async (item: NotionPickerItem) => {
    if (isAtLimit || importingId) return;
    setImportingId(item.id);
    try {
      await sourcesAPI.addNotionSource(projectId, {
        notion_id: item.id,
        object_type: item.type,
        title: item.title,
        notion_url: item.url,
        last_edited_time: item.last_edited_time,
      });
      success(
        item.type === 'database'
          ? 'Notion database added — fetching rows…'
          : 'Notion page added — fetching content…'
      );
      onAdded();
    } catch (err: unknown) {
      log.error({ err }, 'failed to add notion source');
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
          : null;
      toastError(msg || 'Failed to add Notion source');
    } finally {
      setImportingId(null);
    }
  };

  const filterButtonClass = (active: boolean) =>
    `px-3 py-1.5 text-xs rounded-md border transition-colors ${
      active
        ? 'border-amber-600 bg-amber-600 text-white'
        : 'border-stone-300 bg-stone-100 text-stone-700 hover:bg-stone-200'
    }`;

  const rowIcon = useMemo(() => {
    return (kind: 'page' | 'database') =>
      kind === 'database' ? (
        <Table size={18} weight="duotone" className="text-amber-700 shrink-0" />
      ) : (
        <FileText size={18} weight="duotone" className="text-stone-600 shrink-0" />
      );
  }, []);

  if (statusLoading) {
    return (
      <div className="flex justify-center py-8">
        <CircleNotch size={24} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!configured) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <NotionLogo size={48} weight="duotone" className="text-muted-foreground mb-4" />
        <h3 className="font-medium mb-2">Notion Not Configured</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          An administrator needs to add the Notion integration token in
          Admin Settings → API Keys (<code>NOTION_API_KEY</code>) before
          this can be used.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm">
        Pick a Notion page or database to import. The page content (including
        nested toggles and sub-pages) is fetched once and embedded for
        semantic search in chat.
      </p>

      <div className="relative">
        <MagnifyingGlass
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          className="pl-9"
          placeholder="Search Notion…"
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          disabled={isAtLimit}
        />
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          className={filterButtonClass(filter === 'all')}
          onClick={() => setFilter('all')}
        >
          All
        </button>
        <button
          type="button"
          className={filterButtonClass(filter === 'page')}
          onClick={() => setFilter('page')}
        >
          Pages
        </button>
        <button
          type="button"
          className={filterButtonClass(filter === 'database')}
          onClick={() => setFilter('database')}
        >
          Databases
        </button>
      </div>

      <div className="border rounded-md max-h-96 overflow-y-auto">
        {searching ? (
          <div className="flex justify-center py-8">
            <CircleNotch size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : results.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-8 px-4">
            No Notion {filter === 'all' ? 'pages or databases' : `${filter}s`} found.
            Make sure your Notion integration has been shared with the workspace
            you want to import from.
          </div>
        ) : (
          <ul className="divide-y">
            {results.map((item) => (
              <li
                key={item.id}
                className="flex items-center gap-3 px-3 py-2 hover:bg-stone-50"
              >
                {rowIcon(item.type)}
                <div className="flex-1 min-w-0">
                  <div className="truncate text-sm font-medium">
                    {item.title || 'Untitled'}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {item.type === 'database' ? 'Database' : 'Page'}
                    {item.last_edited_time
                      ? ` · edited ${new Date(item.last_edited_time).toLocaleDateString()}`
                      : ''}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="soft"
                  onClick={() => handlePick(item)}
                  disabled={isAtLimit || importingId !== null}
                >
                  {importingId === item.id ? (
                    <>
                      <CircleNotch size={14} className="mr-1.5 animate-spin" />
                      Adding…
                    </>
                  ) : (
                    <>
                      <Plus size={14} className="mr-1.5" />
                      Add
                    </>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
