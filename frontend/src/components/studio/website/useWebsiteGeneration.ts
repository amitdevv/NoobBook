/**
 * useWebsiteGeneration Hook
 * Educational Note: Custom hook for website generation logic.
 * Handles state management, API calls, and polling.
 */

import { useState, useRef } from 'react';
import { websitesAPI, type WebsiteJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import { useToast } from '../../ui/use-toast';
import type { StudioSignal } from '../types';
import { createLogger } from '@/lib/logger';

const log = createLogger('website-generation');

export const useWebsiteGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  // State
  const [savedWebsiteJobs, setSavedWebsiteJobs] = useState<WebsiteJob[]>([]);
  const [currentWebsiteJob, setCurrentWebsiteJob] = useState<WebsiteJob | null>(null);
  const [isGeneratingWebsite, setIsGeneratingWebsite] = useState(false);
  const pollingRef = useRef(false);
  const [viewingWebsiteJob, setViewingWebsiteJob] = useState<WebsiteJob | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  /**
   * Load saved website jobs from backend
   */
  const loadSavedJobs = async () => {
    try {
      const websiteResponse = await websitesAPI.listJobs(projectId);
      if (websiteResponse.success && websiteResponse.jobs) {
        const finishedJobs = websiteResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedWebsiteJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingWebsite && !pollingRef.current) {
          const inProgressJob = websiteResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingWebsite(true);
            setCurrentWebsiteJob(inProgressJob);
            try {
              const finalJob = await websitesAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentWebsiteJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh — keep parent so user can view previous versions
                  setSavedWebsiteJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh — delete orphaned error job
                  websitesAPI.deleteJob(projectId, finalJob.id).catch((err) => {
                    console.warn('[Studio] Failed to delete failed edit job', err);
                  });
                } else {
                  setSavedWebsiteJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingWebsite(false);
              setCurrentWebsiteJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved website jobs');
    }
  };

  /**
   * Handle website generation
   * Educational Note: Websites open in new window automatically after generation
   */
  const handleWebsiteGeneration = async (signal: StudioSignal) => {
    setIsGeneratingWebsite(true);
    setCurrentWebsiteJob(null);

    try {
      const sourceId = signal.sources[0]?.source_id || "";

      // Start website generation
      const startResponse = await websitesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start website generation');
        return;
      }

      // Poll for completion
      const finalJob = await websitesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWebsiteJob(job)
      );

      if (finalJob.status === 'ready') {
        setSavedWebsiteJobs((prev) => [finalJob, ...prev]);
        // Open website in modal viewer automatically
        setViewingWebsiteJob(finalJob);
        showSuccess('Website generated successfully!');
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Website generation failed');
      }
    } catch (error) {
      log.error({ err: error }, 'LWebsite generationE failed');
      showError('Website generation failed');
    } finally {
      setIsGeneratingWebsite(false);
      setCurrentWebsiteJob(null);
    }
  };

  /**
   * Open website in modal viewer
   */
  const openWebsite = (jobId: string) => {
    const job = savedWebsiteJobs.find((j) => j.id === jobId);
    if (job) {
      setViewingWebsiteJob(job);
    }
  };

  /**
   * Delete a website job
   */
  const handleWebsiteDelete = async (jobId: string) => {
    try {
      await websitesAPI.deleteJob(projectId, jobId);
      setSavedWebsiteJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (error) {
      log.error({ err: error }, 'failed to delete website job');
    }
  };

  /**
   * Download website as ZIP
   */
  const downloadWebsite = (jobId: string) => {
    const downloadUrl = websitesAPI.getDownloadUrl(projectId, jobId);
    const link = document.createElement('a');
    link.href = getAuthUrl(downloadUrl);
    link.click();
  };

  const handleWebsiteEdit = async (parentJob: WebsiteJob, editInstructions: string) => {
    if (isGeneratingWebsite) return;
    setIsGeneratingWebsite(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await websitesAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Website edit: API start failed', startResponse);
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError(startResponse.error || 'Failed to start website edit.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        showError(startResponse.error || 'Failed to start website edit.');
        return;
      }

      // Only close modal once we know generation started
      setCurrentWebsiteJob(null);
      setViewingWebsiteJob(null);

      showSuccess('Editing website...');

      const finalJob = await websitesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentWebsiteJob(job)
      );

      setCurrentWebsiteJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Website edited: ${finalJob.site_name || 'Website'}`);
        setSavedWebsiteJobs((prev) => [finalJob, ...prev]);
        setViewingWebsiteJob(finalJob); // Reopen modal with new job
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Website edit failed.');
        setViewingWebsiteJob(parentJob); // Restore parent modal so user can retry
        websitesAPI.deleteJob(projectId, finalJob.id).catch((err) => {
          console.warn('[Studio] Failed to delete failed edit job', err);
        });
      }
    } catch (error) {
      console.error('[Studio] Website edit: failed', error);
      log.error({ err: error }, 'Website edit failed');
      showError(error instanceof Error ? error.message : 'Website edit failed.');
      setViewingWebsiteJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingWebsite(false);
      setCurrentWebsiteJob(null);
    }
  };

  return {
    savedWebsiteJobs,
    currentWebsiteJob,
    isGeneratingWebsite,
    viewingWebsiteJob,
    setViewingWebsiteJob,
    configError,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingWebsiteJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleWebsiteGeneration,
    handleWebsiteEdit,
    handleWebsiteDelete,
    openWebsite,
    downloadWebsite,
  };
};
