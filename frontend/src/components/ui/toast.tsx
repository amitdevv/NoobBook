/**
 * Simple Toast Notification Component
 *
 * A lightweight toast notification system for showing
 * temporary messages to users. Toasts can carry an optional action
 * button (e.g. "View logs") which is admin-gated when `adminOnly` is
 * set on the action.
 */

import React, { useEffect } from 'react';
import { CheckCircle, XCircle, Info, X } from '@phosphor-icons/react';
import type { Toast } from './use-toast';
import { getAdminMode } from '@/lib/adminMode';

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ toast, onDismiss }) => {
  // Toasts with an action stay on screen longer — the user needs time to
  // notice and click. Plain toasts dismiss in 5s as before. The dismiss
  // timer resets whenever a coalesced duplicate bumps `lastBumpAt`, so a
  // burst of identical errors keeps the toast alive long enough to read.
  const dismissMs = toast.action ? 8000 : 5000;
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, dismissMs);

    return () => clearTimeout(timer);
  }, [toast.id, toast.lastBumpAt, onDismiss, dismissMs]);

  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return <CheckCircle size={20} className="text-green-500" />;
      case 'error':
        return <XCircle size={20} className="text-red-500" />;
      case 'info':
        return <Info size={20} className="text-blue-500" />;
    }
  };

  const getBgColor = () => {
    switch (toast.type) {
      case 'success':
        return 'bg-green-50 border-green-200';
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'info':
        return 'bg-blue-50 border-blue-200';
    }
  };

  // Action button visibility: hide adminOnly actions when the current
  // user isn't admin, so a "View logs" button never appears for someone
  // who can't actually see logs.
  const showAction =
    toast.action && (!toast.action.adminOnly || getAdminMode());

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg ${getBgColor()} min-w-[300px] max-w-[500px] animate-in slide-in-from-right`}
    >
      {getIcon()}
      <p className="flex-1 text-sm">
        {toast.message}
        {toast.count && toast.count > 1 && (
          <span
            aria-label={`${toast.count} times`}
            className="ml-2 inline-flex items-center justify-center rounded-full bg-stone-800/80 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white tabular-nums"
          >
            ×{toast.count}
          </span>
        )}
      </p>
      {showAction && toast.action && (
        <button
          onClick={() => {
            toast.action!.onClick();
            onDismiss(toast.id);
          }}
          className="text-xs font-medium text-stone-700 hover:text-stone-900 underline underline-offset-2 decoration-stone-400 hover:decoration-stone-700 whitespace-nowrap"
        >
          {toast.action.label}
        </button>
      )}
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-muted-foreground hover:text-foreground"
      >
        <X size={16} />
      </button>
    </div>
  );
};
