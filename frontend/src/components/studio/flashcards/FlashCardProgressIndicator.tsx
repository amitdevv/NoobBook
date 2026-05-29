/**
 * FlashCardProgressIndicator Component
 * Shows real-time progress during flash card generation.
 * Purple theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { FlashCardJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface FlashCardProgressIndicatorProps {
  currentFlashCardJob: FlashCardJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const FlashCardProgressIndicator: React.FC<FlashCardProgressIndicatorProps> = ({
  currentFlashCardJob,
  projectId,
}) => {
  if (!currentFlashCardJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentFlashCardJob?.id) return;
    await cancelStudioJob(projectId, currentFlashCardJob.id);
  };

  return (
    <div className="p-2 bg-purple-500/5 rounded-md border border-purple-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-purple-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentFlashCardJob.source_name || 'Generating flash cards...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentFlashCardJob.progress || 'Starting...'}
          </p>
        </div>
        {projectId && currentFlashCardJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
