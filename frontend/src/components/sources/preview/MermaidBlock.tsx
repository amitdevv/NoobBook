/**
 * MermaidBlock — renders a fenced ```mermaid``` code block as the
 * actual diagram inside the markdown preview.
 *
 * Mermaid is already initialized at module load by FlowDiagramViewer
 * for the studio, so we just call `mermaid.render(id, source)` here.
 * Each block gets a unique render id so simultaneous diagrams don't
 * clash. Errors render the raw source verbatim with a small notice.
 */
import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { createLogger } from '@/lib/logger';

const log = createLogger('mermaid-block');

let nextId = 0;
function makeId() {
  nextId += 1;
  return `mermaid-preview-${nextId}-${Math.random().toString(36).slice(2, 8)}`;
}

interface MermaidBlockProps {
  source: string;
}

export const MermaidBlock: React.FC<MermaidBlockProps> = ({ source }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const id = makeId();
    (async () => {
      try {
        const { svg } = await mermaid.render(id, source);
        if (cancelled) return;
        if (containerRef.current) containerRef.current.innerHTML = svg;
        // Clear any prior error from the previous source. This sits
        // inside the async callback (not the effect body) so it
        // doesn't trip the no-setState-in-effect lint.
        setError(null);
      } catch (e) {
        if (cancelled) return;
        log.warn({ err: e }, 'mermaid render failed');
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [source]);

  if (error) {
    return (
      <div className="my-4 rounded-lg border border-rose-200 bg-rose-50/60 p-3">
        <p className="text-[11px] font-mono uppercase tracking-[0.15em] text-rose-700 mb-2">
          Mermaid render error
        </p>
        <pre className="text-xs text-stone-700 whitespace-pre-wrap font-mono">{source}</pre>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="my-4 rounded-lg border border-stone-200 bg-white p-4 overflow-x-auto [&>svg]:max-w-full [&>svg]:h-auto"
    />
  );
};
