/**
 * PreviewToolbar — single-row chrome above the source preview body.
 *
 * Composition (left → right):
 *   - Source title + status pill
 *   - Metadata pill row (type · size · tokens · processed date)
 *   - Search input + match count + prev/next
 *   - Page nav (PDF only)
 *   - Image fit toggle (IMAGE only)
 *   - Download button
 *
 * The visual idiom is "editorial reading room": hairline dividers
 * between segments instead of bordered buttons; muted stone palette
 * with amber as the single accent for active states.
 */
import React from 'react';
import {
  MagnifyingGlass,
  CaretLeft,
  CaretRight,
  Download,
  ArrowsOut,
  ArrowsIn,
  X,
} from '@phosphor-icons/react';
import { Input } from '../../ui/input';
import { Button } from '../../ui/button';
import type { Source } from '../../../lib/api/sources';
import type { DocSearchAPI } from './useDocSearch';

interface PreviewToolbarProps {
  source: Source;
  search: DocSearchAPI;
  // PDF-only
  pdfPage?: number;
  pdfTotalPages?: number;
  onPdfPageChange?: (page: number) => void;
  // Image-only
  fitMode?: 'fit' | 'actual';
  onFitModeChange?: (mode: 'fit' | 'actual') => void;
  onDownload?: () => void;
}

const Pill: React.FC<{
  children: React.ReactNode;
  tone?: 'neutral' | 'amber';
  title?: string;
}> = ({ children, tone = 'neutral', title }) => (
  <span
    title={title}
    className={
      tone === 'amber'
        ? 'inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-medium text-amber-800'
        : 'inline-flex items-center gap-1 rounded-full border border-stone-200/60 bg-stone-100 px-2.5 py-0.5 text-[11px] text-stone-600'
    }
  >
    {children}
  </span>
);

const Divider: React.FC = () => <span className="h-6 w-px bg-stone-200/70" />;

function humanFileSize(bytes: number): string {
  if (!bytes && bytes !== 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function formatDate(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '—';
  }
}

export const PreviewToolbar: React.FC<PreviewToolbarProps> = ({
  source,
  search,
  pdfPage,
  pdfTotalPages,
  onPdfPageChange,
  fitMode,
  onFitModeChange,
  onDownload,
}) => {
  const tokenCount =
    (source.embedding_info as { token_count?: number } | undefined)?.token_count;

  const handleSearchKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (e.shiftKey) search.prev();
      else search.next();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      search.clear();
    }
  };

  return (
    <div className="flex-shrink-0 border-b border-stone-200/80 bg-white">
      {/* Title row */}
      <div className="flex items-center gap-3 px-5 pt-4 pb-2">
        <h2
          className="flex-1 truncate text-base font-medium text-stone-900"
          title={source.name}
        >
          {source.name}
        </h2>
        <Pill tone="amber" title={`Source type: ${source.type ?? 'unknown'}`}>
          {source.type ?? 'UNKNOWN'}
        </Pill>
      </div>

      {/* Metadata + actions row */}
      <div className="flex flex-wrap items-center gap-3 px-5 py-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Pill>{humanFileSize(source.file_size)}</Pill>
          {tokenCount != null && (
            <Pill title={`${tokenCount.toLocaleString()} tokens`}>
              {tokenCount.toLocaleString()} tk
            </Pill>
          )}
          <Pill>{formatDate(source.updated_at || source.created_at)}</Pill>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {/* Search */}
          <div className="relative flex items-center">
            <MagnifyingGlass
              size={14}
              className="absolute left-2.5 text-stone-400"
            />
            <Input
              value={search.term}
              onChange={(e) => search.setTerm(e.target.value)}
              onKeyDown={handleSearchKey}
              placeholder="Find in document"
              className="h-8 w-56 bg-stone-100/60 pl-7 pr-16 text-[13px] text-stone-700 placeholder:text-stone-400 focus-visible:bg-white focus-visible:ring-1 focus-visible:ring-amber-300"
            />
            {search.term && (
              <span className="absolute right-2 flex items-center gap-1 text-[11px] tabular-nums text-stone-500">
                <span>
                  {search.count === 0 ? 0 : search.active + 1}/{search.count}
                </span>
                <button
                  type="button"
                  onClick={search.clear}
                  className="rounded p-0.5 text-stone-400 hover:text-stone-700"
                  aria-label="Clear search"
                >
                  <X size={11} />
                </button>
              </span>
            )}
          </div>
          {search.term && (
            <div className="flex items-center">
              <button
                type="button"
                onClick={search.prev}
                className="rounded p-1 text-stone-500 hover:bg-stone-100 hover:text-stone-800 disabled:opacity-40"
                disabled={search.count === 0}
                aria-label="Previous match"
              >
                <CaretLeft size={14} />
              </button>
              <button
                type="button"
                onClick={search.next}
                className="rounded p-1 text-stone-500 hover:bg-stone-100 hover:text-stone-800 disabled:opacity-40"
                disabled={search.count === 0}
                aria-label="Next match"
              >
                <CaretRight size={14} />
              </button>
            </div>
          )}

          {/* PDF page nav */}
          {pdfTotalPages != null && pdfPage != null && onPdfPageChange && (
            <>
              <Divider />
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onPdfPageChange(Math.max(1, pdfPage - 1))}
                  disabled={pdfPage <= 1}
                  className="rounded p-1 text-stone-500 hover:bg-stone-100 hover:text-stone-800 disabled:opacity-40"
                  aria-label="Previous page"
                >
                  <CaretLeft size={14} />
                </button>
                <span className="px-1 text-[12px] tabular-nums text-stone-600">
                  {pdfPage} / {pdfTotalPages}
                </span>
                <button
                  type="button"
                  onClick={() => onPdfPageChange(Math.min(pdfTotalPages, pdfPage + 1))}
                  disabled={pdfPage >= pdfTotalPages}
                  className="rounded p-1 text-stone-500 hover:bg-stone-100 hover:text-stone-800 disabled:opacity-40"
                  aria-label="Next page"
                >
                  <CaretRight size={14} />
                </button>
              </div>
            </>
          )}

          {/* Image fit toggle */}
          {fitMode && onFitModeChange && (
            <>
              <Divider />
              <button
                type="button"
                onClick={() => onFitModeChange(fitMode === 'fit' ? 'actual' : 'fit')}
                className="rounded p-1.5 text-stone-500 hover:bg-stone-100 hover:text-stone-800"
                aria-label={fitMode === 'fit' ? 'Actual size' : 'Fit to window'}
              >
                {fitMode === 'fit' ? <ArrowsOut size={14} /> : <ArrowsIn size={14} />}
              </button>
            </>
          )}

          {/* Download */}
          {onDownload && (
            <>
              <Divider />
              <Button
                variant="ghost"
                size="sm"
                onClick={onDownload}
                className="h-8 px-2 text-stone-600 hover:text-stone-900"
              >
                <Download size={14} className="mr-1.5" />
                <span className="text-[12px]">Download</span>
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
