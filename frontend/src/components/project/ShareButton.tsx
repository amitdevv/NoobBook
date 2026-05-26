import React, { useState } from 'react';
import { Share } from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { SharingModal } from './SharingModal';

/**
 * ShareButton
 *
 * Quiet, refined trigger for the share modal. Used in two places:
 *   • Project header — no chat props → modal manages project-wide
 *     shares (every chat visible to viewers).
 *   • Chat header — chatId + chatTitle passed → modal flips to
 *     chat-scope mode and only manages shares for that one chat.
 *
 * Visual variants:
 *   • variant='soft' (default) — full button with label, used in
 *     ProjectHeader.
 *   • variant='ghost-icon' — icon-only ghost, used in ChatHeader so
 *     it sits unobtrusively next to Export PDF.
 */
interface ShareButtonProps {
  projectId: string;
  projectName: string;
  chatId?: string;
  chatTitle?: string;
  variant?: 'soft' | 'ghost-icon';
  disabled?: boolean;
}

export const ShareButton: React.FC<ShareButtonProps> = ({
  projectId,
  projectName,
  chatId,
  chatTitle,
  variant = 'soft',
  disabled = false,
}) => {
  const [open, setOpen] = useState(false);
  return (
    <>
      {variant === 'ghost-icon' ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen(true)}
          disabled={disabled}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
          aria-haspopup="dialog"
          aria-label="Share this chat"
        >
          <Share size={16} weight="bold" />
        </Button>
      ) : (
        <Button
          variant="soft"
          size="sm"
          onClick={() => setOpen(true)}
          disabled={disabled}
          className="gap-2"
          aria-haspopup="dialog"
        >
          <Share size={16} />
          Share project
        </Button>
      )}
      <SharingModal
        open={open}
        onOpenChange={setOpen}
        projectId={projectId}
        projectName={projectName}
        chatId={chatId}
        chatTitle={chatTitle}
      />
    </>
  );
};
