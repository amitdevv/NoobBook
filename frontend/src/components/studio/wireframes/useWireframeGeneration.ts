/**
 * useWireframeGeneration Hook
 * Educational Note: Manages Excalidraw wireframe generation from sources.
 * Creates UI/UX wireframes for visual prototyping.
 */

import { useState, useRef } from 'react';
import { wireframesAPI, type WireframeJob } from '@/lib/api/studio/wireframes';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('wireframe-generation');

export const useWireframeGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedWireframeJobs, setSavedWireframeJobs] = useState<WireframeJob[]>([]);
  const [currentWireframeJob, setCurrentWireframeJob] = useState<WireframeJob | null>(null);
  const [isGeneratingWireframe, setIsGeneratingWireframe] = useState(false);
  const pollingRef = useRef(false);
  const [viewingWireframeJob, setViewingWireframeJob] = useState<WireframeJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSavedJobs = async () => {
    try {
      const response = await wireframesAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        const finishedJobs = response.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedWireframeJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingWireframe && !pollingRef.current) {
          const inProgressJob = response.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingWireframe(true);
            setCurrentWireframeJob(inProgressJob);
            try {
              const finalJob = await wireframesAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentWireframeJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh -- keep parent so user can view previous versions
                  setSavedWireframeJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh -- orphaned error job filtered by backend list
                } else {
                  setSavedWireframeJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed -- job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingWireframe(false);
              setCurrentWireframeJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved wireframe jobs');
    }
  };

  const handleWireframeGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;

    setIsGeneratingWireframe(true);
    setCurrentWireframeJob(null);

    try {
      const startResponse = await wireframesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError(startResponse.error || 'Failed to start wireframe generation.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        showError(startResponse.error || 'Failed to start wireframe generation.');
        setIsGeneratingWireframe(false);
        return;
      }

      showSuccess(`Generating wireframe for ${startResponse.source_name}...`);

      const finalJob = await wireframesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWireframeJob(job)
      );

      setCurrentWireframeJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated wireframe: ${finalJob.title} (${finalJob.element_count} elements)`);
        setSavedWireframeJobs((prev) => [finalJob, ...prev]);
        setViewingWireframeJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Wireframe generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'wireframe generation failed');
      showError(error instanceof Error ? error.message : 'Wireframe generation failed.');
    } finally {
      setIsGeneratingWireframe(false);
      setCurrentWireframeJob(null);
    }
  };

  const handleWireframeEdit = async (parentJob: WireframeJob, editInstructions: string) => {
    if (isGeneratingWireframe) return;
    setIsGeneratingWireframe(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await wireframesAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start wireframe edit.');
        return;
      }

      // Only close modal once we know generation started
      setCurrentWireframeJob(null);
      setViewingWireframeJob(null);

      showSuccess('Editing wireframe...');

      const finalJob = await wireframesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWireframeJob(job)
      );

      setCurrentWireframeJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Wireframe edited: ${finalJob.title || 'Wireframe'}`);
        setSavedWireframeJobs((prev) => [finalJob, ...prev]);
        // Only reopen if user hasn't navigated to another wireframe
        setViewingWireframeJob((current) => current === null ? finalJob : current);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Wireframe edit failed.');
        setViewingWireframeJob(parentJob); // Restore parent modal so user can retry
      }
    } catch (error) {
      log.error({ err: error }, 'wireframe edit failed');
      showError(error instanceof Error ? error.message : 'Wireframe edit failed.');
      setViewingWireframeJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingWireframe(false);
      setCurrentWireframeJob(null);
      // Note: pendingEdit is intentionally NOT cleared here -- on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
    }
  };

  /**
   * Delete a wireframe job from the backend and remove from local state
   */
  const handleWireframeDelete = async (jobId: string) => {
    try {
      await wireframesAPI.deleteJob(projectId, jobId);
      setSavedWireframeJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (error) {
      log.error({ err: error }, 'failed to delete wireframe job');
    }
  };

  return {
    savedWireframeJobs,
    currentWireframeJob,
    isGeneratingWireframe,
    viewingWireframeJob,
    setViewingWireframeJob,
    configError,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingWireframeJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleWireframeGeneration,
    handleWireframeEdit,
    handleWireframeDelete,
  };
};
