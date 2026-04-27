import React, { useState } from 'react';
import { Share } from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { SharingModal } from './SharingModal';

/**
 * ShareButton
 *
 * Quiet, refined trigger for the project-share modal. Lives in the
 * project header next to Memory / Settings / New Project — same visual
 * weight as those, slightly warmer accent on hover.
 */
interface ShareButtonProps {
  projectId: string;
  projectName: string;
}

export const ShareButton: React.FC<ShareButtonProps> = ({ projectId, projectName }) => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="soft"
        size="sm"
        onClick={() => setOpen(true)}
        className="gap-2"
        aria-haspopup="dialog"
      >
        <Share size={16} />
        Share
      </Button>
      <SharingModal
        open={open}
        onOpenChange={setOpen}
        projectId={projectId}
        projectName={projectName}
      />
    </>
  );
};
