/**
 * QuizViewerModal Component
 * Educational Note: Modal for viewing interactive quiz questions.
 * Uses QuizViewer component for question display and answer checking.
 * Supports iterative editing of quiz content.
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
import { Exam, PencilSimple } from '@phosphor-icons/react';
import { QuizViewer } from './QuizViewer';
import type { QuizJob } from '@/lib/api/studio';

interface QuizViewerModalProps {
  viewingQuizJob: QuizJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const QuizViewerModal: React.FC<QuizViewerModalProps> = ({
  viewingQuizJob,
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
    <Dialog open={viewingQuizJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-3xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Exam size={20} className="text-orange-600" />
            Quiz - {viewingQuizJob?.source_name}
          </DialogTitle>
          <DialogDescription>
            {viewingQuizJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-orange-600 bg-orange-500/10 px-1.5 py-0.5 rounded mr-2">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {viewingQuizJob?.topic_summary || ''}
          </DialogDescription>
        </DialogHeader>

        {/* Quiz Viewer */}
        <div className="flex-1 min-h-0">
          {viewingQuizJob && (
            <QuizViewer
              questions={viewingQuizJob.questions}
              topicSummary={viewingQuizJob.topic_summary}
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
                placeholder="Describe changes... (e.g., 'make questions harder', 'add more options')"
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
