/**
 * PRDProgressIndicator Component
 * Shows real-time progress during PRD generation.
 * Amber theme distinguishes PRDs from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { PRDJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface PRDProgressIndicatorProps {
  currentPRDJob: PRDJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const PRDProgressIndicator: React.FC<PRDProgressIndicatorProps> = ({
  currentPRDJob,
  projectId,
}) => {
  if (!currentPRDJob) return null;

  // Calculate progress percentage
  const progress = currentPRDJob.total_sections > 0
    ? Math.round((currentPRDJob.sections_written / currentPRDJob.total_sections) * 100)
    : 0;

  const handleCancel = async () => {
    if (!projectId || !currentPRDJob?.id) return;
    await cancelStudioJob(projectId, currentPRDJob.id);
  };

  return (
    <div className="p-2 bg-amber-500/5 rounded-md border border-amber-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-amber-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentPRDJob.document_title || currentPRDJob.source_name || 'Generating PRD...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentPRDJob.status_message || 'Starting...'}
            {currentPRDJob.total_sections > 0 && ` (${progress}%)`}
          </p>
        </div>
        {projectId && currentPRDJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
