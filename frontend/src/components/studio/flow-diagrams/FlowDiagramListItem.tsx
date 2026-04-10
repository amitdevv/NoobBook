/**
 * FlowDiagramListItem Component
 * Educational Note: Renders a saved flow diagram in the Generated Content list.
 * Clicking opens the diagram in the viewer modal.
 */

import React from 'react';
import { FlowArrow, Trash } from '@phosphor-icons/react';
import type { FlowDiagramJob } from '@/lib/api/studio';

interface FlowDiagramListItemProps {
  job: FlowDiagramJob;
  onClick: () => void;
  onDelete: () => void;
}

export const FlowDiagramListItem: React.FC<FlowDiagramListItemProps> = ({ job, onClick, onDelete }) => {
  // Format diagram type for display
  const diagramTypeLabel = job.diagram_type
    ? job.diagram_type.charAt(0).toUpperCase() + job.diagram_type.slice(1)
    : 'Diagram';

  return (
    <div
      className="group flex items-center gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="p-1.5 bg-cyan-500/10 rounded-md flex-shrink-0">
        <FlowArrow size={16} className="text-cyan-600" />
      </div>
      <div className="flex-1 min-w-0 overflow-hidden">
        <p className="text-xs font-medium truncate">
          {job.title || diagramTypeLabel}
        </p>
        <p className="text-[11px] text-muted-foreground truncate">
          {job.source_name}
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
