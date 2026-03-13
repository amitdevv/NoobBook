/**
 * MindMapViewerModal Component
 * Educational Note: Modal for viewing mind map tree visualization.
 * Uses MindMapViewer component for interactive node display.
 * Supports iterative editing of mind map content.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { TreeStructure, PencilSimple } from '@phosphor-icons/react';
import { MindMapViewer } from './MindMapViewer';
import type { MindMapJob } from '@/lib/api/studio';

interface MindMapViewerModalProps {
  viewingMindMapJob: MindMapJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const MindMapViewerModal: React.FC<MindMapViewerModalProps> = ({
  viewingMindMapJob,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [editInput, setEditInput] = useState('');

  // Sync edit input separately to avoid re-fetching state
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
    }
  };

  return (
    <Dialog open={viewingMindMapJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-5xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <TreeStructure size={20} className="text-blue-600" />
            {viewingMindMapJob?.source_name}
          </DialogTitle>
          <DialogDescription>
            {viewingMindMapJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-blue-600 bg-blue-500/10 px-1.5 py-0.5 rounded mr-2">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {viewingMindMapJob?.topic_summary || ''}
          </DialogDescription>
        </DialogHeader>

        {/* Mind Map Visualization */}
        <div className="flex-1 min-h-0">
          {viewingMindMapJob && (
            <MindMapViewer
              nodes={viewingMindMapJob.nodes}
              topicSummary={viewingMindMapJob.topic_summary}
            />
          )}
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add more subtopics', 'focus on X section')"
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
