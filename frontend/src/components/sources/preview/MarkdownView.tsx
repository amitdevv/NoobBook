/**
 * MarkdownView — renders extracted text (or pasted markdown) with
 * react-markdown, styling existing page markers as section dividers.
 *
 * Search highlighting runs as a post-render pass over the rendered DOM
 * (walk text nodes, wrap matches in <mark>) rather than threading a
 * custom renderer through react-markdown. react-markdown v10's
 * component map only covers element nodes, not text nodes — DOM
 * post-processing is the clean way to intercept rendered text without
 * forking the markdown→HAST pipeline.
 *
 * Used by:
 *   - TEXT  (pasted notes — markdown round-tripped through the editor)
 *   - DOCX, PPTX, LINK, YOUTUBE, RESEARCH (extracted plain text;
 *     markdown-as-text is a graceful superset)
 */
import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { DocSearchAPI } from './useDocSearch';

interface MarkdownViewProps {
  content: string;
  search: DocSearchAPI;
}

// Page-marker regex. We instantiate fresh inside helpers rather than
// share a module-level regex, since stateful global regexes carry
// `lastIndex` between calls and ESLint flags writes to module-level
// values from inside components.
const PAGE_MARKER_PATTERN = '(===\\s*\\w+\\s*PAGE\\s*\\d+\\s*of\\s*\\d+\\s*===)';
function isPageMarker(segment: string): boolean {
  return new RegExp(PAGE_MARKER_PATTERN, 'i').test(segment);
}

export const MarkdownView: React.FC<MarkdownViewProps> = ({ content, search }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Split on page markers so they render as styled separators rather
  // than getting swallowed as plain text. Capturing group keeps the
  // markers in the resulting segment array so we can recognize them.
  const segments = content.split(new RegExp(PAGE_MARKER_PATTERN, 'gi'));

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

    // Strip any previous marks before re-applying. This keeps the
    // post-process idempotent across term/content changes.
    const previous = root.querySelectorAll('mark[data-doc-search]');
    previous.forEach((m) => {
      const parent = m.parentNode;
      if (!parent) return;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    });

    const term = search.term.trim();
    if (!term) {
      search.registerMatches([]);
      return;
    }

    const lowerTerm = term.toLowerCase();
    const matches: HTMLElement[] = [];

    // Walk text nodes; skip nodes inside <pre>/<code> so code blocks
    // stay byte-faithful and inside <mark> so we don't double-wrap.
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        const parent = n.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (parent.closest('pre, code, mark[data-doc-search]')) {
          return NodeFilter.FILTER_REJECT;
        }
        return n.nodeValue && n.nodeValue.toLowerCase().includes(lowerTerm)
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT;
      },
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
        if (idx > cursor) {
          fragment.appendChild(document.createTextNode(text.slice(cursor, idx)));
        }
        const mark = document.createElement('mark');
        mark.dataset.docSearch = 'true';
        mark.textContent = text.slice(idx, idx + term.length);
        fragment.appendChild(mark);
        matches.push(mark);
        cursor = idx + term.length;
      }
      node.parentNode?.replaceChild(fragment, node);
    });

    search.registerMatches(matches);
  }, [content, search.term, search]);

  // Re-style the active match whenever the cursor moves through the
  // collected matches; keeps DOM mutation in one place.
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const marks = root.querySelectorAll<HTMLElement>('mark[data-doc-search]');
    marks.forEach((m, i) => {
      m.className =
        i === search.active
          ? 'bg-amber-400 text-stone-900 rounded-sm px-0.5 ring-2 ring-amber-300/60'
          : 'bg-amber-200/70 text-stone-900 rounded-sm px-0.5';
    });
  }, [search.active, search.count]);

  return (
    <div
      ref={containerRef}
      className="font-serif text-[16px] leading-[1.75] text-stone-800 selection:bg-amber-200/60 [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:mt-8 [&_h1]:mb-3 [&_h1]:text-stone-900 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mt-7 [&_h2]:mb-2 [&_h2]:text-stone-900 [&_h3]:text-lg [&_h3]:font-medium [&_h3]:mt-5 [&_h3]:mb-2 [&_h3]:text-stone-900 [&_p]:my-3 [&_ul]:my-3 [&_ul]:pl-6 [&_ul]:list-disc [&_ol]:my-3 [&_ol]:pl-6 [&_ol]:list-decimal [&_li]:my-1 [&_a]:text-amber-700 [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-amber-800 [&_blockquote]:my-4 [&_blockquote]:pl-4 [&_blockquote]:border-l-2 [&_blockquote]:border-amber-300 [&_blockquote]:text-stone-600 [&_blockquote]:italic [&_code]:bg-stone-100 [&_code]:text-stone-800 [&_code]:rounded [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em] [&_code]:font-mono [&_pre]:bg-stone-900 [&_pre]:text-stone-100 [&_pre]:rounded-lg [&_pre]:p-4 [&_pre]:overflow-x-auto [&_pre_code]:bg-transparent [&_pre_code]:text-stone-100 [&_pre_code]:p-0 [&_table]:my-4 [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-stone-200 [&_th]:bg-stone-50 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-sm [&_th]:font-medium [&_td]:border [&_td]:border-stone-200 [&_td]:px-3 [&_td]:py-2 [&_td]:text-sm [&_hr]:my-6 [&_hr]:border-stone-200 [&_img]:rounded-lg [&_img]:my-4 [&_img]:max-w-full"
    >
      {segments.map((segment, i) => {
        if (isPageMarker(segment)) {
          return (
            <div
              key={i}
              className="my-6 flex items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-stone-400"
            >
              <span className="flex-1 border-t border-dashed border-stone-200" />
              <span className="font-mono">{segment.replace(/=+/g, '').trim()}</span>
              <span className="flex-1 border-t border-dashed border-stone-200" />
            </div>
          );
        }
        const trimmed = segment.replace(/^\n+/, '');
        if (!trimmed) return null;
        return (
          <ReactMarkdown key={i} remarkPlugins={[remarkGfm]}>
            {trimmed}
          </ReactMarkdown>
        );
      })}
    </div>
  );
};
