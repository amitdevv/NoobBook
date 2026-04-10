/**
 * usePresentationGeneration Hook
 * Educational Note: Custom hook for presentation generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { presentationsAPI, type PresentationJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { useToast } from '../../ui/use-toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('presentation-generation');

export const usePresentationGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedPresentationJobs, setSavedPresentationJobs] = useState<PresentationJob[]>([]);
  const [currentPresentationJob, setCurrentPresentationJob] = useState<PresentationJob | null>(null);
  const [isGeneratingPresentation, setIsGeneratingPresentation] = useState(false);
  const pollingRef = useRef(false);
  const [viewingPresentationJob, setViewingPresentationJob] = useState<PresentationJob | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Load saved presentation jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const response = await presentationsAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        // Show fully exported presentations + error jobs
        const finishedJobs = response.jobs.filter(
          (job) =>
            (job.status === 'ready' && job.export_status === 'ready') ||
            job.status === 'error'
        );
        setSavedPresentationJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingPresentation && !pollingRef.current) {
          const inProgressJob = response.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingPresentation(true);
            setCurrentPresentationJob(inProgressJob);
            try {
              const finalJob = await presentationsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentPresentationJob(job)
              );
              if ((finalJob.status === 'ready' && finalJob.export_status === 'ready') || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh — keep parent so user can view previous versions
                  setSavedPresentationJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh — delete orphaned error job
                  presentationsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
                    console.warn('[Studio] Failed to delete failed edit job', err);
                  });
                } else {
                  setSavedPresentationJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingPresentation(false);
              setCurrentPresentationJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved presentation jobs');
    }
  };

  /**
   * Handle presentation generation
   * Educational Note: Presentations auto-open in viewer after generation
   */
  const handlePresentationGeneration = async (signal: StudioSignal) => {
    setIsGeneratingPresentation(true);
    setCurrentPresentationJob(null);

    try {
      const sourceId = signal.sources[0]?.source_id || "";

      // Start presentation generation
      const startResponse = await presentationsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start presentation generation');
        return;
      }

      // Poll for completion (including PPTX export)
      const finalJob = await presentationsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentPresentationJob(job)
      );

      if (finalJob.status === 'ready' && finalJob.export_status === 'ready') {
        setSavedPresentationJobs((prev) => [finalJob, ...prev]);
        // Open presentation in viewer automatically
        setViewingPresentationJob(finalJob);
        showSuccess('Presentation generated successfully!');
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Presentation generation failed');
      }
    } catch (error) {
      log.error({ err: error }, 'LPresentation generationE failed');
      showError('Presentation generation failed');
    } finally {
      setIsGeneratingPresentation(false);
      setCurrentPresentationJob(null);
    }
  };

  /**
   * Download presentation as PPTX
   */
  const downloadPresentation = (jobId: string) => {
    // API_BASE_URL already includes /api/v1 path, getAuthUrl adds JWT for browser element auth
    const downloadUrl = presentationsAPI.getDownloadUrl(projectId, jobId, 'pptx');
    const link = document.createElement('a');
    link.href = getAuthUrl(downloadUrl);
    link.click();
  };

  /**
   * Download presentation source as ZIP
   */
  const downloadPresentationSource = (jobId: string) => {
    // API_BASE_URL already includes /api/v1 path, getAuthUrl adds JWT for browser element auth
    const downloadUrl = presentationsAPI.getDownloadUrl(projectId, jobId, 'zip');
    const link = document.createElement('a');
    link.href = getAuthUrl(downloadUrl);
    link.click();
  };

  const handlePresentationDelete = async (jobId: string) => {
    try {
      await presentationsAPI.deleteJob(projectId, jobId);
      setSavedPresentationJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (error) {
      log.error({ err: error }, 'failed to delete presentation job');
    }
  };

  const handlePresentationEdit = async (parentJob: PresentationJob, editInstructions: string) => {
    if (isGeneratingPresentation) return;
    setIsGeneratingPresentation(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await presentationsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Presentation edit: API start failed', startResponse);
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError(startResponse.error || 'Failed to start presentation edit.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        showError(startResponse.error || 'Failed to start presentation edit.');
        return;
      }

      // Only close modal once we know generation started
      setCurrentPresentationJob(null);
      setViewingPresentationJob(null);

      showSuccess('Editing presentation...');

      const finalJob = await presentationsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentPresentationJob(job)
      );

      setCurrentPresentationJob(finalJob);

      if (finalJob.status === 'ready' && finalJob.export_status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Presentation edited: ${finalJob.presentation_title || 'Presentation'}`);
        setSavedPresentationJobs((prev) => [finalJob, ...prev]);
        setViewingPresentationJob(finalJob); // Reopen modal with new job
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Presentation edit failed.');
        setViewingPresentationJob(parentJob); // Restore parent modal so user can retry
        presentationsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
          console.warn('[Studio] Failed to delete failed edit job', err);
        });
      }
    } catch (error) {
      console.error('[Studio] Presentation edit: failed', error);
      log.error({ err: error }, 'Presentation edit failed');
      showError(error instanceof Error ? error.message : 'Presentation edit failed.');
      setViewingPresentationJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingPresentation(false);
      setCurrentPresentationJob(null);
    }
  };

  return {
    savedPresentationJobs,
    currentPresentationJob,
    isGeneratingPresentation,
    viewingPresentationJob,
    setViewingPresentationJob,
    configError,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingPresentationJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handlePresentationGeneration,
    handlePresentationEdit,
    handlePresentationDelete,
    downloadPresentation,
    downloadPresentationSource,
  };
};
