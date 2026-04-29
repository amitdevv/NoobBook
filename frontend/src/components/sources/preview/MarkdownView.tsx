/**
 * MarkdownView — renders extracted text (or pasted markdown) with
 * react-markdown. Three concerns layered on top of plain rendering:
 *
 *   1. Page markers (`=== TYPE PAGE N of M ===`) become styled section
 *      dividers instead of leaking into the prose as text.
 *   2. Fenced code blocks render via CodeBlock — syntax-highlighted +
 *      copy-to-clipboard button.
 *   3. After every render we walk the DOM and wrap matches of
 *      `search.term` in `<mark>` elements. Code blocks are excluded.
 *
 *   4. Headings emit `data-heading-id` attributes (slugified text) so
 *      the TOC sidebar can scroll-into-view-on-click without us
 *      maintaining a parallel data structure.
 *
 * Used by:
 *   - TEXT  (pasted notes — markdown round-tripped through the editor)
 *   - DOCX, PPTX, LINK, YOUTUBE, RESEARCH (extracted plain text;
 *     markdown-as-text is a graceful superset)
 */
import React, { useEffect, useMemo, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { DocSearchAPI } from './useDocSearch';
import { CodeBlock } from './CodeBlock';

interface MarkdownViewProps {
  content: string;
  search: DocSearchAPI;
  /** Optional callback fired with the headings collected during
   *  render. Parent uses this to populate a TOC sidebar. */
  onHeadings?: (headings: HeadingEntry[]) => void;
}

export interface HeadingEntry {
  id: string;
  text: string;
  /** 1 for h1, 2 for h2, ... */
  level: number;
}

const PAGE_MARKER_PATTERN = '(===\\s*\\w+\\s*PAGE\\s*\\d+\\s*of\\s*\\d+\\s*===)';
function isPageMarker(segment: string): boolean {
  return new RegExp(PAGE_MARKER_PATTERN, 'i').test(segment);
}

// Callout palette per GitHub-flavored convention.
const CALLOUT_PALETTE: Record<
  'NOTE' | 'WARNING' | 'TIP' | 'IMPORTANT' | 'CAUTION',
  { border: string; bg: string; label: string; text: string }
> = {
  NOTE:      { border: 'border-sky-200',    bg: 'bg-sky-50/70',    label: 'text-sky-700',    text: 'text-stone-700' },
  TIP:       { border: 'border-emerald-200',bg: 'bg-emerald-50/70',label: 'text-emerald-700',text: 'text-stone-700' },
  IMPORTANT: { border: 'border-violet-200', bg: 'bg-violet-50/70', label: 'text-violet-700', text: 'text-stone-700' },
  WARNING:   { border: 'border-amber-300',  bg: 'bg-amber-50/70',  label: 'text-amber-800',  text: 'text-stone-800' },
  CAUTION:   { border: 'border-rose-200',   bg: 'bg-rose-50/70',   label: 'text-rose-700',   text: 'text-stone-800' },
};

// Drop the leading `[!XYZ]` token from a react-markdown blockquote's
// children tree. The marker always lives at the start of the first
// text node of the first paragraph child.
function stripCalloutMarker(children: React.ReactNode): React.ReactNode {
  const arr = React.Children.toArray(children);
  if (arr.length === 0) return children;
  const first = arr[0];
  if (!React.isValidElement(first)) return children;
  const firstProps = first.props as { children?: React.ReactNode };
  const innerArr = React.Children.toArray(firstProps.children);
  if (innerArr.length === 0) return children;
  const head = innerArr[0];
  if (typeof head !== 'string') return children;
  const stripped = head.replace(/^\s*\[!(NOTE|WARNING|TIP|IMPORTANT|CAUTION)\]\s*/i, '');
  if (stripped === head) return children;
  const rebuilt = React.cloneElement(first, undefined, [stripped, ...innerArr.slice(1)]);
  return [rebuilt, ...arr.slice(1)];
}

// Module-scope component overrides for react-markdown. Defining them
// once here gives react-markdown stable component identity across
// renders — recreating the components-map inside the parent forces a
// remount of every rendered element on every parent render, which
// among other things wipes any DOM mutations our search-highlight
// effect just made.
//
// Heading ids + data-heading-id are assigned post-render by an effect
// inside MarkdownView (we can't access the local headings array from
// here, so the effect walks the rendered DOM in document order).

const Heading1 = ({ children }: { children?: React.ReactNode }) => (
  <h1 className="text-[26px] font-semibold mt-8 mb-3 text-stone-900 scroll-mt-24">{children}</h1>
);
const Heading2 = ({ children }: { children?: React.ReactNode }) => (
  <h2 className="text-[21px] font-semibold mt-7 mb-2 text-stone-900 scroll-mt-24">{children}</h2>
);
const Heading3 = ({ children }: { children?: React.ReactNode }) => (
  <h3 className="text-[18px] font-medium mt-5 mb-2 text-stone-900 scroll-mt-24">{children}</h3>
);
const Heading4 = ({ children }: { children?: React.ReactNode }) => (
  <h4 className="text-[16px] font-medium mt-4 mb-2 text-stone-900 scroll-mt-24">{children}</h4>
);
const Heading5 = ({ children }: { children?: React.ReactNode }) => (
  <h5 className="text-[15px] font-medium mt-4 mb-2 text-stone-900 scroll-mt-24">{children}</h5>
);
const Heading6 = ({ children }: { children?: React.ReactNode }) => (
  <h6 className="text-[14px] font-medium mt-4 mb-2 text-stone-700 scroll-mt-24">{children}</h6>
);

const Paragraph = ({ children }: { children?: React.ReactNode }) => (
  <p className="my-3">{children}</p>
);
const UnorderedList = ({ children }: { children?: React.ReactNode }) => (
  <ul className="my-3 pl-6 list-disc">{children}</ul>
);
const OrderedList = ({ children }: { children?: React.ReactNode }) => (
  <ol className="my-3 pl-6 list-decimal">{children}</ol>
);
const ListItem = ({ children }: { children?: React.ReactNode }) => (
  <li className="my-1">{children}</li>
);
const Anchor = ({ children, href }: { children?: React.ReactNode; href?: string }) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="text-amber-700 underline underline-offset-2 hover:text-amber-800"
  >
    {children}
  </a>
);
const Hr = () => <hr className="my-6 border-stone-200" />;
const Img = ({ src, alt }: { src?: string; alt?: string }) => (
  <img src={src} alt={alt ?? ''} className="rounded-lg my-4 max-w-full" />
);
const Tbl = ({ children }: { children?: React.ReactNode }) => (
  <table className="my-4 w-full border-collapse">{children}</table>
);
const Th = ({ children }: { children?: React.ReactNode }) => (
  <th className="border border-stone-200 bg-stone-50 px-3 py-2 text-left text-sm font-medium">
    {children}
  </th>
);
const Td = ({ children }: { children?: React.ReactNode }) => (
  <td className="border border-stone-200 px-3 py-2 text-sm">{children}</td>
);

