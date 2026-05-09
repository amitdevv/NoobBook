/**
 * PresentationProgressIndicator Component
 * Educational Note: Shows real-time progress during presentation generation.
 * Amber theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { PresentationJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface PresentationProgressIndicatorProps {
  currentPresentationJob: PresentationJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const PresentationProgressIndicator: React.FC<PresentationProgressIndicatorProps> = ({
  currentPresentationJob,
  projectId,
}) => {
  if (!currentPresentationJob) return null;

  // Show slide creation progress if available
  const progressText = currentPresentationJob.slides_created > 0
    ? `${currentPresentationJob.slides_created}/${currentPresentationJob.total_slides || '?'} slides`
    : currentPresentationJob.status_message || 'Starting...';

  const handleCancel = async () => {
    if (!projectId || !currentPresentationJob?.id) return;
    await cancelStudioJob(projectId, currentPresentationJob.id);
  };

  return (
    <div className="p-2 bg-amber-500/5 rounded-md border border-amber-500/20">
      <div className="flex items-center gap-2">
        <SpinnerGap className="animate-spin text-amber-500" size={16} />
        <div className="flex-1">
          <p className="text-xs text-amber-700 font-medium">
            {currentPresentationJob.presentation_title || 'Generating presentation...'}
          </p>
          <p className="text-xs text-amber-600">
            {progressText}
          </p>
        </div>
      </div>
    {projectId && currentPresentationJob?.id && (
      <StopHoldButton onConfirm={handleCancel} size="sm" />
    )}
    </div>
  );
};
