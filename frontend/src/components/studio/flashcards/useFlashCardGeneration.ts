/**
 * useFlashCardGeneration Hook
 * Educational Note: Custom hook for flash card generation logic.
 * Handles state management, API calls, polling, and iterative editing.
 */

import { useState, useRef } from 'react';
import { flashCardsAPI, type FlashCardJob } from '@/lib/api/studio';
import { useToast } from '../../ui/use-toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('flash-card-generation');

export const useFlashCardGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedFlashCardJobs, setSavedFlashCardJobs] = useState<FlashCardJob[]>([]);
  const [currentFlashCardJob, setCurrentFlashCardJob] = useState<FlashCardJob | null>(null);
  const [isGeneratingFlashCards, setIsGeneratingFlashCards] = useState(false);
  const pollingRef = useRef(false);
  const [viewingFlashCardJob, setViewingFlashCardJob] = useState<FlashCardJob | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);

  /**
   * Load saved flash card jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const flashCardResponse = await flashCardsAPI.listJobs(projectId);
      if (flashCardResponse.success && flashCardResponse.jobs) {
        const finishedJobs = flashCardResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedFlashCardJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingFlashCards && !pollingRef.current) {
          const inProgressJob = flashCardResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingFlashCards(true);
            setCurrentFlashCardJob(inProgressJob);
            try {
              const finalJob = await flashCardsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentFlashCardJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh — keep parent so user can view previous versions
                  setSavedFlashCardJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh — delete orphaned error job, parent stays
                  flashCardsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
                    console.warn('[Studio] Failed to delete failed edit job', err);
                  });
                } else {
                  setSavedFlashCardJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingFlashCards(false);
              setCurrentFlashCardJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved flash card jobs');
    }
  };

  /**
   * Handle flash card generation
   */
  const handleFlashCardGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id || "";

    setIsGeneratingFlashCards(true);
    setCurrentFlashCardJob(null);

    try {
      const startResponse = await flashCardsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start flash card generation.');
        setIsGeneratingFlashCards(false);
        return;
      }

      showSuccess(`Generating flash cards for ${startResponse.source_name}...`);

      const finalJob = await flashCardsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlashCardJob(job)
      );

      setCurrentFlashCardJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.card_count} flash cards!`);
        setSavedFlashCardJobs((prev) => [finalJob, ...prev]);
        setViewingFlashCardJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flash card generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'Flash card generation failed');
      showError(error instanceof Error ? error.message : 'Flash card generation failed.');
    } finally {
      setIsGeneratingFlashCards(false);
      setCurrentFlashCardJob(null);
    }
  };

  /**
   * Handle flash card edit — refine existing cards based on user instructions
   */
  const handleFlashCardEdit = async (parentJob: FlashCardJob, editInstructions: string) => {
    if (isGeneratingFlashCards) return;
    setIsGeneratingFlashCards(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await flashCardsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Flash card edit: API start failed', startResponse);
        showError(startResponse.error || 'Failed to start flash card edit.');
        setViewingFlashCardJob(parentJob);
        return;
      }

      // Only close modal once we know generation started
      setCurrentFlashCardJob(null);
      setViewingFlashCardJob(null);

      showSuccess('Editing flash cards...');

      const finalJob = await flashCardsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlashCardJob(job)
      );

      setCurrentFlashCardJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Flash cards edited: ${finalJob.card_count} cards`);
        setSavedFlashCardJobs((prev) => [finalJob, ...prev]);
        setViewingFlashCardJob(finalJob); // Reopen modal with new job
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flash card edit failed.');
        setViewingFlashCardJob(parentJob); // Restore parent modal so user can retry
        // Delete the failed edit job so it doesn't pollute the list on refresh
        flashCardsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
          console.warn('[Studio] Failed to delete failed edit job', err);
        });
      }
    } catch (error) {
      console.error('[Studio] Flash card edit: failed', error);
      log.error({ err: error }, 'Flash card edit failed');
      showError(error instanceof Error ? error.message : 'Flash card edit failed.');
      setViewingFlashCardJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingFlashCards(false);
      setCurrentFlashCardJob(null);
      // Note: pendingEdit is intentionally NOT cleared here — on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
      // It IS cleared on success (see the `if (finalJob.status === 'ready')` branch above).
    }
  };

  /**
   * Delete a flash card job
   */
  const handleFlashCardDelete = async (jobId: string) => {
    if (!window.confirm('Are you sure you want to delete this? This cannot be undone.')) return;
    try {
      await flashCardsAPI.deleteJob(projectId, jobId);
      setSavedFlashCardJobs((prev) => prev.filter((j) => j.id !== jobId));
      showSuccess('Deleted successfully.');
    } catch (error) {
      log.error({ err: error }, 'failed to delete flash card job');
      showError('Failed to delete. Please try again.');
    }
  };

  return {
    savedFlashCardJobs,
    currentFlashCardJob,
    isGeneratingFlashCards,
    viewingFlashCardJob,
    setViewingFlashCardJob,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingFlashCardJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleFlashCardGeneration,
    handleFlashCardEdit,
    handleFlashCardDelete,
  };
};
