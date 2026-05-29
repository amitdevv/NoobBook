/**
 * FlowDiagramProgressIndicator Component
 * Shows real-time progress during flow diagram generation.
 * Cyan theme distinguishes from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { FlowDiagramJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface FlowDiagramProgressIndicatorProps {
  currentFlowDiagramJob: FlowDiagramJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const FlowDiagramProgressIndicator: React.FC<FlowDiagramProgressIndicatorProps> = ({
  currentFlowDiagramJob,
  projectId,
}) => {
  if (!currentFlowDiagramJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentFlowDiagramJob?.id) return;
    await cancelStudioJob(projectId, currentFlowDiagramJob.id);
  };

  return (
    <div className="p-2 bg-cyan-500/5 rounded-md border border-cyan-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-cyan-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentFlowDiagramJob.source_name || 'Generating flow diagram...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentFlowDiagramJob.progress || 'Starting...'}
          </p>
        </div>
        {projectId && currentFlowDiagramJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
