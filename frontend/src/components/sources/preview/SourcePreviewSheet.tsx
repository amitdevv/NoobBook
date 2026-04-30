/**
 * SourcePreviewSheet — type-aware preview modal that replaces the old
 * ProcessedContentSheet.
 *
 * Branches per source.type:
 *   PDF                    → PdfView (raw signed URL + page nav)
 *   IMAGE                  → ImageView (raw signed URL)
 *   AUDIO                  → AudioView (raw signed URL + transcript)
 *   CSV                    → CsvTableView (raw signed URL, parsed)
 *   TEXT/DOCX/LINK/...     → MarkdownView (extracted text via /processed)
 *
 * Owns:
 *   - Fetch lifecycle (chooses /raw vs /processed based on type)
 *   - Search state (single useDocSearch instance threaded into views)
 *   - PDF page state, image fit mode
 *
 * Lazy-loads PDF / Image / Audio / CSV views so the heavy react-pdf
 * dependency stays out of the entry bundle.
 */
import React, { Suspense, useCallback, useEffect, useState } from 'react';
import { Sheet, SheetContent, SheetTitle } from '../../ui/sheet';
import { ScrollArea } from '../../ui/scroll-area';
import { CircleNotch, FileX } from '@phosphor-icons/react';
import {
  sourcesAPI,
  getSourceFileExtension,
  getViewKind,
  type Source,
  type SourceViewKind,
} from '../../../lib/api/sources';
import { createLogger } from '@/lib/logger';
import { PreviewToolbar } from './PreviewToolbar';
import { MarkdownView } from './MarkdownView';
import { useDocSearch } from './useDocSearch';
import { DocumentEditorDialog } from '../DocumentEditorDialog';

const log = createLogger('source-preview-sheet');

const PdfView = React.lazy(() => import('./PdfView').then((m) => ({ default: m.PdfView })));
const ImageView = React.lazy(() =>
  import('./ImageView').then((m) => ({ default: m.ImageView })),
);
const AudioView = React.lazy(() =>
  import('./AudioView').then((m) => ({ default: m.AudioView })),
);
const CsvTableView = React.lazy(() =>
  import('./CsvTableView').then((m) => ({ default: m.CsvTableView })),
);

interface SourcePreviewSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  source: Source | null;
}

type Mode = 'raw' | 'processed';

// Kinds whose preview reads the original raw bytes via /raw signed
// URL (PdfView / ImageView / AudioView / CsvTableView). Markdown
// kinds read the extracted text via /processed.
const RAW_KINDS = new Set<SourceViewKind>(['pdf', 'image', 'audio', 'csv']);

function pickMode(kind: SourceViewKind): Mode {
  return RAW_KINDS.has(kind) ? 'raw' : 'processed';
}

