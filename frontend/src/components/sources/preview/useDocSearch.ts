/**
 * useDocSearch — find/highlight/jump state for the source preview modal.
 *
 * Each per-type view (markdown, plain text, PDF page, csv table) walks
 * its DOM after rendering and registers each match element via
 * `registerMatches`. The hook owns the active-match index and exposes
 * `next` / `prev` / `clear` plus a derived count.
 *
 * The hook does NOT mutate the DOM. Views are responsible for wrapping
 * matches in <mark> themselves — typically via a small recursive
 * `highlight(text)` utility that runs over rendered children. The hook
 * just tracks the registry of those <mark> elements so we can jump.
 */

import { useCallback, useMemo, useRef, useState } from 'react';

export interface DocSearchAPI {
  /** Current search term (lowercased for case-insensitive compare). */
  term: string;
  setTerm: (next: string) => void;

  /** 0-based index of the currently focused match. */
  active: number;
  count: number;

  next: () => void;
  prev: () => void;
  clear: () => void;

  /** Called by views to register the current frame's match elements. */
  registerMatches: (matches: HTMLElement[]) => void;
}

export function useDocSearch(): DocSearchAPI {
  const [term, setTermState] = useState('');
  const [active, setActive] = useState(0);
  const [count, setCount] = useState(0);
  const matchesRef = useRef<HTMLElement[]>([]);

  const setTerm = useCallback((next: string) => {
    setTermState(next);
    setActive(0);
  }, []);

  const clear = useCallback(() => {
    setTermState('');
    setActive(0);
    setCount(0);
    matchesRef.current = [];
  }, []);

  const focusActive = useCallback((idx: number) => {
    const el = matchesRef.current[idx];
    if (!el) return;
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, []);

  const next = useCallback(() => {
    setActive((cur) => {
      if (count === 0) return 0;
      const nxt = (cur + 1) % count;
      focusActive(nxt);
      return nxt;
    });
  }, [count, focusActive]);

  const prev = useCallback(() => {
    setActive((cur) => {
      if (count === 0) return 0;
      const nxt = (cur - 1 + count) % count;
      focusActive(nxt);
      return nxt;
    });
  }, [count, focusActive]);

  const registerMatches = useCallback((matches: HTMLElement[]) => {
    matchesRef.current = matches;
    setCount(matches.length);
    setActive((cur) => (matches.length === 0 ? 0 : Math.min(cur, matches.length - 1)));
  }, []);

  return useMemo(
    () => ({ term, setTerm, active, count, next, prev, clear, registerMatches }),
    [term, setTerm, active, count, next, prev, clear, registerMatches],
  );
}
