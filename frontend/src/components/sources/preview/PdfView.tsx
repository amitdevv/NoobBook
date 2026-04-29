/**
 * PdfView — renders a PDF page-by-page with react-pdf (pdfjs-dist).
 *
 * The pdfjs worker is loaded from a CDN URL keyed to the same version
 * as the installed pdfjs-dist package. Bundling the worker via Vite
 * works too but adds ~600KB to the lazy chunk; the CDN approach keeps
 * the chunk small and lets the browser cache it across deployments.
 *
 * Page nav state is owned by the parent (SourcePreviewSheet) so the
 * toolbar's Page-of-N display stays in sync. Search highlighting
 * piggybacks on react-pdf's textLayer: after every page render we
 * post-process the textLayer DOM the same way MarkdownView does.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { CircleNotch } from '@phosphor-icons/react';
import type { DocSearchAPI } from './useDocSearch';

// Pin the worker to the bundled pdfjs-dist version so a future bump
// can't drift the worker out of sync with the API. The unpkg host is
// well-cached and CORS-safe.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfViewProps {
  url: string;
  page: number;
  onTotalPages: (total: number) => void;
  search: DocSearchAPI;
}

export const PdfView: React.FC<PdfViewProps> = ({ url, page, onTotalPages, search }) => {
  const [width, setWidth] = useState<number | undefined>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  // Tracks which page number currently has a rendered text layer in
  // the DOM. Compared against the `page` prop to know whether
  // `applyHighlights` has anything to walk. Storing the page number
  // (rather than a boolean + a separate "reset on page change" effect)
  // means we never have to write state from inside an effect.
  const [renderedPage, setRenderedPage] = useState(0);
  const textLayerReady = renderedPage === page;

  // Keep the page width responsive so the document fills the modal
  // body without overflowing horizontally.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { term, registerMatches } = search;

  // The highlight pass is shared by two triggers:
  //   1. onRenderSuccess fires it after a fresh page renders
  //   2. a useEffect fires it when search.term changes mid-page
  // Wrapped in useCallback so the effect's dep list is stable.
  const applyHighlights = useCallback(() => {
    const root = containerRef.current?.querySelector('.react-pdf__Page__textContent');
    if (!root) return;

    // Clear prior marks idempotently.
    root.querySelectorAll('mark[data-doc-search]').forEach((m) => {
      const parent = m.parentNode;
      if (!parent) return;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    });

    const trimmed = term.trim();
    if (!trimmed) {
      registerMatches([]);
      return;
    }
    const lowerTerm = trimmed.toLowerCase();
    const matches: HTMLElement[] = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) =>
        n.nodeValue && n.nodeValue.toLowerCase().includes(lowerTerm)
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT,
    });
    const textNodes: Text[] = [];
    let cur: Node | null;
    while ((cur = walker.nextNode())) textNodes.push(cur as Text);

    textNodes.forEach((node) => {
      const text = node.nodeValue ?? '';
      const fragment = document.createDocumentFragment();
      let cursor = 0;
      const lower = text.toLowerCase();
      while (cursor < text.length) {
        const idx = lower.indexOf(lowerTerm, cursor);
        if (idx === -1) {
          fragment.appendChild(document.createTextNode(text.slice(cursor)));
          break;
        }
        if (idx > cursor) fragment.appendChild(document.createTextNode(text.slice(cursor, idx)));
        const mark = document.createElement('mark');
        mark.dataset.docSearch = 'true';
        mark.style.backgroundColor = 'rgba(252, 211, 77, 0.7)';
        mark.style.color = 'inherit';
        mark.textContent = text.slice(idx, idx + trimmed.length);
        fragment.appendChild(mark);
        matches.push(mark);
        cursor = idx + trimmed.length;
      }
      node.parentNode?.replaceChild(fragment, node);
    });
    registerMatches(matches);
  }, [term, registerMatches]);

  const onPageRendered = () => {
    setRenderedPage(page);
    applyHighlights();
  };

  // Re-run the highlight pass when the search term changes while the
  // user is staring at an already-rendered page. Without this, typing
  // in the search box doesn't highlight anything until the user
  // navigates to another page and back.
  useEffect(() => {
    if (!textLayerReady) return;
    applyHighlights();
  }, [term, textLayerReady, applyHighlights]);

  return (
    <div ref={containerRef} className="w-full flex flex-col items-center">
      <Document
        file={url}
        onLoadSuccess={({ numPages }) => onTotalPages(numPages)}
        loading={
          <div className="h-96 flex items-center justify-center text-sm text-stone-500">
            <CircleNotch size={18} className="mr-2 animate-spin" />
            Loading PDF…
          </div>
        }
        error={
          <div className="h-32 flex items-center justify-center text-sm text-rose-600">
            Failed to load PDF.
          </div>
        }
      >
        <Page
          pageNumber={page}
          width={width}
          onRenderSuccess={onPageRendered}
          className="shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.18)] rounded-sm overflow-hidden bg-white"
          renderAnnotationLayer
          renderTextLayer
        />
      </Document>
    </div>
  );
};
