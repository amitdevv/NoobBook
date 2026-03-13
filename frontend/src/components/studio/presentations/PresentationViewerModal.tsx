/**
 * PresentationViewerModal Component
 * Educational Note: Modal for previewing generated presentations with slide navigation.
 * Shows screenshot images with PPTX download option.
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  DownloadSimple,
  Presentation,
  CaretLeft,
  CaretRight,
  PencilSimple,
} from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { presentationsAPI, type PresentationJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';

interface PresentationViewerModalProps {
  projectId: string;
  viewingPresentationJob: PresentationJob | null;
  onClose: () => void;
  onDownloadPptx?: (jobId: string) => void;
  onDownloadSource?: (jobId: string) => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const PresentationViewerModal: React.FC<PresentationViewerModalProps> = ({
  projectId,
  viewingPresentationJob,
  onClose,
  onDownloadPptx,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [currentSlide, setCurrentSlide] = useState(1);
  const [editInput, setEditInput] = useState('');

  // Sync edit input separately to avoid re-rendering slides
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  // Reset to first slide when opening a new presentation
  useEffect(() => {
    if (viewingPresentationJob) {
      setCurrentSlide(1);
    }
  }, [viewingPresentationJob?.id]);

  // Compute screenshot URL synchronously during render (not in useEffect)
  // Educational Note: useMemo ensures the URL updates in the SAME render as
  // the slide counter, keeping them in sync. useEffect runs after paint which
  // causes a visible desync between the counter and the displayed image.
  const screenshotUrl = useMemo(() => {
    if (viewingPresentationJob && viewingPresentationJob.screenshots?.length > 0) {
      const screenshot = viewingPresentationJob.screenshots[currentSlide - 1];
      if (screenshot && screenshot.screenshot_file) {
        return getAuthUrl(presentationsAPI.getScreenshotUrl(
          projectId,
          viewingPresentationJob.id,
          screenshot.screenshot_file
        ));
      }
    }
    return null;
  }, [viewingPresentationJob, currentSlide, projectId]);

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
    }
  };

  if (!viewingPresentationJob) return null;

  const totalSlides = viewingPresentationJob.screenshots?.length || 0;

  const handlePrevSlide = () => {
    if (currentSlide > 1) {
      setCurrentSlide((prev) => prev - 1);
    }
  };

  const handleNextSlide = () => {
    if (currentSlide < totalSlides) {
      setCurrentSlide((prev) => prev + 1);
    }
  };

  const handleDownloadPptx = () => {
    if (onDownloadPptx) {
      onDownloadPptx(viewingPresentationJob.id);
    } else {
      const link = document.createElement('a');
      // API_BASE_URL already includes /api/v1 path, getAuthUrl adds JWT for browser element auth
      link.href = getAuthUrl(presentationsAPI.getDownloadUrl(
        projectId,
        viewingPresentationJob.id,
        'pptx'
      ));
      link.click();
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      handlePrevSlide();
    } else if (e.key === 'ArrowRight') {
      handleNextSlide();
    }
  };

  return (
    <Dialog open={!!viewingPresentationJob} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="sm:max-w-6xl h-[85vh] p-0 overflow-hidden flex flex-col"
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex-shrink-0">
          <DialogHeader className="mb-2">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-amber-500/10 rounded">
                <Presentation size={20} weight="duotone" className="text-amber-600" />
              </div>
              <div>
                <DialogTitle className="text-lg">
                  {viewingPresentationJob.presentation_title || 'Presentation'}
                </DialogTitle>
              </div>
            </div>
            <DialogDescription className="flex items-center gap-3">
              {viewingPresentationJob.parent_job_id && (
                <span className="inline-flex items-center gap-0.5 text-[11px] text-amber-600 bg-amber-500/10 px-1.5 py-0.5 rounded">
                  <PencilSimple size={10} />
                  Edited version
                </span>
              )}
              <span>
                {totalSlides} slides
                {viewingPresentationJob.presentation_type &&
                  ` | ${viewingPresentationJob.presentation_type}`}
                {viewingPresentationJob.target_audience &&
                  ` | For: ${viewingPresentationJob.target_audience}`}
              </span>
            </DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadPptx}
              className="px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-700 text-white rounded transition-colors flex items-center gap-1.5"
            >
              <DownloadSimple size={14} />
              Download PPTX
            </button>
          </div>
        </div>

        {/* Slide Preview - Shows Screenshot Image */}
        <div className="flex-1 min-h-0 bg-gray-900 relative flex items-center justify-center">
          {screenshotUrl ? (
            <img
              key={currentSlide}
              src={screenshotUrl}
              alt={`Slide ${currentSlide}`}
              className="max-w-full max-h-full object-contain"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400">
              No slides available
            </div>
          )}

          {/* Navigation Controls */}
          {totalSlides > 1 && (
            <>
              {/* Previous Button */}
              <button
                onClick={handlePrevSlide}
                disabled={currentSlide === 1}
                className="absolute left-4 top-1/2 -translate-y-1/2 p-2 bg-white/90 hover:bg-white rounded-full shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <CaretLeft size={24} className="text-gray-700" />
              </button>

              {/* Next Button */}
              <button
                onClick={handleNextSlide}
                disabled={currentSlide === totalSlides}
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 bg-white/90 hover:bg-white rounded-full shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                <CaretRight size={24} className="text-gray-700" />
              </button>
            </>
          )}
        </div>

        {/* Footer - Slide Counter */}
        <div className="px-6 py-3 border-t bg-gray-50/50 flex-shrink-0 flex items-center justify-between">
          <div className="text-xs text-muted-foreground max-w-[70%] truncate">
            {viewingPresentationJob.summary && (
              <span>
                <span className="font-medium">Summary:</span> {viewingPresentationJob.summary}
              </span>
            )}
          </div>
          <div className="text-sm font-medium text-gray-600">
            Slide {currentSlide} of {totalSlides}
          </div>
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add more data charts', 'simplify slide 3')"
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