export const SourcePreviewSheet: React.FC<SourcePreviewSheetProps> = ({
  open,
  onOpenChange,
  projectId,
  source,
}) => {
  const [content, setContent] = useState<string>('');
  const [rawUrl, setRawUrl] = useState<string>('');
  const [transcript, setTranscript] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [pdfPage, setPdfPage] = useState(1);
  const [pdfTotalPages, setPdfTotalPages] = useState<number | null>(null);
  const [fitMode, setFitMode] = useState<'fit' | 'actual'>('fit');
  const [editOpen, setEditOpen] = useState(false);
  // Bumped after a save to force the fetch effect below to refetch
  // the freshly reprocessed content. Cheaper than tracking every
  // field of the source row.
  const [refetchKey, setRefetchKey] = useState(0);

  const search = useDocSearch();

  // Fetch on open / source change.
  useEffect(() => {
    if (!open || !source) return;

    setContent('');
    setRawUrl('');
    setTranscript(null);
    setErrorMsg(null);
    setPdfPage(1);
    setPdfTotalPages(null);
    setFitMode('fit');
    search.clear();
    setLoading(true);

    let cancelled = false;
    const mode = pickMode(getViewKind(source));

    const work = async () => {
      try {
        if (mode === 'raw') {
          const raw = await sourcesAPI.getRawUrl(projectId, source.id);
          if (cancelled) return;
          setRawUrl(raw.url);
          // Audio sources: also fetch the extracted transcript so we
          // can show it below the player. Failure is non-fatal.
          if (getViewKind(source) === 'audio') {
            try {
              const proc = await sourcesAPI.getProcessedContent(projectId, source.id);
              if (!cancelled) setTranscript(proc.content);
            } catch (e) {
              log.warn({ err: e }, 'transcript fetch failed (non-fatal)');
            }
          }
        } else {
          const proc = await sourcesAPI.getProcessedContent(projectId, source.id);
          if (cancelled) return;
          setContent(proc.content);
        }
      } catch (e) {
        if (!cancelled) {
          log.error({ err: e }, 'failed to load preview');
          setErrorMsg('Failed to load preview.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    work();
    return () => {
      cancelled = true;
    };
    // search and projectId are stable; source.id and refetchKey
    // trigger refetch (the latter after an edit-and-save).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, source?.id, projectId, refetchKey]);

  // Cmd/Ctrl+F focuses the search input. Bound at the sheet level so
  // it works regardless of which view is active inside.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        const el = document.querySelector<HTMLInputElement>(
          'input[placeholder="Find in document"]',
        );
        if (el) {
          e.preventDefault();
          el.focus();
          el.select();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const handleDownload = useCallback(async () => {
    if (!source) return;
    try {
      // Always download the original raw bytes. Falls back to a
      // signed URL even for text-based sources so the user gets the
      // exact content they uploaded, not the page-marker-decorated
      // processed version.
      const raw = await sourcesAPI.getRawUrl(projectId, source.id).catch(() => null);
      if (raw?.url) {
        window.open(raw.url, '_blank', 'noopener');
      } else {
        log.warn('no raw URL available for download');
      }
    } catch (e) {
      log.error({ err: e }, 'download failed');
    }
  }, [projectId, source]);

  // Strip the page-marker header from /processed output so the
  // editor opens with the user's clean markdown body, not the
  // chunker's decorations. Single-page text sources have a single
  // marker line followed by the body; multi-page sources interleave
  // the original content. For now we drop *only* a leading single-page
  // marker (PAGE 1 of 1) — that's the shape pasted-text sources have.
  const stripSinglePageMarker = (raw: string): string =>
    raw.replace(/^===\s*\w+\s*PAGE\s*1\s*of\s*1\s*===\s*\n+/i, '');

  const handleEditSave = useCallback(
    async (markdown: string, name: string) => {
      if (!source) return;
      await sourcesAPI.updateSourceContent(projectId, source.id, markdown, name);
      // Force the fetch effect to refetch with the new content.
      // The status flips to "processing" then back to "ready" — by
      // the time the dialog closes and the refetch runs, the new
      // processed text usually exists. If the user is fast, we'll
      // briefly show a "loading" placeholder.
      setRefetchKey((k) => k + 1);
    },
    [projectId, source],
  );

  if (!source) return null;

  const sourceType = (source.type ?? '').toUpperCase();
  const ext = getSourceFileExtension(source);
  const kind = getViewKind(source);
  // Layout: PDF / IMAGE / CSV breakouts use the modal's full body
  // width; markdown/audio center at the reading-measure 760px column.
  const useFullWidth = kind === 'pdf' || kind === 'image' || kind === 'csv';
  // Edit dialog is TEXT-only — other sources can't be edited in-place.
  const isEditable = sourceType === 'TEXT';

  const renderBody = () => {
    if (loading) {
      return (
        <div className="h-64 flex items-center justify-center text-sm text-stone-500">
          <CircleNotch size={18} className="mr-2 animate-spin" />
          Loading preview…
        </div>
      );
    }
    if (errorMsg) {
      return (
        <div className="flex flex-col items-center justify-center py-16 text-stone-500">
          <FileX size={28} className="mb-2 text-stone-400" />
          <p className="text-sm">{errorMsg}</p>
        </div>
      );
    }

    switch (kind) {
      case 'pdf':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <PdfView
              url={rawUrl}
              page={pdfPage}
              onTotalPages={setPdfTotalPages}
              search={search}
            />
          </Suspense>
        );
      case 'image':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <ImageView url={rawUrl} alt={source.name} fitMode={fitMode} />
          </Suspense>
        );
      case 'audio':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <AudioView url={rawUrl} transcript={transcript} search={search} />
          </Suspense>
        );
      case 'csv':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <CsvTableView url={rawUrl} search={search} />
          </Suspense>
        );
      default:
        // 'markdown' — TEXT, DOCX, PPTX, LINK, YOUTUBE, RESEARCH,
        // DATABASE, MCP, FRESHDESK, JIRA, MIXPANEL all render the
        // extracted-text body the same way.
        return <MarkdownView content={content} search={search} />;
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-[95vw] sm:w-[920px] lg:w-[1080px] max-w-[1100px] flex flex-col p-0 bg-stone-50"
      >
        <SheetTitle className="sr-only">{source.name}</SheetTitle>

        <PreviewToolbar
          source={source}
          search={search}
          pdfPage={kind === 'pdf' ? pdfPage : undefined}
          pdfTotalPages={kind === 'pdf' ? pdfTotalPages ?? undefined : undefined}
          onPdfPageChange={kind === 'pdf' ? setPdfPage : undefined}
          fitMode={kind === 'image' ? fitMode : undefined}
          onFitModeChange={kind === 'image' ? setFitMode : undefined}
          onDownload={ext ? handleDownload : undefined}
          onEdit={isEditable ? () => setEditOpen(true) : undefined}
        />

        <ScrollArea className="flex-1 bg-[radial-gradient(circle_at_top_right,rgba(254,243,199,0.45),transparent_55%)]">
          <div
            className={
              useFullWidth
                ? 'px-6 py-8'
                : 'mx-auto max-w-[760px] px-8 py-10'
            }
          >
            {renderBody()}
          </div>
        </ScrollArea>
      </SheetContent>

      {/* Edit dialog — TEXT sources only. Prefilled with the current
          markdown body (page-marker header stripped). On save,
          updateSourceContent re-uploads + reprocesses, then we bump
          refetchKey to pull the fresh content back into the sheet. */}
      {isEditable && (
        <DocumentEditorDialog
          open={editOpen}
          onOpenChange={setEditOpen}
          onSave={handleEditSave}
          initialMarkdown={stripSinglePageMarker(content)}
          initialName={source.name}
          saveLabel="Save changes"
        />
      )}
    </Sheet>
  );
};
