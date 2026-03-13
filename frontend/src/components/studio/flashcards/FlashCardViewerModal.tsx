/**
 * FlashCardViewerModal Component
 * Educational Note: Modal with carousel and 3D flip animation.
 * Features: card navigation, flip animation, progress bar, reset, and iterative editing.
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
import { Cards, CaretLeft, CaretRight, ArrowsClockwise, PencilSimple } from '@phosphor-icons/react';
import type { FlashCardJob } from '@/lib/api/studio';

interface FlashCardViewerModalProps {
  viewingFlashCardJob: FlashCardJob | null;
  onClose: () => void;
  onEdit?: (instructions: string) => void;
  isGenerating?: boolean;
  defaultEditInput?: string;
}

export const FlashCardViewerModal: React.FC<FlashCardViewerModalProps> = ({
  viewingFlashCardJob,
  onClose,
  onEdit,
  isGenerating,
  defaultEditInput = '',
}) => {
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isCardFlipped, setIsCardFlipped] = useState(false);
  const [editInput, setEditInput] = useState('');

  useEffect(() => {
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
  }, [viewingFlashCardJob?.id]);

  // Sync edit input separately to avoid re-fetching state
  useEffect(() => {
    setEditInput(defaultEditInput);
  }, [defaultEditInput]);

  /**
   * Toggle current card flip
   */
  const toggleCardFlip = () => {
    setIsCardFlipped((prev) => !prev);
  };

  /**
   * Navigate to next card
   */
  const nextCard = () => {
    if (viewingFlashCardJob && currentCardIndex < viewingFlashCardJob.cards.length - 1) {
      setCurrentCardIndex((prev) => prev + 1);
      setIsCardFlipped(false); // Reset flip state for new card
    }
  };

  /**
   * Navigate to previous card
   */
  const prevCard = () => {
    if (currentCardIndex > 0) {
      setCurrentCardIndex((prev) => prev - 1);
      setIsCardFlipped(false); // Reset flip state for new card
    }
  };

  /**
   * Reset to first card
   */
  const resetCards = () => {
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
  };

  /**
   * Handle modal close - reset state
   */
  const handleClose = () => {
    setCurrentCardIndex(0);
    setIsCardFlipped(false);
    onClose();
  };

  const handleEdit = () => {
    if (editInput.trim() && onEdit) {
      onEdit(editInput.trim());
    }
  };

  return (
    <Dialog open={viewingFlashCardJob !== null} onOpenChange={(open) => {
      if (!open) handleClose();
    }}>
      <DialogContent className="sm:max-w-2xl p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Cards size={20} className="text-purple-600" />
            {viewingFlashCardJob?.source_name}
          </DialogTitle>
          <DialogDescription>
            {viewingFlashCardJob?.parent_job_id && (
              <span className="inline-flex items-center gap-0.5 text-[11px] text-purple-600 bg-purple-500/10 px-1.5 py-0.5 rounded mr-2">
                <PencilSimple size={10} />
                Edited version
              </span>
            )}
            {viewingFlashCardJob?.topic_summary || ''}
          </DialogDescription>
        </DialogHeader>

        {/* Flip instruction */}
        <p className="text-xs text-center text-muted-foreground pt-2">
          Click card to flip
        </p>

        {/* Card Carousel */}
        <div className="flex items-center justify-center gap-4 py-4 px-6">
          {/* Previous Button */}
          <button
            onClick={prevCard}
            disabled={currentCardIndex === 0}
            className={`p-3 rounded-full border transition-all ${
              currentCardIndex === 0
                ? 'opacity-30 cursor-not-allowed border-muted'
                : 'hover:bg-muted border-border hover:border-primary/50'
            }`}
          >
            <CaretLeft size={20} className="text-muted-foreground" />
          </button>

          {/* Flash Card with 3D Flip */}
          {viewingFlashCardJob?.cards[currentCardIndex] && (
            <div
              className="relative w-full max-w-md cursor-pointer"
              style={{ perspective: '1000px' }}
              onClick={toggleCardFlip}
            >
              <div
                className="relative w-full transition-transform duration-500"
                style={{
                  transformStyle: 'preserve-3d',
                  transform: isCardFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
                }}
              >
                {/* Front of Card (Question) */}
                <div
                  className="w-full min-h-[280px] p-6 rounded-2xl bg-zinc-900 dark:bg-zinc-900 text-white flex flex-col"
                  style={{ backfaceVisibility: 'hidden' }}
                >
                  <div className="flex-1 flex items-center justify-center">
                    <p className="text-xl font-medium text-center leading-relaxed">
                      {viewingFlashCardJob.cards[currentCardIndex].front}
                    </p>
                  </div>
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-xs text-zinc-400 capitalize">
                      {viewingFlashCardJob.cards[currentCardIndex].category}
                    </span>
                    <span className="text-xs text-zinc-500">
                      Click to see answer
                    </span>
                  </div>
                </div>

                {/* Back of Card (Answer) */}
                <div
                  className="absolute inset-0 w-full min-h-[280px] p-6 rounded-2xl bg-gradient-to-br from-green-600 to-green-700 text-white flex flex-col"
                  style={{
                    backfaceVisibility: 'hidden',
                    transform: 'rotateY(180deg)',
                  }}
                >
                  <div className="flex-1 flex items-center justify-center">
                    <p className="text-lg text-center leading-relaxed">
                      {viewingFlashCardJob.cards[currentCardIndex].back}
                    </p>
                  </div>
                  <div className="flex items-center justify-between mt-4">
                    <span className="text-xs text-green-200">
                      Answer
                    </span>
                    <span className="text-xs text-green-300">
                      Click to see question
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Next Button */}
          <button
            onClick={nextCard}
            disabled={!viewingFlashCardJob || currentCardIndex >= viewingFlashCardJob.cards.length - 1}
            className={`p-3 rounded-full border transition-all ${
              !viewingFlashCardJob || currentCardIndex >= viewingFlashCardJob.cards.length - 1
                ? 'opacity-30 cursor-not-allowed border-muted'
                : 'hover:bg-muted border-border hover:border-primary/50'
            }`}
          >
            <CaretRight size={20} className="text-muted-foreground" />
          </button>
        </div>

        {/* Progress Indicator */}
        <div className="flex items-center justify-center gap-3 px-6 pb-4">
          {/* Reset Button */}
          <button
            onClick={resetCards}
            className="p-1.5 rounded hover:bg-muted transition-colors"
            title="Reset to first card"
          >
            <ArrowsClockwise size={16} className="text-muted-foreground" />
          </button>

          {/* Progress Bar */}
          <div className="flex-1 max-w-[200px] h-1 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 transition-all duration-300"
              style={{
                width: viewingFlashCardJob
                  ? `${((currentCardIndex + 1) / viewingFlashCardJob.cards.length) * 100}%`
                  : '0%'
              }}
            />
          </div>

          {/* Card Counter */}
          <span className="text-sm text-muted-foreground min-w-[60px] text-right">
            {currentCardIndex + 1} / {viewingFlashCardJob?.card_count || 0} cards
          </span>
        </div>

        {/* Edit input */}
        {onEdit && (
          <div className="px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
            <div className="flex gap-2">
              <Input
                value={editInput}
                onChange={(e) => setEditInput(e.target.value)}
                placeholder="Describe changes... (e.g., 'add more concept cards', 'make answers shorter')"
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