const Blockquote = ({ children }: { children?: React.ReactNode }) => {
  // GitHub-flavored callout convention: a blockquote whose first
  // line is `[!NOTE]` (or WARNING / TIP / IMPORTANT / CAUTION)
  // renders as a colored panel. Otherwise it's a plain styled
  // blockquote.
  const text = childrenToText(children);
  const m = text.match(/^\[!(NOTE|WARNING|TIP|IMPORTANT|CAUTION)\]\s*/i);
  if (!m) {
    return (
      <blockquote className="my-4 pl-4 border-l-2 border-amber-300 text-stone-600 italic">
        {children}
      </blockquote>
    );
  }
  const variant = m[1].toUpperCase() as
    | 'NOTE' | 'WARNING' | 'TIP' | 'IMPORTANT' | 'CAUTION';
  const palette = CALLOUT_PALETTE[variant];
  return (
    <div
      className={`my-4 rounded-lg border ${palette.border} ${palette.bg} px-4 py-3 not-italic`}
    >
      <p className={`text-[11px] font-mono uppercase tracking-[0.18em] ${palette.label} mb-1`}>
        {variant}
      </p>
      <div className={`text-[15px] leading-relaxed ${palette.text} [&>p]:my-1`}>
        {stripCalloutMarker(children)}
      </div>
    </div>
  );
};

// Inline code is compact + warm; block code is delegated to
// CodeBlock via the `pre` override below.
const InlineCode: React.FC<React.HTMLAttributes<HTMLElement>> = ({
  className,
  children,
  ...props
}) => {
  // react-markdown wraps fenced code in a <pre><code>; for inline
  // there is no `pre` parent, so the `pre` override doesn't
  // intercept those — we handle them here. Fenced blocks have a
  // className like `language-ts`; treat presence of that as the
  // signal they're block code (and pass through unchanged for the
  // <pre> override to grab).
  const isBlock = typeof className === 'string' && className.startsWith('language-');
  if (isBlock) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  }
  return (
    <code className="bg-stone-100 text-stone-800 rounded px-1 py-0.5 text-[0.85em] font-mono">
      {children}
    </code>
  );
};

