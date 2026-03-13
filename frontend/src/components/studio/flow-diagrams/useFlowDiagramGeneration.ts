/**
 * useFlowDiagramGeneration Hook
 * Educational Note: Manages Mermaid flow diagram generation from sources.
 * Creates various diagram types (flowchart, sequence, state, ER, etc.) for visualization.
 */

import { useState, useRef } from 'react';
import { flowDiagramsAPI, type FlowDiagramJob } from '@/lib/api/studio';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('flow-diagram-generation');

export const useFlowDiagramGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedFlowDiagramJobs, setSavedFlowDiagramJobs] = useState<FlowDiagramJob[]>([]);
  const [currentFlowDiagramJob, setCurrentFlowDiagramJob] = useState<FlowDiagramJob | null>(null);
  const [isGeneratingFlowDiagram, setIsGeneratingFlowDiagram] = useState(false);
  const pollingRef = useRef(false);
  const [viewingFlowDiagramJob, setViewingFlowDiagramJob] = useState<FlowDiagramJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSavedJobs = async () => {
    try {
      const response = await flowDiagramsAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        const finishedJobs = response.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedFlowDiagramJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingFlowDiagram && !pollingRef.current) {
          const inProgressJob = response.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingFlowDiagram(true);
            setCurrentFlowDiagramJob(inProgressJob);
            try {
              const finalJob = await flowDiagramsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentFlowDiagramJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh -- keep parent so user can view previous versions
                  setSavedFlowDiagramJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh -- orphaned error job filtered by backend list
                } else {
                  setSavedFlowDiagramJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed -- job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingFlowDiagram(false);
              setCurrentFlowDiagramJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved flow diagram jobs');
    }
  };

  const handleFlowDiagramGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;

    setIsGeneratingFlowDiagram(true);
    setCurrentFlowDiagramJob(null);

    try {
      const startResponse = await flowDiagramsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError(startResponse.error || 'Failed to start flow diagram generation.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        showError(startResponse.error || 'Failed to start flow diagram generation.');
        setIsGeneratingFlowDiagram(false);
        return;
      }

      showSuccess(`Generating flow diagram for ${startResponse.source_name}...`);

      const finalJob = await flowDiagramsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlowDiagramJob(job)
      );

      setCurrentFlowDiagramJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.diagram_type} diagram: ${finalJob.title}`);
        setSavedFlowDiagramJobs((prev) => [finalJob, ...prev]);
        setViewingFlowDiagramJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flow diagram generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'flow diagram generation failed');
      showError(error instanceof Error ? error.message : 'Flow diagram generation failed.');
    } finally {
      setIsGeneratingFlowDiagram(false);
      setCurrentFlowDiagramJob(null);
    }
  };

  const handleFlowDiagramEdit = async (parentJob: FlowDiagramJob, editInstructions: string) => {
    if (isGeneratingFlowDiagram) return;
    setIsGeneratingFlowDiagram(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await flowDiagramsAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start flow diagram edit.');
        return;
      }

      // Only close modal once we know generation started
      setCurrentFlowDiagramJob(null);
      setViewingFlowDiagramJob(null);

      showSuccess('Editing flow diagram...');

      const finalJob = await flowDiagramsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentFlowDiagramJob(job)
      );

      setCurrentFlowDiagramJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Flow diagram edited: ${finalJob.title || 'Flow Diagram'}`);
        setSavedFlowDiagramJobs((prev) => [finalJob, ...prev]);
        // Only reopen if user hasn't navigated to another diagram
        setViewingFlowDiagramJob((current) => current === null ? finalJob : current);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Flow diagram edit failed.');
        setViewingFlowDiagramJob(parentJob); // Restore parent modal so user can retry
      }
    } catch (error) {
      log.error({ err: error }, 'flow diagram edit failed');
      showError(error instanceof Error ? error.message : 'Flow diagram edit failed.');
      setViewingFlowDiagramJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingFlowDiagram(false);
      setCurrentFlowDiagramJob(null);
      // Note: pendingEdit is intentionally NOT cleared here -- on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
      // It IS cleared on success (see the ready branch above).
    }
  };

  return {
    savedFlowDiagramJobs,
    currentFlowDiagramJob,
    isGeneratingFlowDiagram,
    viewingFlowDiagramJob,
    setViewingFlowDiagramJob,
    configError,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingFlowDiagramJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleFlowDiagramGeneration,
    handleFlowDiagramEdit,
  };
};
