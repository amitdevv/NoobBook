/**
 * GlobalLogsModalGate
 *
 * Mounts a single LogsModal instance at the App root that opens in
 * response to the `noobbook:open-logs` window event. Lets any toast
 * (or other deeply-nested component) request the logs view without
 * having to plumb open-state down through props or context.
 *
 * Only renders for admins — non-admin users dispatching the event get
 * no-op behavior, which is the correct fallback since the underlying
 * /logs/* endpoints are admin-gated server-side anyway.
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
    if (!isAdmin) return;
    const handler = () => setOpen(true);
    window.addEventListener(LOGS_OPEN_EVENT, handler);
    return () => window.removeEventListener(LOGS_OPEN_EVENT, handler);
  }, [isAdmin]);

  if (!isAdmin) return null;
  return <LogsModal open={open} onOpenChange={setOpen} />;
};
