import React, { useState } from 'react';
import { Bug } from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { LogsModal } from './LogsModal';

/**
 * LogsButton
 *
 * Admin-only header trigger that opens the diagnostic logs modal. Caller
 * is responsible for the `isAdmin` gate — this component renders the
 * button unconditionally so it can be reused from settings too.
 */
export const LogsButton: React.FC = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="soft"
        size="sm"
        onClick={() => setOpen(true)}
        className="gap-2"
        aria-haspopup="dialog"
        title="View diagnostic logs"
      >
        <Bug size={16} />
        Logs
      </Button>
      <LogsModal open={open} onOpenChange={setOpen} />
    </>
  );
};