const PreBlock = ({ children }: { children?: React.ReactNode }) => {
  // children is the inner <code>; pull language + text out of it.
  // react-markdown gives us a single child.
  let language: string | null = null;
  let codeText = '';
  if (React.isValidElement(children)) {
    const props = children.props as { className?: string; children?: React.ReactNode };
    const cls = props.className ?? '';
    const m = cls.match(/language-([\w-]+)/);
    if (m) language = m[1].toLowerCase();
    codeText = childrenToText(props.children);
  }
  return <CodeBlock language={language} code={codeText.replace(/\n$/, '')} />;
};

// Single, frozen components map. Stable identity is what
// react-markdown needs to avoid remounting every node on each render.
const MD_COMPONENTS = {
  h1: Heading1,
  h2: Heading2,
  h3: Heading3,
  h4: Heading4,
  h5: Heading5,
  h6: Heading6,
  p: Paragraph,
  ul: UnorderedList,
  ol: OrderedList,
  li: ListItem,
  a: Anchor,
  blockquote: Blockquote,
  hr: Hr,
  img: Img,
  table: Tbl,
  th: Th,
  td: Td,
  code: InlineCode,
  pre: PreBlock,
} as const;

// Slug stable enough across renders for the TOC scroll target.
function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .slice(0, 80);
}

// Pull a leaf string out of react-markdown's children prop. Headings
// in our content rarely contain inline formatting, but we walk the
// children array defensively to handle the case.
function childrenToText(children: React.ReactNode): string {
  if (typeof children === 'string') return children;
  if (Array.isArray(children)) return children.map(childrenToText).join('');
  if (React.isValidElement(children)) {
    return childrenToText(
      (children.props as { children?: React.ReactNode })?.children,
    );
  }
  return '';
}

export const MarkdownView: React.FC<MarkdownViewProps> = ({
  content,
  search,
  onHeadings,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  const segments = content.split(new RegExp(PAGE_MARKER_PATTERN, 'gi'));

  // Heading collection runs once per content change. Slugs are
  // de-duplicated with a counter suffix so two `## Wins` sections
  // don't both jump to the same anchor.
  const headings = useMemo<HeadingEntry[]>(() => {
    const out: HeadingEntry[] = [];
    const seen = new Map<string, number>();
    const re = /^(#{1,6})\s+(.+?)\s*$/gm;
    let match: RegExpExecArray | null;
    while ((match = re.exec(content)) !== null) {
      const level = match[1].length;
      const text = match[2].trim();
      const baseSlug = slugify(text) || `h${level}`;
      const count = (seen.get(baseSlug) ?? 0) + 1;
      seen.set(baseSlug, count);
      const id = count === 1 ? baseSlug : `${baseSlug}-${count}`;
      out.push({ id, text, level });
    }
    return out;
  }, [content]);

  useEffect(() => {
    onHeadings?.(headings);
  }, [headings, onHeadings]);

  // Heading id assignment runs as a post-render effect rather than
  // inline during render. ReactMarkdown's heading components don't
  // receive enough context to disambiguate duplicate-text headings,
  // and any in-render counter trips the immutability lint. Walking
  // the DOM in document order and applying ids matches the parser's
  // own ordering for free.
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const els = root.querySelectorAll<HTMLElement>('h1, h2, h3, h4, h5, h6');
    els.forEach((el, i) => {
      const entry = headings[i];
      if (!entry) return;
      el.id = entry.id;
      el.dataset.headingId = entry.id;
    });
  }, [headings, content]);

  // ---- search highlight pass (unchanged from prior version) ----
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;

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

  // Heading wrapper shared across h1-h6 — assigns the slug id and
  // applies the typography styles inline.
  // Heading typography classes are inlined in HeadingComponents above
  // (module scope) so react-markdown gets a stable component ref per
  // heading level — recreating the map every render forces a remount
  // of every heading element on each MarkdownView render.

  return (
    <div
      ref={containerRef}
      className="font-serif text-[16px] leading-[1.75] text-stone-800 selection:bg-amber-200/60"
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
          <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {trimmed}
          </ReactMarkdown>
        );
      })}
    </div>
  );
};
