/**
 * InfographicListItem Component
 * Educational Note: Renders a saved infographic in the Generated Content list.
 */

import React from 'react';
import { ChartPieSlice, Trash } from '@phosphor-icons/react';
import type { InfographicJob } from '@/lib/api/studio';

interface InfographicListItemProps {
  job: InfographicJob;
  onClick: () => void;
  onDelete: () => void;
}

export const InfographicListItem: React.FC<InfographicListItemProps> = ({ job, onClick, onDelete }) => {
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-amber-500/10 rounded-md flex-shrink-0">
        <ChartPieSlice size={16} className="text-amber-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.topic_title || 'Infographic'}
        </p>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="p-1 hover:bg-destructive/10 rounded flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Delete"
      >
        <Trash size={14} className="text-muted-foreground hover:text-destructive" />
      </button>
    </div>
  );
};
