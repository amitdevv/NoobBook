/**
 * StudioSignalPicker Component
 *
 * Modal for picking which signal (= user-supplied "direction" prompt) to feed
 * into a studio generator when more than one exists for the same item. Shared
 * across every studio generation — title and icon come from the parent via
 * getItemTitle / getItemIcon.
 *
 * Design intent:
 * - Numbered chip on every row so the picker reads as "choose option N".
 * - The direction text gets full vertical room (3-line clamp at the line
 *   boundary, never mid-word) instead of being cut off in a single line.
 * - Source count rendered as a labelled pill — easier to scan than a bare
 *   "N sources" run of muted text.
 * - Per-row primary CTA + keyboard shortcut (1–9). The whole row is still
 *   clickable; the visible button removes the "is this clickable" ambiguity.
 */

import React, { useEffect, useRef } from 'react';
import { ArrowRight, FileText } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { cn } from '@/lib/utils';
import type { StudioSignal, StudioItemId } from './types';

interface StudioSignalPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedItem: StudioItemId | null;
  selectedSignals: StudioSignal[];
  onSelectSignal: (itemId: StudioItemId, signal: StudioSignal) => void;
  getItemTitle: (itemId: StudioItemId) => string;
  getItemIcon: (itemId: StudioItemId) => React.ComponentType<{ size?: number; className?: string }> | undefined;
}

