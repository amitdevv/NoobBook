/**
 * TocSidebar — sticky table-of-contents shown alongside MarkdownView
 * for long text-based sources.
 *
 * Renders the heading list passed up from MarkdownView, indented by
 * level. Click-to-jump uses the heading's slugified id (set by
 * MarkdownView via `data-heading-id`). An IntersectionObserver tracks
 * which heading is currently the "active" one — the one closest to
 * the top of the scroll container — so the active row gets an amber
 * left-border tick.
 *
 * Hidden when the source has fewer than 3 headings. A 1-heading TOC
 * is just chrome with no value.
 */
import React, { useEffect, useRef, useState } from 'react';
import type { HeadingEntry } from './MarkdownView';

interface TocSidebarProps {
  headings: HeadingEntry[];
  /** Scroll container the headings live inside — used to compute
   *  IntersectionObserver root. Pass the ScrollArea viewport's
   *  internal scroll element. */
  scrollRoot: HTMLElement | null;
}

const LEVEL_INDENT: Record<number, string> = {
  1: 'pl-0',
  2: 'pl-3',
  3: 'pl-6',
  4: 'pl-9',
  5: 'pl-12',
  6: 'pl-12',
};

export const TocSidebar: React.FC<TocSidebarProps> = ({ headings, scrollRoot }) => {
  const [activeId, setActiveId] = useState<string | null>(null);
  // The root the IntersectionObserver watches against. We can't use
  // the document viewport because the preview sheet has its own
  // scroll container.
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (!scrollRoot || headings.length === 0) return;

    const targets: HTMLElement[] = [];
    headings.forEach((h) => {
      const el = scrollRoot.querySelector<HTMLElement>(`[data-heading-id="${h.id}"]`);
      if (el) targets.push(el);
    });
    if (targets.length === 0) return;

    // Prefer the heading whose top crosses the band 0–35% of the
    // scroll viewport. Anything entering that band wins. Falls back
    // to whichever one was last visible.
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) {
          const id = (visible[0].target as HTMLElement).dataset.headingId;
          if (id) setActiveId(id);
        }
      },
      {
        root: scrollRoot,
        rootMargin: '0px 0px -65% 0px',
        threshold: [0, 1],
      },
    );
    targets.forEach((t) => observerRef.current?.observe(t));

    return () => {
      observerRef.current?.disconnect();
      observerRef.current = null;
    };
  }, [headings, scrollRoot]);

  // Don't render TOC for trivially-short docs.
  if (headings.length < 3) return null;

  const handleClick = (id: string) => {
    if (!scrollRoot) return;
    const target = scrollRoot.querySelector<HTMLElement>(`[data-heading-id="${id}"]`);
    if (!target) return;
    target.scrollIntoView({ block: 'start', behavior: 'smooth' });
    // Optimistically set active so the click lands feeling responsive
    // even before the observer catches up.
    setActiveId(id);
  };

  return (
    <aside className="hidden lg:block w-56 flex-shrink-0 border-l border-stone-200/70 bg-stone-50/40">
      <div className="sticky top-0 px-4 py-5 max-h-[calc(100vh-200px)] overflow-y-auto">
        <p className="text-[10px] uppercase tracking-[0.2em] text-stone-400 mb-3 font-mono">
          On this page
        </p>
        <ul className="space-y-1">
          {headings.map((h) => {
            const active = h.id === activeId;
            return (
              <li key={h.id}>
                <button
                  type="button"
                  onClick={() => handleClick(h.id)}
                  className={
                    LEVEL_INDENT[h.level] +
                    ' w-full text-left text-[12px] leading-snug py-1 border-l-2 transition ' +
                    (active
                      ? 'border-amber-500 text-amber-800 font-medium'
                      : 'border-transparent text-stone-500 hover:text-stone-800 hover:border-stone-300')
                  }
                >
                  {h.text}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
};
