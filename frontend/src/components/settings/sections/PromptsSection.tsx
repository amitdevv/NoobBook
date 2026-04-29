/**
 * PromptsSection — Admin Settings → Prompts (Roadmap #16).
 *
 * Two-pane layout: filterable list of all 32 shipped prompts on the
 * left, full editor on the right. The list is grouped by category
 * (Chat / Studio / Extraction / Agents) with thin uppercase headers —
 * subtle so the eye is drawn to prompt names, not the dividers.
 *
 * Aesthetic. Library/index page: monospace prompt names sit in tight
 * rows, descriptions wrap once and truncate, the "Edited" pill is the
 * only saturated mark in the rail. Empty state on the right has a
 * single ghost icon + tagline — no busy work.
 *
 * Interaction.
 *   - Click a row → fetch detail, hand off to the editor.
 *   - Save / reset in the editor → bubble updated detail back so the
 *     "Edited" pill in the rail stays in sync without a full refetch.
 *   - "Edit in Models →" link in the editor dispatches a
 *     `noobbook:settings:switch-section` event, which AppSettings
 *     listens to and routes to the Models tab.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { CircleNotch, Code, MagnifyingGlass, Sparkle, X } from '@phosphor-icons/react';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/use-toast';
import {
  promptsAPI,
  type PromptDetail,
  type PromptSummary,
} from '@/lib/api/admin/prompts';
import { categoryFor, CATEGORY_LABELS, CATEGORY_ORDER, type PromptCategory } from './promptsLib';
import { PromptEditor } from './PromptEditor';
import { createLogger } from '@/lib/logger';

const log = createLogger('prompts-section');

export const PromptsSection: React.FC = () => {
  const { error } = useToast();

  const [summaries, setSummaries] = useState<PromptSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);

  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [filter, setFilter] = useState('');

  // Load list once on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setListLoading(true);
        const res = await promptsAPI.list();
        if (cancelled) return;
        setSummaries(res.data.prompts || []);
      } catch (err) {
        log.error({ err }, 'failed to load prompts');
        if (!cancelled) error('Failed to load prompts');
      } finally {
        if (!cancelled) setListLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [error]);

  // Load detail when selection changes.
  useEffect(() => {
    if (!selectedName) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        setDetailLoading(true);
        const res = await promptsAPI.get(selectedName);
        if (cancelled) return;
        setDetail(res.data.prompt);
      } catch (err) {
        log.error({ err, selectedName }, 'failed to load prompt detail');
        if (!cancelled) error('Failed to load prompt');
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedName, error]);

  // Bubble editor changes back to the list rail so the "Edited" pill stays accurate.
  const handleDetailChange = (next: PromptDetail) => {
    setDetail(next);
    setSummaries((prev) =>
      prev.map((row) =>
        row.prompt_name === next.prompt_name
          ? {
              ...row,
              has_override: Boolean(next.override),
              max_tokens:
                typeof next.effective.max_tokens === 'number'
                  ? next.effective.max_tokens
                  : row.max_tokens,
              temperature:
                typeof next.effective.temperature === 'number'
                  ? next.effective.temperature
                  : row.temperature,
            }
          : row,
      ),
    );
  };

  // Filter + group for the left rail.
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return summaries;
    return summaries.filter(
      (row) =>
        row.prompt_name.toLowerCase().includes(needle) ||
        row.name.toLowerCase().includes(needle) ||
        row.description.toLowerCase().includes(needle),
    );
  }, [summaries, filter]);

  const grouped = useMemo(() => {
    const buckets: Record<PromptCategory, PromptSummary[]> = {
      chat: [],
      studio: [],
      extraction: [],
      agents: [],
    };
    filtered.forEach((row) => buckets[categoryFor(row.prompt_name)].push(row));
    // Within each bucket, alphabetize by display name.
    Object.values(buckets).forEach((bucket) =>
      bucket.sort((a, b) => a.name.localeCompare(b.name)),
    );
    return buckets;
  }, [filtered]);

  const totalEdited = summaries.filter((s) => s.has_override).length;

  // Bridge to the parent dialog for "Edit in Models →".
  const handleSwitchSection = (section: 'models') => {
    window.dispatchEvent(
      new CustomEvent('noobbook:settings:switch-section', { detail: section }),
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* ── Section header ───────────────────────────────────────── */}
      <div className="flex-shrink-0 mb-5">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="text-base font-medium text-stone-900 mb-1">Prompts</h2>
            <p className="text-sm text-muted-foreground max-w-xl">
              Edit any system prompt without a release. Locked variables are required by
              the consuming service — leaving them in keeps everything wired up.
            </p>
          </div>
          {totalEdited > 0 && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10.5px] uppercase tracking-wider font-medium bg-amber-50 text-amber-800 border border-amber-200/80 flex-shrink-0">
              <Sparkle size={10} weight="fill" />
              {totalEdited} edited
            </span>
          )}
        </div>
      </div>

      {/* ── Two-pane body ────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 grid grid-cols-12 gap-0 border border-stone-200 rounded-lg overflow-hidden bg-white">
        {/* Left rail */}
        <aside className="col-span-12 md:col-span-4 lg:col-span-4 xl:col-span-3 border-r border-stone-200 bg-stone-50/40 flex flex-col min-h-0">
          <div className="px-3 py-3 border-b border-stone-200/80 flex-shrink-0">
            <div className="relative">
              <MagnifyingGlass
                size={13}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400"
              />
              <Input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter prompts…"
                className="pl-7 pr-7 h-8 text-[12.5px] bg-white"
              />
              {filter && (
                <button
                  type="button"
                  onClick={() => setFilter('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
                  aria-label="Clear filter"
                >
                  <X size={12} weight="bold" />
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto py-2">
            {listLoading ? (
              <div className="flex items-center justify-center py-8 text-stone-400">
                <CircleNotch size={20} className="animate-spin" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-8 text-center text-[12px] text-stone-500">
                No prompts match <span className="font-mono">"{filter}"</span>.
              </div>
            ) : (
              CATEGORY_ORDER.map((cat) => {
                const rows = grouped[cat];
                if (rows.length === 0) return null;
                return (
                  <div key={cat} className="mb-3 last:mb-0">
                    <div className="px-3 pt-1.5 pb-1 text-[10px] uppercase tracking-[0.14em] font-semibold text-stone-400">
                      {CATEGORY_LABELS[cat]}
                    </div>
                    <div className="space-y-px">
                      {rows.map((row) => {
                        const isActive = selectedName === row.prompt_name;
                        return (
                          <button
                            key={row.prompt_name}
                            type="button"
                            onClick={() => setSelectedName(row.prompt_name)}
                            className={[
                              'w-full text-left px-3 py-1.5 transition-colors group',
                              isActive
                                ? 'bg-amber-50 border-l-2 border-amber-500 -ml-px pl-[calc(0.75rem-1px)]'
                                : 'border-l-2 border-transparent hover:bg-stone-100/70',
                            ].join(' ')}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span
                                className={[
                                  'font-mono text-[11.5px] truncate',
                                  isActive
                                    ? 'text-amber-900 font-medium'
                                    : 'text-stone-800 group-hover:text-stone-900',
                                ].join(' ')}
                              >
                                {row.prompt_name}
                              </span>
                              {row.has_override && (
                                <Sparkle
                                  size={10}
                                  weight="fill"
                                  className={
                                    isActive ? 'text-amber-600' : 'text-amber-500/80'
                                  }
                                />
                              )}
                            </div>
                            {row.description && (
                              <div
                                className={[
                                  'text-[11px] truncate mt-0.5 leading-snug',
                                  isActive
                                    ? 'text-amber-800/70'
                                    : 'text-stone-500 group-hover:text-stone-600',
                                ].join(' ')}
                              >
                                {row.description}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* Right pane */}
        <section className="col-span-12 md:col-span-8 lg:col-span-8 xl:col-span-9 min-h-0 flex flex-col">
          {!selectedName ? (
            <EmptyState />
          ) : detailLoading || !detail ? (
            <div className="flex-1 flex items-center justify-center text-stone-400">
              <CircleNotch size={22} className="animate-spin" />
            </div>
          ) : (
            <PromptEditor
              detail={detail}
              onChange={handleDetailChange}
              onSwitchSection={handleSwitchSection}
            />
          )}
        </section>
      </div>
    </div>
  );
};

const EmptyState: React.FC = () => (
  <div className="flex-1 flex items-center justify-center px-8">
    <div className="text-center max-w-sm">
      <div className="mx-auto mb-4 inline-flex items-center justify-center h-12 w-12 rounded-full bg-stone-100 text-stone-400">
        <Code size={22} weight="duotone" />
      </div>
      <h3 className="text-sm font-medium text-stone-700 mb-1">
        Pick a prompt to edit
      </h3>
      <p className="text-[12.5px] text-stone-500 leading-relaxed">
        Every prompt that ships with NoobBook is here. Edits land in
        <span className="font-mono text-stone-600"> data/prompt_overrides/</span>
        and survive container redeploys.
      </p>
    </div>
  </div>
);
