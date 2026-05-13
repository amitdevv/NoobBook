/**
 * GlobalLogsModalGate
 *
 * Mounts a single LogsModal instance at the App root that opens in
 * response to the `noobbook:open-logs` window event. Lets any toast
 * (or other deeply-nested component) request the logs view without
 * having to plumb open-state down through props or context.
 *
 * All authenticated users can view and download logs. The Clear action
 * is admin-only and is hidden in the modal for non-admin users (the
 * server also enforces this via @require_admin on POST /logs/clear).
 */
import React, { useEffect, useState } from 'react';
import { LogsModal } from './LogsModal';
import { LOGS_OPEN_EVENT } from '@/lib/adminMode';

interface GlobalLogsModalGateProps {
  isAdmin: boolean;
}

export const GlobalLogsModalGate: React.FC<GlobalLogsModalGateProps> = ({ isAdmin }) => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener(LOGS_OPEN_EVENT, handler);
    return () => window.removeEventListener(LOGS_OPEN_EVENT, handler);
  }, []);

  return <LogsModal open={open} onOpenChange={setOpen} canClear={isAdmin} />;
};
