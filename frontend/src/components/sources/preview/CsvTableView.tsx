/**
 * CsvTableView — fetches the raw CSV bytes via the signed URL and
 * renders them as an HTML <table> with sticky header and zebra rows.
 *
 * Uses a small hand-rolled CSV parser (handles quoted fields with
 * embedded commas, newlines, and escaped quotes) to avoid pulling in
 * papaparse (~40KB) for what's typically a preview-grade table. For
 * very large CSVs we cap rendering at MAX_ROWS and show a hint.
 */
import React, { useEffect, useRef, useState } from 'react';
import { CircleNotch } from '@phosphor-icons/react';
import type { DocSearchAPI } from './useDocSearch';

interface CsvTableViewProps {
  url: string;
  search: DocSearchAPI;
}

const MAX_ROWS = 1000;

export const CsvTableView: React.FC<CsvTableViewProps> = ({ url, search }) => {
  // Single state object so the effect only writes once per fetch
  // outcome — keeps lint's "no setState in effect body" rule happy
  // and avoids the cascading-render pattern.
  type LoadState =
    | { url: string; status: 'loading' }
    | { url: string; status: 'loaded'; rows: string[][]; truncated: boolean }
    | { url: string; status: 'error'; message: string };

  const [state, setState] = useState<LoadState>({ url, status: 'loading' });
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((text) => {
        if (cancelled) return;
        const all = parseCsv(text);
        const truncated = all.length > MAX_ROWS;
        setState({
          url,
          status: 'loaded',
          rows: truncated ? all.slice(0, MAX_ROWS) : all,
          truncated,
        });
      })
      .catch((e) => {
        if (cancelled) return;
        setState({ url, status: 'error', message: String(e) });
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  // The current `url` may be ahead of `state.url` for one render after
  // a switch — treat that frame as loading too.
  const isLoading = state.url !== url || state.status === 'loading';
  const rows = state.status === 'loaded' && state.url === url ? state.rows : null;
  const truncated = state.status === 'loaded' && state.truncated;
  const error = state.status === 'error' && state.url === url ? state.message : null;

  // Reuse the same DOM-walk highlight pattern as MarkdownView.
  useEffect(() => {
    const root = containerRef.current;
    if (!root || !rows) return;

    root.querySelectorAll('mark[data-doc-search]').forEach((m) => {
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
        mark.className = 'bg-amber-200/70 text-stone-900 rounded-sm px-0.5';
        mark.textContent = text.slice(idx, idx + term.length);
        fragment.appendChild(mark);
        matches.push(mark);
        cursor = idx + term.length;
      }
      node.parentNode?.replaceChild(fragment, node);
    });
    search.registerMatches(matches);
  }, [rows, search.term, search]);

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

  if (error) {
    return (
      <p className="text-sm text-rose-600 text-center py-8">
        Failed to load CSV: {error}
      </p>
    );
  }
  if (isLoading || !rows) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-stone-500">
        <CircleNotch size={18} className="mr-2 animate-spin" />
        Loading CSV…
      </div>
    );
  }
  if (rows.length === 0) {
    return <p className="text-sm text-stone-500 text-center py-8">CSV is empty.</p>;
  }

  const [header, ...body] = rows;

  return (
    <div ref={containerRef} className="overflow-auto rounded-md border border-stone-200">
      <table className="w-full border-collapse text-sm tabular-nums">
        <thead className="sticky top-0 bg-stone-50 backdrop-blur">
          <tr>
            {header.map((cell, i) => (
              <th
                key={i}
                className="border-b border-stone-200 px-3 py-2 text-left font-medium text-stone-700"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr
              key={ri}
              className={ri % 2 === 0 ? 'bg-white' : 'bg-stone-50/50'}
            >
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="border-b border-stone-100 px-3 py-2 text-stone-700"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {truncated && (
        <p className="px-3 py-2 text-xs text-stone-500 bg-stone-50 border-t border-stone-200">
          Preview limited to first {MAX_ROWS.toLocaleString()} rows.
        </p>
      )}
    </div>
  );
};

// RFC-4180-ish CSV parser. Handles quoted fields, embedded commas /
// newlines, and `""` escapes. Doesn't handle TSV or custom delimiters
// — preview-grade is fine for a dropped CSV; downstream chunking uses
// the dedicated CSV processor on the backend.
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let inQuotes = false;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 2;
        continue;
      }
      if (ch === '"') {
        inQuotes = false;
        i++;
        continue;
      }
      field += ch;
      i++;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i++;
      continue;
    }
    if (ch === ',') {
      row.push(field);
      field = '';
      i++;
      continue;
    }
    if (ch === '\n' || ch === '\r') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      // Swallow CRLF as one separator.
      if (ch === '\r' && text[i + 1] === '\n') i += 2;
      else i++;
      continue;
    }
    field += ch;
    i++;
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}
