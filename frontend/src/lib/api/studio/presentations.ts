/**
 * Presentations API
 * Educational Note: Handles AI-generated PowerPoint presentations.
 * Uses an agentic approach for HTML slides, then exports to PPTX.
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import type { JobStatus } from './index';
import { listStudioJobsByType } from './jobGroups';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-presentations-api');

/**
 * Presentation slide metadata
 */
export interface PresentationSlide {
  filename: string;
  title: string;
  type: string;
}

/**
 * Presentation design system
 */
export interface PresentationDesignSystem {
  primary_color: string;
  secondary_color: string;
  accent_color?: string;
  background_color: string;
  text_color: string;
  font_family?: string;
}

/**
 * Planned slide from the agent
 */
export interface PlannedSlide {
  slide_number: number;
  slide_type: string;
  title: string;
  key_points?: string[];
}

/**
 * Presentation generation job
 */
export interface PresentationJob {
  id: string;
  source_id: string;
  source_name: string;
  direction: string;
  status: JobStatus;
  status_message: string;
  error_message: string | null;
  // Edit lineage
  parent_job_id: string | null;
  edit_instructions: string | null;

  // Plan
  presentation_title: string | null;
  presentation_type: 'business' | 'educational' | 'pitch' | 'report' | 'training' | 'marketing' | 'technical' | null;
  target_audience: string | null;
  planned_slides: PlannedSlide[];
  design_system: PresentationDesignSystem | null;
  style_notes: string | null;

  // Generated content
  files: string[];
  slide_files: string[];
  slides_created: number;
  slides_metadata: PresentationSlide[];
  total_slides: number;
  summary: string | null;
  design_notes: string | null;

  // Export
  screenshots: Array<{
    slide_file: string;
    screenshot_file: string;
    screenshot_path: string;
    success: boolean;
  }>;
  pptx_file: string | null;
  pptx_filename: string | null;
  export_status: 'pending' | 'exporting' | 'ready' | 'error' | null;

  // URLs
  preview_url: string | null;
  download_url: string | null;

  // Metadata
  iterations: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

/**
 * Response from starting presentation generation
 */
export interface StartPresentationResponse {
  success: boolean;
  job_id?: string;
  status?: string;
  message?: string;
  error?: string;
}

/**
 * Response from getting presentation job status
 */
export interface PresentationJobStatusResponse {
  success: boolean;
  job?: PresentationJob;
  error?: string;
}

/**
 * Response from listing presentation jobs
 */
export interface ListPresentationJobsResponse {
  success: boolean;
  jobs: PresentationJob[];
  error?: string;
}

/**
 * Response from preview endpoint
 */
export interface PresentationPreviewResponse {
  success: boolean;
  total_slides: number;
  current_slide: number;
  slide_file: string;
  slide_url: string;
  presentation_title: string;
  export_status: string | null;
  pptx_available: boolean;
  error?: string;
}

/**
 * Presentations API
 */
export const presentationsAPI = {
  /**
   * Start presentation generation or edit (background task)
   * Educational Note: Non-blocking - returns immediately with job_id
   */
  async startGeneration(
    projectId: string,
    sourceId: string,
    direction?: string,
    parentJobId?: string,
    editInstructions?: string
  ): Promise<StartPresentationResponse> {
    try {
      const body: Record<string, unknown> = {
        source_id: sourceId,
        direction: direction || '',
      };
      if (parentJobId) body.parent_job_id = parentJobId;
      if (editInstructions) body.edit_instructions = editInstructions;

      const response = await axios.post(
        `${API_BASE_URL}/projects/${projectId}/studio/presentation`,
        body
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to start presentation generation');
      throw error;
    }
  },

  /**
   * Get presentation job status
   */
  async getJobStatus(projectId: string, jobId: string): Promise<PresentationJobStatusResponse> {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/presentation-jobs/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get presentation job status');
      throw error;
    }
  },

  /**
   * List all presentation jobs for a project, optionally filtered by source
   */
  async listJobs(projectId: string, sourceId?: string): Promise<ListPresentationJobsResponse> {
    return listStudioJobsByType<PresentationJob>(projectId, 'presentation', sourceId);
  },

  /**
   * Get preview info for a presentation
   */
  async getPreview(projectId: string, jobId: string, slideNum?: number): Promise<PresentationPreviewResponse> {
    try {
      const params = slideNum ? { slide: slideNum } : {};
      const response = await axios.get(
        `${API_BASE_URL}/projects/${projectId}/studio/presentations/${jobId}/preview`,
        { params }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to get presentation preview');
      throw error;
    }
  },

  /**
   * Get the slide URL for iframe viewing
   */
  getSlideUrl(projectId: string, jobId: string, slideFile: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/presentations/${jobId}/slides/${slideFile}`;
  },

  /**
   * Get screenshot URL for image viewing
   * Educational Note: Screenshots are PNG images captured by Playwright at 1920x1080
   */
  getScreenshotUrl(projectId: string, jobId: string, screenshotFile: string): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/presentations/${jobId}/screenshots/${screenshotFile}`;
  },

  /**
   * Get the download URL for PPTX
   */
  getDownloadUrl(projectId: string, jobId: string, format: 'pptx' | 'zip' = 'pptx'): string {
    return `${API_BASE_URL}/projects/${projectId}/studio/presentations/${jobId}/download?format=${format}`;
  },

  /**
   * Delete a presentation job
   */
  async deleteJob(projectId: string, jobId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await axios.delete(
        `${API_BASE_URL}/projects/${projectId}/studio/presentations/${jobId}`
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        return error.response.data;
      }
      log.error({ err: error }, 'failed to delete presentation job');
      throw error;
    }
  },

  /**
   * Poll presentation job status until complete or error
   */
  async pollJobStatus(
    projectId: string,
    jobId: string,
    onProgress?: (job: PresentationJob) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 250  // Presentations can take longer (many slides + export)
  ): Promise<PresentationJob> {
    let attempts = 0;
    let currentInterval = intervalMs;

    while (attempts < maxAttempts) {
      const response = await this.getJobStatus(projectId, jobId);

      if (!response.success || !response.job) {
        throw new Error(response.error || 'Failed to get job status');
      }

      const job = response.job;

      if (onProgress) {
        onProgress(job);
      }

      // Check if fully complete (including PPTX export)
      if (job.status === 'ready' && job.export_status === 'ready') {
        return job;
      }

      if (job.status === 'error') {
        return job;
      }

      await new Promise((resolve) => setTimeout(resolve, currentInterval));

      attempts++;

      if (attempts > 5 && currentInterval < 5000) {
        currentInterval = Math.min(currentInterval * 1.2, 5000);
      }
    }

    throw new Error('Presentation generation timed out');
  },
};
