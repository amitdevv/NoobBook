/**
 * WebsiteListItem Component
 * Educational Note: Renders a saved website in the Generated Content list.
 * Clicking opens website in new window. Download button downloads ZIP.
 */

import React from 'react';
import { Globe, DownloadSimple, Trash } from '@phosphor-icons/react';
import type { WebsiteJob } from '@/lib/api/studio';

interface WebsiteListItemProps {
  job: WebsiteJob;
  onOpen: () => void;
  onDownload: (e: React.MouseEvent) => void;
  onDelete: () => void;
}

export const WebsiteListItem: React.FC<WebsiteListItemProps> = ({
  job,
  onOpen,
  onDownload,
  onDelete,
}) => {
  return (
    <div
      onClick={onOpen}
      className="group flex items-start gap-2.5 p-2.5 bg-muted/50 rounded-lg border hover:border-primary/50 cursor-pointer transition-colors"
    >
      <Globe size={16} weight="duotone" className="text-purple-600 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-900 truncate">
          {job.site_name || 'Website'}
        </p>
        <p className="text-[11px] text-gray-500 truncate">
          {job.pages_created?.length || 0} pages • {job.features_implemented?.length || 0} features
        </p>
      </div>
      {/* Download button */}
      <button
        onClick={onDownload}
        className="p-1.5 hover:bg-purple-600/20 rounded transition-colors"
        title="Download ZIP"
      >
        <DownloadSimple size={14} className="text-purple-600" />
      </button>
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
