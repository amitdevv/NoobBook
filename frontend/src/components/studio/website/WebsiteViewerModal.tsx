/**
 * WebsiteViewerModal Component
 * Educational Note: Modal for previewing generated websites in an iframe.
 * Simpler than component viewer since websites are single-page previews.
 */

import React, { useState, useEffect } from 'react';
import { DownloadSimple, Globe, PencilSimple } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { websitesAPI, type WebsiteJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface WebsiteViewerModalProps {
  projectId: string;
  viewingWebsiteJob: WebsiteJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const WebsiteViewerModal: React.FC<WebsiteViewerModalProps> = ({
  projectId,
  viewingWebsiteJob,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [editInput, setEditInput] = useState('');

  // Sync edit input separately to avoid re-rendering iframe
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
    }
  };

  if (!viewingWebsiteJob) return null;

  const previewUrl = getAuthUrl(websitesAPI.getPreviewUrl(projectId, viewingWebsiteJob.id));
  const downloadUrl = getAuthUrl(websitesAPI.getDownloadUrl(projectId, viewingWebsiteJob.id));

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `${viewingWebsiteJob.site_name || 'website'}.zip`;
    link.click();
  };

  const handleOpenInNewTab = () => {
    window.open(previewUrl, '_blank');
  };

  return (
    <Dialog open={!!viewingWebsiteJob} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-6xl h-[85vh] p-0 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b flex-shrink-0">
          <DialogHeader className="mb-2">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-purple-500/10 rounded">
                <Globe size={20} weight="duotone" className="text-purple-600" />
              </div>
              <div>
                <DialogTitle className="text-lg">
                  {viewingWebsiteJob.site_name || 'Website'}
                </DialogTitle>
              </div>
            </div>
            <DialogDescription className="flex items-center gap-3">
              {viewingWebsiteJob.parent_job_id && (
                <span className="inline-flex items-center gap-0.5 text-[11px] text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                  <PencilSimple size={10} />
                  Edited version
                </span>
              )}
              <span>
                {viewingWebsiteJob.pages_created?.length || 0} pages • {viewingWebsiteJob.features_implemented?.length || 0} features
              </span>
            </DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-2">
            <button
              onClick={handleOpenInNewTab}
              className="px-3 py-1.5 text-xs bg-purple-500/10 hover:bg-purple-500/20 text-purple-700 rounded transition-colors flex items-center gap-1.5"
            >
              <Globe size={14} />
              Open in New Tab
            </button>
            <button
              onClick={handleDownload}
              className="px-3 py-1.5 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded transition-colors flex items-center gap-1.5"
            >
              <DownloadSimple size={14} />
              Download ZIP
            </button>
          </div>
        </div>

        {/* Website Preview */}
        <div className="flex-1 min-h-0 bg-gray-50">
          <iframe
            src={previewUrl}
            className="w-full h-full border-0"
            title={viewingWebsiteJob.site_name || 'Website Preview'}
            sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
          />
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add a contact form', 'change color scheme')"
                className="flex-1"
                disabled={isGenerating}
                onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && !isGenerating && handleEdit()}
              />
              <Button
                onClick={handleEdit}
                disabled={!editInput.trim() || isGenerating}
                size="sm"
              >
                <PencilSimple size={14} className="mr-1" />
                Edit
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
