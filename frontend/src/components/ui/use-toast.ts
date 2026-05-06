import { useCallback, useState } from 'react';
import { getAdminMode, openLogsModal } from '@/lib/adminMode';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastAction {
  label: string;
  onClick: () => void;
  /** When true, the action is hidden for non-admins. Used by `errorWithLogs`
   * so a "View logs" affordance never leaks past the role gate. */
  adminOnly?: boolean;
}

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  action?: ToastAction;
  /**
   * When duplicate toasts arrive in quick succession, we collapse them into
   * a single row and show this count instead of stacking. `undefined` and
   * `1` render the same — only `>= 2` is shown as a badge.
   */
  count?: number;
  /** Tracks the last time this toast was bumped, for coalescence windowing. */
  lastBumpAt?: number;
}

// Toasts emitted within this window with the same (type, message) collapse
// into a single entry with an incremented `count` instead of stacking.
// Sub-1s on purpose: any later duplicate is treated as a fresh event because
// the user may not have seen the original.
const COALESCE_WINDOW_MS = 1500;

export const useToast = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback(
    (type: ToastType, message: string, action?: ToastAction) => {
      const now = Date.now();
      setToasts((prev) => {
        // Coalesce duplicates: if an identical toast was just shown, bump
        // its count + reset its dismiss timer instead of stacking a new
        // row. Toasts with an action don't coalesce — the user might
        // have already clicked the previous one.
        if (!action) {
          const lastIdx = prev.length - 1;
          for (let i = lastIdx; i >= 0; i--) {
            const t = prev[i];
            if (
              t.type === type &&
              t.message === message &&
              !t.action &&
              now - (t.lastBumpAt ?? 0) <= COALESCE_WINDOW_MS
            ) {
              const nextCount = (t.count ?? 1) + 1;
              const updated: Toast = { ...t, count: nextCount, lastBumpAt: now };
              return [...prev.slice(0, i), ...prev.slice(i + 1), updated];
            }
          }
        }
        const id = now.toString() + Math.random().toString(36).slice(2, 6);
        return [...prev, { id, type, message, action, lastBumpAt: now }];
      });
    },
    [],
  );

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const success = useCallback((message: string) => showToast('success', message), [showToast]);
  const error = useCallback((message: string) => showToast('error', message), [showToast]);
  const info = useCallback((message: string) => showToast('info', message), [showToast]);

  /**
   * Like `error()`, but appends a "View logs" button on the toast that
   * opens the diagnostic-logs modal directly. Use this for failures that
   * actually represent backend breakage (network errors, 500s, "failed
   * to load …") — *not* for input validation, missing-config prompts,
   * or "permission denied" messages where logs won't help.
   *
   * The action is admin-only at render time, so non-admins see the same
   * plain error toast as if `error()` had been called.
   */
  const errorWithLogs = useCallback(
    (message: string) =>
      showToast('error', message, {
        label: 'View logs',
        onClick: openLogsModal,
        adminOnly: true,
      }),
    [showToast],
  );

  return {
    toasts,
    showToast,
    dismissToast,
    success,
    error,
    errorWithLogs,
    info,
  };
};

// Re-export for convenience so call sites that already do `import { useToast }`
// can also `import { getAdminMode }` from the same place if needed for
// custom action gating.
export { getAdminMode };
