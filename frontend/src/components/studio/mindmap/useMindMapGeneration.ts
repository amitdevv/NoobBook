/**
 * useMindMapGeneration Hook
 * Educational Note: Manages mind map generation from sources.
 * Creates hierarchical node structures for visualization.
 * Supports iterative editing of existing mind maps.
 */

import { useState, useRef } from 'react';
import { mindMapsAPI, type MindMapJob } from '@/lib/api/studio';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('mind-map-generation');

export const useMindMapGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedMindMapJobs, setSavedMindMapJobs] = useState<MindMapJob[]>([]);
  const [currentMindMapJob, setCurrentMindMapJob] = useState<MindMapJob | null>(null);
  const [isGeneratingMindMap, setIsGeneratingMindMap] = useState(false);
  const pollingRef = useRef(false);
  const [viewingMindMapJob, setViewingMindMapJob] = useState<MindMapJob | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);

  const loadSavedJobs = async () => {
    try {
      const mindMapResponse = await mindMapsAPI.listJobs(projectId);
      if (mindMapResponse.success && mindMapResponse.jobs) {
        const finishedJobs = mindMapResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedMindMapJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingMindMap && !pollingRef.current) {
          const inProgressJob = mindMapResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingMindMap(true);
            setCurrentMindMapJob(inProgressJob);
            try {
              const finalJob = await mindMapsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentMindMapJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh — keep parent so user can view previous versions
                  setSavedMindMapJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh — delete orphaned error job, parent stays
                  mindMapsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
                    console.warn('[Studio] Failed to delete failed edit job', err);
                  });
                } else {
                  setSavedMindMapJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingMindMap(false);
              setCurrentMindMapJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved mind map jobs');
    }
  };

  const handleMindMapGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id || "";

    setIsGeneratingMindMap(true);
    setCurrentMindMapJob(null);

    try {
      const startResponse = await mindMapsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start mind map generation.');
        setIsGeneratingMindMap(false);
        return;
      }

      showSuccess(`Generating mind map for ${startResponse.source_name}...`);

      const finalJob = await mindMapsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentMindMapJob(job)
      );

      setCurrentMindMapJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated mind map with ${finalJob.node_count} nodes!`);
        setSavedMindMapJobs((prev) => [finalJob, ...prev]);
        setViewingMindMapJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Mind map generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'Mind map generation failed');
      showError(error instanceof Error ? error.message : 'Mind map generation failed.');
    } finally {
      setIsGeneratingMindMap(false);
      setCurrentMindMapJob(null);
    }
  };

  /**
   * Handle mind map edit — refine existing nodes based on user instructions
   */
  const handleMindMapEdit = async (parentJob: MindMapJob, editInstructions: string) => {
    if (isGeneratingMindMap) return;
    setIsGeneratingMindMap(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await mindMapsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Mind map edit: API start failed', startResponse);
        showError(startResponse.error || 'Failed to start mind map edit.');
        setViewingMindMapJob(parentJob);
        return;
      }

      // Only close modal once we know generation started
      setCurrentMindMapJob(null);
      setViewingMindMapJob(null);

      showSuccess('Editing mind map...');

      const finalJob = await mindMapsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentMindMapJob(job)
      );

      setCurrentMindMapJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Mind map edited: ${finalJob.node_count} nodes`);
        setSavedMindMapJobs((prev) => [finalJob, ...prev]);
        setViewingMindMapJob(finalJob); // Reopen modal with new job
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Mind map edit failed.');
        setViewingMindMapJob(parentJob); // Restore parent modal so user can retry
        // Delete the failed edit job so it doesn't pollute the list on refresh
        mindMapsAPI.deleteJob(projectId, finalJob.id).catch((err) => {
          console.warn('[Studio] Failed to delete failed edit job', err);
        });
      }
    } catch (error) {
      console.error('[Studio] Mind map edit: failed', error);
      log.error({ err: error }, 'Mind map edit failed');
      showError(error instanceof Error ? error.message : 'Mind map edit failed.');
      setViewingMindMapJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingMindMap(false);
      setCurrentMindMapJob(null);
      // Note: pendingEdit is intentionally NOT cleared here — on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
      // It IS cleared on success (see the `if (finalJob.status === 'ready')` branch above).
    }
  };

  /**
   * Delete a mind map job
   */
  const handleMindMapDelete = async (jobId: string) => {
    try {
      await mindMapsAPI.deleteJob(projectId, jobId);
      setSavedMindMapJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (error) {
      log.error({ err: error }, 'failed to delete mind map job');
    }
  };

  return {
    savedMindMapJobs,
    currentMindMapJob,
    isGeneratingMindMap,
    viewingMindMapJob,
    setViewingMindMapJob,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingMindMapJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleMindMapGeneration,
    handleMindMapEdit,
    handleMindMapDelete,
  };
};
