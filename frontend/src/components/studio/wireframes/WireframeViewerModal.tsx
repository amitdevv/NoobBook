/**
 * WireframeViewerModal Component
 * Educational Note: Full-screen modal for viewing and editing wireframes.
 * Uses Excalidraw's built-in pan/zoom and editing capabilities.
 * Supports iterative editing via an edit input bar.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PencilSimple } from '@phosphor-icons/react';
import { WireframeViewer } from './WireframeViewer';
import type { WireframeJob } from '@/lib/api/studio/wireframes';

interface WireframeViewerModalProps {
  job: WireframeJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const WireframeViewerModal: React.FC<WireframeViewerModalProps> = ({
  job,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [editInput, setEditInput] = useState('');

  // Sync edit input when defaultEditInput changes (e.g. after failed edit preserves input)
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  if (!job || !job.elements || job.elements.length === 0) return null;

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
    }
  };

  return (
    <Dialog open={!!job} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[95vw] w-[95vw] h-[92vh] p-0 flex flex-col gap-0">
        {/* Compact header */}
        <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold">
              {job.title || 'Wireframe'}
            </h2>
            <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
              wireframe
            </span>
            {job.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {job.source_name && (
              <span className="text-sm text-muted-foreground">
                from {job.source_name}
              </span>
            )}
            {job.generation_time_seconds && (
              <span className="text-xs text-muted-foreground">
                ({job.generation_time_seconds}s)
              </span>
            )}
          </div>
        </div>

        {/* Wireframe viewer - Excalidraw needs explicit non-zero dimensions */}
        <div style={{ flex: 1, height: 'calc(92vh - 50px)', width: '100%' }}>
          <WireframeViewer elements={job.elements} />
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add a sidebar navigation', 'make it mobile-first')"
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