export const StudioSignalPicker: React.FC<StudioSignalPickerProps> = ({
  open,
  onOpenChange,
  selectedItem,
  selectedSignals,
  onSelectSignal,
  getItemTitle,
  getItemIcon,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Keyboard shortcuts: 1–9 picks the Nth option. Radix already handles Esc.
  // Arrow keys move focus between rows; the row buttons themselves handle Enter.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      // Ignore when the user is typing somewhere inside the dialog.
      const target = e.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return;

      const numberKey = Number(e.key);
      if (!Number.isNaN(numberKey) && numberKey >= 1 && numberKey <= 9) {
        const signal = selectedSignals[numberKey - 1];
        if (signal && selectedItem) {
          e.preventDefault();
          onSelectSignal(selectedItem, signal);
        }
        return;
      }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const rows = containerRef.current?.querySelectorAll<HTMLButtonElement>(
          '[data-signal-row]'
        );
        if (!rows || rows.length === 0) return;
        e.preventDefault();
        const current = Array.from(rows).findIndex((el) => el === document.activeElement);
        const delta = e.key === 'ArrowDown' ? 1 : -1;
        const next = current === -1
          ? (delta === 1 ? 0 : rows.length - 1)
          : (current + delta + rows.length) % rows.length;
        rows[next].focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, selectedItem, selectedSignals, onSelectSignal]);

  const itemIcon = selectedItem ? getItemIcon(selectedItem) : undefined;
  const itemTitle = selectedItem ? getItemTitle(selectedItem) : '';
  const count = selectedSignals.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-5 pt-5 pb-4 border-b space-y-3">
          <DialogTitle className="flex items-center gap-2.5 text-base font-semibold">
            {itemIcon && (
              <span className="inline-flex w-7 h-7 items-center justify-center rounded-md bg-amber-50 text-primary">
                {React.createElement(itemIcon, { size: 16 })}
              </span>
            )}
            <span>Generate {itemTitle}</span>
          </DialogTitle>
          <DialogDescription className="flex items-center gap-2 text-[13px] text-muted-foreground">
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-md border border-amber-200 bg-amber-50 text-primary font-mono text-[11px] font-medium">
              {count}
            </span>
            <span>
              You wrote <span className="font-semibold text-foreground">{count} topics</span> for this. Pick which one to generate.
            </span>
          </DialogDescription>
        </DialogHeader>

        {/* Topic list */}
        <div
          ref={containerRef}
          className="px-3 py-3 max-h-[60vh] overflow-y-auto flex flex-col gap-2"
          role="listbox"
          aria-label="Available topics"
        >
          {selectedSignals.map((signal, idx) => {
            const sourceCount = signal.sources?.length ?? 0;
            const positionLabel = idx + 1;
            return (
              <button
                key={signal.id}
                data-signal-row
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => selectedItem && onSelectSignal(selectedItem, signal)}
                className={cn(
                  'group w-full text-left',
                  'grid grid-cols-[28px_1fr_auto] gap-3 items-start',
                  'p-3 rounded-md border border-border bg-card',
                  'transition-all duration-150',
                  'hover:border-primary hover:bg-amber-50/50',
                  'focus:outline-none focus-visible:border-primary focus-visible:bg-amber-50/50 focus-visible:ring-2 focus-visible:ring-primary/15'
                )}
              >
                {/* Numbered chip — instantly says "this is option N" */}
                <span
                  aria-hidden="true"
                  className={cn(
                    'row-span-2 w-7 h-7 mt-0.5 inline-flex items-center justify-center',
                    'rounded-md border bg-muted/40 border-border',
                    'font-mono text-[12px] font-medium text-muted-foreground',
                    'transition-colors',
                    'group-hover:bg-white group-hover:border-primary group-hover:text-primary',
                    'group-focus-visible:bg-white group-focus-visible:border-primary group-focus-visible:text-primary'
                  )}
                >
                  {positionLabel}
                </span>

                {/* Body: direction text + source pill */}
                <div className="min-w-0">
                  <p
                    className={cn(
                      'text-sm font-medium leading-snug text-foreground',
                      // Clamp to 3 lines, wrap at word boundaries.
                      'line-clamp-3 break-words [overflow-wrap:anywhere]'
                    )}
                  >
                    {signal.direction || (
                      <span className="text-muted-foreground italic">
                        No direction provided — let NoobBook pick the angle.
                      </span>
                    )}
                  </p>

                  <div className="mt-2.5 flex items-center gap-2 flex-wrap">
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 pl-1.5 pr-2 py-0.5',
                        'rounded-full border border-border bg-muted/30',
                        'text-[11.5px] text-muted-foreground'
                      )}
                    >
                      <FileText size={12} weight="duotone" className="text-muted-foreground/70" />
                      {sourceCount} {sourceCount === 1 ? 'source' : 'sources'}
                    </span>
                  </div>
                </div>

                {/* Primary action — always visible, fills on hover/focus */}
                <span
                  className={cn(
                    'row-span-2 self-center',
                    'inline-flex items-center gap-1.5 px-3 py-1.5',
                    'rounded-md border border-border bg-card',
                    'text-[12.5px] font-medium text-foreground whitespace-nowrap',
                    'transition-colors',
                    'group-hover:bg-primary group-hover:border-primary group-hover:text-primary-foreground',
                    'group-focus-visible:bg-primary group-focus-visible:border-primary group-focus-visible:text-primary-foreground'
                  )}
                >
                  Generate
                  <ArrowRight
                    size={14}
                    className="transition-transform duration-200 group-hover:translate-x-0.5 group-focus-visible:translate-x-0.5"
                  />
                  {positionLabel <= 9 && (
                    <kbd
                      aria-hidden="true"
                      className={cn(
                        'ml-0.5 inline-flex items-center justify-center min-w-[16px] h-4 px-1',
                        'rounded border border-border border-b-2 bg-background',
                        'font-mono text-[10px] text-muted-foreground leading-none',
                        'group-hover:border-white/30 group-hover:bg-white/15 group-hover:text-primary-foreground',
                        'group-focus-visible:border-white/30 group-focus-visible:bg-white/15 group-focus-visible:text-primary-foreground'
                      )}
                    >
                      {positionLabel}
                    </kbd>
                  )}
                </span>
              </button>
            );
          })}
        </div>

        {/* Footer with keyboard hints */}
        <div className="flex items-center justify-between gap-3 px-5 py-3 border-t bg-muted/30 text-[11.5px] text-muted-foreground font-mono">
          <span className="inline-flex items-center gap-1.5">
            <FooterKbd>↑</FooterKbd>
            <FooterKbd>↓</FooterKbd>
            <span className="ml-1">navigate</span>
            <span className="mx-2 text-border">·</span>
            <FooterKbd>1</FooterKbd>
            <span className="ml-1">…</span>
            <FooterKbd>{Math.min(count, 9)}</FooterKbd>
            <span className="ml-1">pick</span>
            <span className="mx-2 text-border">·</span>
            <FooterKbd>Esc</FooterKbd>
            <span className="ml-1">close</span>
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
};

const FooterKbd: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <kbd className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded border border-border border-b-2 bg-background text-muted-foreground leading-none">
    {children}
  </kbd>
);
