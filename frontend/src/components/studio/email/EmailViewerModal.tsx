/**
 * EmailViewerModal Component
 * Educational Note: Modal for viewing and downloading email templates.
 * Displays preview iframe, color scheme, and download options.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { ShareNetwork, DownloadSimple, PencilSimple } from '@phosphor-icons/react';
import { emailsAPI, type EmailJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface EmailViewerModalProps {
  projectId: string;
  viewingEmailJob: EmailJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const EmailViewerModal: React.FC<EmailViewerModalProps> = ({
  projectId,
  viewingEmailJob,
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

  return (
    <Dialog open={viewingEmailJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-6xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center gap-2">
            <ShareNetwork size={20} className="text-blue-600" />
            <DialogTitle>
              {viewingEmailJob?.template_name || 'Email Template'}
            </DialogTitle>
          </div>
          <DialogDescription className="flex items-center gap-3">
            {viewingEmailJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-blue-600 bg-blue-500/10 px-1.5 py-0.5 rounded">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {viewingEmailJob?.subject_line && (
              <span>Subject: {viewingEmailJob.subject_line}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* Email Template Preview */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {viewingEmailJob?.preview_url && (
            <div className="p-6">
              {/* Preview iframe */}
              <div className="relative rounded-lg overflow-hidden border bg-gray-50 dark:bg-gray-900 mb-4">
                <iframe
                  src={getAuthUrl(viewingEmailJob.preview_url)}
                  className="w-full h-[600px]"
                  title="Email template preview"
                  sandbox="allow-same-origin"
                />
              </div>

              {/* Template Info */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Template Type</p>
                  <p className="text-sm capitalize">{viewingEmailJob.template_type || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Images</p>
                  <p className="text-sm">{viewingEmailJob.images?.length || 0} image{viewingEmailJob.images?.length !== 1 ? 's' : ''}</p>
                </div>
              </div>

              {/* Color Scheme */}
              {viewingEmailJob.color_scheme && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Color Scheme</p>
                  <div className="flex gap-2">
                    {Object.entries(viewingEmailJob.color_scheme).map(([name, color]) => (
                      <TooltipProvider key={name}>
                        <Tooltip>
                          <TooltipTrigger>
                            <div
                              className="w-8 h-8 rounded border border-gray-300 dark:border-gray-700"
                              style={{ backgroundColor: color }}
                            />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="text-xs capitalize">{name}: {color}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    ))}
                  </div>
                </div>
              )}

              {/* Download Buttons */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="default"
                  className="gap-1 flex-1"
                  onClick={() => {
                    const downloadUrl = emailsAPI.getDownloadUrl(projectId, viewingEmailJob.id);
                    const link = document.createElement('a');
                    link.href = getAuthUrl(downloadUrl);
                    link.click();
                  }}
                >
                  <DownloadSimple size={14} />
                  Download All (ZIP)
                </Button>
                <Button
                  size="sm"
                  variant="soft"
                  className="gap-1"
                  onClick={() => {
                    if (viewingEmailJob.html_url) {
                      const link = document.createElement('a');
                      link.href = getAuthUrl(viewingEmailJob.html_url);
                      link.download = viewingEmailJob.html_file || 'email_template.html';
                      link.click();
                    }
                  }}
                >
                  Download HTML
                </Button>
              </div>

              {/* Source info */}
              <p className="text-xs text-muted-foreground mt-4">
                Generated from: {viewingEmailJob.source_name}
              </p>
            </div>
          )}
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'make it more casual', 'change CTA button text')"
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
