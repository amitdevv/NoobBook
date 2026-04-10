/**
 * AdListItem Component
 * Educational Note: Renders saved ad creatives in the Generated Content list.
 */

import React from 'react';
import { Image, Trash } from '@phosphor-icons/react';
import type { AdJob } from '@/lib/api/studio';

interface AdListItemProps {
  job: AdJob;
  index: number;
  onClick: () => void;
  onDelete: () => void;
}

export const AdListItem: React.FC<AdListItemProps> = ({ job, index, onClick, onDelete }) => {
  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-green-500/10 rounded-md flex-shrink-0">
        <Image size={16} className="text-green-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">Ad Creatives · Iteration {index}</p>
      </div>
      <span className="text-[11px] text-muted-foreground flex-shrink-0">
        {job.images.length}
      </span>
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
