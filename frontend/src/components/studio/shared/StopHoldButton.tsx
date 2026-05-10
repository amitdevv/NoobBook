/**
 * StopHoldButton — type-"stop"-to-confirm cancellation control.
 *
 * The previous studio Stop button (PR #211) shipped as a small icon-only
 * button that swapped to red on hover. Users tapped it accidentally; even
 * after a window.confirm() was added (PR #219) muscle memory bypassed it.
 * Net: jobs disappeared silently, the PR was reverted.
 *
 * This control is structurally incompatible with accidental clicks. The
 * Stop icon opens a shadcn Dialog (NOT window.confirm) where the user
 * must type the literal word "stop" to enable the destructive action.
 * The Confirm button stays disabled until the input matches.
 *
 *   [ ◯ Stop ] → click → modal: "Type **stop** to confirm" → submit
 *
 * Editorial language for the modal copy reuses the rest of the app's
 * voice (italic font-serif headline, calm body copy reassuring the user
 * that re-running is one click). Errors during the cancel POST surface
 * as an inline pill inside the modal so the user can retry without
 * re-typing.
 */
import React, { useCallback, useState } from 'react';
import { Stop, CircleNotch, Warning } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export interface StopHoldButtonProps {
  /**
   * Fired when the user types "stop" and clicks Confirm. Should perform
   * the cancel API call. May throw or reject — the modal will surface
   * the error inline and stay open so the user can retry.
   */
  onConfirm: () => Promise<void> | void;
  /** Optional disabled state (e.g. while the parent is still booting). */
  disabled?: boolean;
  /** Tooltip / aria-label override. Default "Stop generation". */
  label?: string;
  /** Compact/full size — controls the icon button dimensions. */
  size?: 'sm' | 'md';
}

const CONFIRM_TOKEN = 'stop';

export const StopHoldButton: React.FC<StopHoldButtonProps> = ({
  onConfirm,
  disabled = false,
  label = 'Stop generation',
  size = 'md',
}) => {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset modal state on close so reopening starts fresh. Done via the
  // open-handler, NOT a useEffect — eslint flags `setState` calls inside
  // effects, and the open-handler is the only place `open` flips.
  const handleOpenChange = useCallback(
    (next: boolean) => {
      if (submitting) return; // user pressed Esc mid-cancel; ignore
      if (!next) {
        setValue('');
        setError(null);
      }
      setOpen(next);
    },
    [submitting],
  );

  const canConfirm = value.trim().toLowerCase() === CONFIRM_TOKEN && !submitting;

  const handleSubmit = useCallback(async () => {
    if (!canConfirm) return;
    setSubmitting(true);
    setError(null);
    try {
      await onConfirm();
      setOpen(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Could not cancel — try again';
      setError(message);
      setSubmitting(false);
    }
  }, [canConfirm, onConfirm]);

  const dimensions = size === 'sm' ? 'h-7 w-7' : 'h-8 w-8';
  const iconSize = size === 'sm' ? 14 : 16;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        aria-label={label}
        title={label}
        className={cn(
          'inline-flex flex-shrink-0 items-center justify-center rounded-md',
          dimensions,
          'border border-stone-200 bg-white text-stone-500',
          'transition-colors hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-1 focus-visible:ring-offset-white',
          'disabled:cursor-not-allowed disabled:opacity-40',
        )}
      >
        <Stop size={iconSize} weight="fill" />
      </button>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-serif italic text-stone-900">
              <Warning size={18} weight="fill" className="text-amber-600" />
              Cancel this generation?
            </DialogTitle>
            <DialogDescription className="text-stone-600">
              We can&apos;t recover the in-flight work. You can re-run with the
              same inputs in one click after.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-2 py-2">
            <label
              htmlFor="stop-confirm-input"
              className="text-xs font-medium text-stone-700"
            >
              Type <span className="font-mono font-semibold text-amber-700">stop</span> to confirm
            </label>
            <Input
              id="stop-confirm-input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canConfirm) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="stop"
              autoFocus
              disabled={submitting}
              className="font-mono"
              aria-invalid={!!error}
            />
            {error && (
              <p
                role="alert"
                className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-rose-200 bg-rose-50/70 px-2 py-1 text-[11px] font-medium text-rose-700"
              >
                <Warning size={11} weight="fill" />
                {error}
              </p>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={submitting}
            >
              Keep going
            </Button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={!canConfirm}
              className={cn(
                'bg-amber-600 text-white hover:bg-amber-700',
                submitting && 'cursor-wait',
              )}
            >
              {submitting ? (
                <>
                  <CircleNotch size={14} className="mr-1.5 animate-spin" />
                  Cancelling…
                </>
              ) : (
                <>
                  <Stop size={14} weight="fill" className="mr-1.5" />
                  Cancel generation
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
