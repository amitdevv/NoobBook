/**
 * MarketingStrategyProgressIndicator Component
 * Educational Note: Shows real-time progress during marketing strategy generation.
 * Emerald/teal theme distinguishes marketing strategies from other studio items.
 */

import React from 'react';
import { SpinnerGap } from '@phosphor-icons/react';
import type { MarketingStrategyJob } from '@/lib/api/studio';
import { cancelStudioJob } from '@/lib/api/studio';
import { StopHoldButton } from '../shared/StopHoldButton';

interface MarketingStrategyProgressIndicatorProps {
  currentMarketingStrategyJob: MarketingStrategyJob | null;
  /** Project the job belongs to — wires the cancel API. */
  projectId?: string;
}

export const MarketingStrategyProgressIndicator: React.FC<MarketingStrategyProgressIndicatorProps> = ({
  currentMarketingStrategyJob,
  projectId,
}) => {
  if (!currentMarketingStrategyJob) return null;

  // Calculate progress percentage
  const progress = currentMarketingStrategyJob.total_sections > 0
    ? Math.round((currentMarketingStrategyJob.sections_written / currentMarketingStrategyJob.total_sections) * 100)
    : 0;

  const handleCancel = async () => {
    if (!projectId || !currentMarketingStrategyJob?.id) return;
    await cancelStudioJob(projectId, currentMarketingStrategyJob.id);
  };

  return (
    <div className="p-2 bg-emerald-500/5 rounded-md border border-emerald-500/20 overflow-hidden">
      <div className="flex items-center gap-2">
        <SpinnerGap size={14} className="animate-spin text-emerald-500 flex-shrink-0" />
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-xs font-medium truncate">
            {currentMarketingStrategyJob.document_title || currentMarketingStrategyJob.source_name || 'Generating Marketing Strategy...'}
          </p>
          <p className="text-[10px] text-muted-foreground truncate">
            {currentMarketingStrategyJob.status_message || 'Starting...'}
            {currentMarketingStrategyJob.total_sections > 0 && ` (${progress}%)`}
          </p>
        </div>
        {projectId && currentMarketingStrategyJob?.id && (
          <StopHoldButton onConfirm={handleCancel} size="sm" />
        )}
      </div>
    </div>
  );
};
