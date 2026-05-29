/**
 * AudioProgressIndicator Component
 * Shows real-time progress during audio generation.
 * Primary theme distinguishes audio from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { AudioJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface AudioProgressIndicatorProps {
  currentAudioJob: AudioJob | null;
  /** Project the job belongs to — used to wire the cancel API. */
  projectId?: string;
}

export const AudioProgressIndicator: React.FC<AudioProgressIndicatorProps> = ({
  currentAudioJob,
  projectId,
}) => {
  if (!currentAudioJob) return null;

  const handleCancel = async () => {
    if (!projectId || !currentAudioJob?.id) return;
    await cancelStudioJob(projectId, currentAudioJob.id);
  };

  return (
    <div className="p-2 bg-primary/5 rounded-md border border-primary/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-primary flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentAudioJob.source_name || 'Generating audio...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentAudioJob.progress || 'Starting...'}
          </p>
        </div>
        {projectId && currentAudioJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
