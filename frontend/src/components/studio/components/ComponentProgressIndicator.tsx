/**
 * ComponentProgressIndicator Component
 * Educational Note: Shows real-time progress during component generation.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { ComponentJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface ComponentProgressIndicatorProps {
  currentComponentJob: ComponentJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const ComponentProgressIndicator: React.FC<ComponentProgressIndicatorProps> = ({
  currentComponentJob,
  projectId,
}) => {
  if (!currentComponentJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentComponentJob?.id) return;
    await cancelStudioJob(projectId, currentComponentJob.id);
  };

  return (
    <div className="p-2 bg-blue-500/5 rounded-md border border-blue-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-blue-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentComponentJob.source_name || 'Generating components...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentComponentJob.status_message || 'Starting...'}
          </p>
        </div>
        {projectId && currentComponentJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
