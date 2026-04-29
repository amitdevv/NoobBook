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
import { sourcesAPI, getSourceFileExtension, type Source } from '../../../lib/api/sources';
import { createLogger } from '@/lib/logger';
import { PreviewToolbar } from './PreviewToolbar';
import { MarkdownView } from './MarkdownView';
import { useDocSearch } from './useDocSearch';

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

function pickMode(source: Source): Mode {
  // Raw signed URL types: the browser needs the original bytes.
  // Type field is reliable here — uppercase canonical strings written
  // by the backend's source_upload pipeline.
  const t = (source.type ?? '').toUpperCase();
  if (t === 'PDF' || t === 'IMAGE' || t === 'AUDIO' || t === 'CSV') return 'raw';
  return 'processed';
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
    const mode = pickMode(source);

    const work = async () => {
      try {
        if (mode === 'raw') {
          const raw = await sourcesAPI.getRawUrl(projectId, source.id);
          if (cancelled) return;
          setRawUrl(raw.url);
          // Audio sources: also fetch the extracted transcript so we
          // can show it below the player. Failure is non-fatal.
          if ((source.type ?? '').toUpperCase() === 'AUDIO') {
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
    // search and projectId are stable; source.id triggers refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, source?.id, projectId]);

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

  if (!source) return null;

  const sourceType = (source.type ?? '').toUpperCase();
  const ext = getSourceFileExtension(source);
  const useFullWidth = sourceType === 'PDF' || sourceType === 'IMAGE' || sourceType === 'CSV';

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

    switch (sourceType) {
      case 'PDF':
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
      case 'IMAGE':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <ImageView url={rawUrl} alt={source.name} fitMode={fitMode} />
          </Suspense>
        );
      case 'AUDIO':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <AudioView url={rawUrl} transcript={transcript} search={search} />
          </Suspense>
        );
      case 'CSV':
        return (
          <Suspense fallback={<div className="h-64" />}>
            <CsvTableView url={rawUrl} search={search} />
          </Suspense>
        );
      default:
        // TEXT, DOCX, PPTX, LINK, YOUTUBE, RESEARCH and any future
        // text-derivable type all render the same way.
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
          pdfPage={sourceType === 'PDF' ? pdfPage : undefined}
          pdfTotalPages={sourceType === 'PDF' ? pdfTotalPages ?? undefined : undefined}
          onPdfPageChange={sourceType === 'PDF' ? setPdfPage : undefined}
          fitMode={sourceType === 'IMAGE' ? fitMode : undefined}
          onFitModeChange={sourceType === 'IMAGE' ? setFitMode : undefined}
          onDownload={ext ? handleDownload : undefined}
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
    </Sheet>
  );
};
