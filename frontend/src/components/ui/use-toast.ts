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
}

export const useToast = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback(
    (type: ToastType, message: string, action?: ToastAction) => {
      const id = Date.now().toString() + Math.random().toString(36).slice(2, 6);
      setToasts((prev) => [...prev, { id, type, message, action }]);
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
