/**
 * useBlogGeneration Hook
 * Educational Note: Manages blog post generation with SEO optimization.
 * Blog posts are created by an agent that plans, generates images, and writes markdown.
 */

import { useState, useRef } from 'react';
import { blogsAPI, type BlogJob, type BlogType } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('blog-generation');

// Extend StudioSignal for blog-specific fields
interface BlogSignal extends StudioSignal {
  target_keyword?: string;
  blog_type?: BlogType;
}

export const useBlogGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedBlogJobs, setSavedBlogJobs] = useState<BlogJob[]>([]);
  const [currentBlogJob, setCurrentBlogJob] = useState<BlogJob | null>(null);
  const [isGeneratingBlog, setIsGeneratingBlog] = useState(false);
  const pollingRef = useRef(false);
  const [viewingBlogJob, setViewingBlogJob] = useState<BlogJob | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const configErrorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadSavedJobs = async () => {
    try {
      const response = await blogsAPI.listJobs(projectId);
      if (response.success && response.jobs) {
        const finishedJobs = response.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedBlogJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingBlog && !pollingRef.current) {
          const inProgressJob = response.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingBlog(true);
            setCurrentBlogJob(inProgressJob);
            try {
              const finalJob = await blogsAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentBlogJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                setSavedBlogJobs((prev) => [finalJob, ...prev]);
              }
            } catch {
              // Polling failed — job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingBlog(false);
              setCurrentBlogJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved blog jobs');
    }
  };

  const handleBlogGeneration = async (signal: BlogSignal) => {
    // source_id is optional — blog can be generated from direction alone
    const sources = signal.sources || [];
    const sourceId = sources[0]?.source_id || '';

    setIsGeneratingBlog(true);
    setCurrentBlogJob(null);

    try {
      // Extract blog-specific fields from signal
      const targetKeyword = signal.target_keyword || '';
      const blogType = signal.blog_type || 'how_to_guide';

      const startResponse = await blogsAPI.startGeneration(
        projectId,
        sourceId,
        signal.direction,
        targetKeyword,
        blogType
      );

      if (!startResponse.success || !startResponse.job_id) {
        console.error('[Studio] Blog: API start failed', startResponse);
        if (configErrorTimer.current) clearTimeout(configErrorTimer.current);
        setConfigError(startResponse.error || 'Failed to start blog post generation.');
        configErrorTimer.current = setTimeout(() => setConfigError(null), 10000);
        showError(startResponse.error || 'Failed to start blog post generation.');
        setIsGeneratingBlog(false);
        return;
      }

      showSuccess('Generating blog post...');

      const finalJob = await blogsAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentBlogJob(job)
      );

      setCurrentBlogJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess(`Blog post generated: ${finalJob.title || 'Blog Post'}`);
        setSavedBlogJobs((prev) => [finalJob, ...prev]);
        setViewingBlogJob(finalJob); // Open modal to view
      } else if (finalJob.status === 'error') {
        showError(finalJob.error_message || 'Blog post generation failed.');
      }
    } catch (error) {
      console.error('[Studio] Blog: generation failed', error);
      log.error({ err: error }, 'Blog post generation failed');
      showError(error instanceof Error ? error.message : 'Blog post generation failed.');
    } finally {
      setIsGeneratingBlog(false);
      setCurrentBlogJob(null);
    }
  };

  const downloadBlog = (jobId: string) => {
    const url = blogsAPI.getDownloadUrl(projectId, jobId);
    window.open(getAuthUrl(url), '_blank');
  };

  return {
    savedBlogJobs,
    currentBlogJob,
    isGeneratingBlog,
    viewingBlogJob,
    setViewingBlogJob,
    configError,
    loadSavedJobs,
    handleBlogGeneration,
    downloadBlog,
  };
};
