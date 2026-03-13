/**
 * useQuizGeneration Hook
 * Educational Note: Manages quiz generation from sources.
 * Creates interactive quiz questions with multiple choice answers.
 * Supports iterative editing of existing quizzes.
 */

import { useState, useRef } from 'react';
import { quizzesAPI, type QuizJob } from '@/lib/api/studio';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('quiz-generation');

export const useQuizGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedQuizJobs, setSavedQuizJobs] = useState<QuizJob[]>([]);
  const [currentQuizJob, setCurrentQuizJob] = useState<QuizJob | null>(null);
  const [isGeneratingQuiz, setIsGeneratingQuiz] = useState(false);
  const pollingRef = useRef(false);
  const [viewingQuizJob, setViewingQuizJob] = useState<QuizJob | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);

  const loadSavedJobs = async () => {
    try {
      const quizResponse = await quizzesAPI.listJobs(projectId);
      if (quizResponse.success && quizResponse.jobs) {
        const finishedJobs = quizResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedQuizJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingQuiz && !pollingRef.current) {
          const inProgressJob = quizResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingQuiz(true);
            setCurrentQuizJob(inProgressJob);
            try {
              const finalJob = await quizzesAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentQuizJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh — keep parent so user can view previous versions
                  setSavedQuizJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh — delete orphaned error job, parent stays
                  quizzesAPI.deleteJob(projectId, finalJob.id).catch((err) => {
                    console.warn('[Studio] Failed to delete failed edit job', err);
                  });
                } else {
                  setSavedQuizJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingQuiz(false);
              setCurrentQuizJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved quiz jobs');
    }
  };

  const handleQuizGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id;
    if (!sourceId) {
      showError('No source specified for quiz generation.');
      return;
    }

    setIsGeneratingQuiz(true);
    setCurrentQuizJob(null);

    try {
      const startResponse = await quizzesAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start quiz generation.');
        setIsGeneratingQuiz(false);
        return;
      }

      showSuccess(`Generating quiz for ${startResponse.source_name}...`);

      const finalJob = await quizzesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentQuizJob(job)
      );

      setCurrentQuizJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Generated ${finalJob.question_count} quiz questions!`);
        setSavedQuizJobs((prev) => [finalJob, ...prev]);
        setViewingQuizJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Quiz generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'Quiz generation failed');
      showError(error instanceof Error ? error.message : 'Quiz generation failed.');
    } finally {
      setIsGeneratingQuiz(false);
      setCurrentQuizJob(null);
    }
  };

  /**
   * Handle quiz edit — refine existing questions based on user instructions
   */
  const handleQuizEdit = async (parentJob: QuizJob, editInstructions: string) => {
    if (isGeneratingQuiz) return;
    setIsGeneratingQuiz(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });

    try {
      const startResponse = await quizzesAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Quiz edit: API start failed', startResponse);
        showError(startResponse.error || 'Failed to start quiz edit.');
        return;
      }

      // Only close modal once we know generation started
      setCurrentQuizJob(null);
      setViewingQuizJob(null);

      showSuccess('Editing quiz...');

      const finalJob = await quizzesAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentQuizJob(job)
      );

      setCurrentQuizJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess(`Quiz edited: ${finalJob.question_count} questions`);
        setSavedQuizJobs((prev) => [finalJob, ...prev]);
        setViewingQuizJob(finalJob); // Reopen modal with new job
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Quiz edit failed.');
        setViewingQuizJob(parentJob); // Restore parent modal so user can retry
        // Delete the failed edit job so it doesn't pollute the list on refresh
        quizzesAPI.deleteJob(projectId, finalJob.id).catch((err) => {
          console.warn('[Studio] Failed to delete failed edit job', err);
        });
      }
    } catch (error) {
      console.error('[Studio] Quiz edit: failed', error);
      log.error({ err: error }, 'Quiz edit failed');
      showError(error instanceof Error ? error.message : 'Quiz edit failed.');
      setViewingQuizJob(parentJob); // Restore parent modal so user can retry
    } finally {
      setIsGeneratingQuiz(false);
      setCurrentQuizJob(null);
      // Note: pendingEdit is intentionally NOT cleared here — on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
      // It IS cleared on success (see the `if (finalJob.status === 'ready')` branch above).
    }
  };

  return {
    savedQuizJobs,
    currentQuizJob,
    isGeneratingQuiz,
    viewingQuizJob,
    setViewingQuizJob,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === viewingQuizJob?.id ? pendingEdit.input : '',
    loadSavedJobs,
    handleQuizGeneration,
    handleQuizEdit,
  };
};
