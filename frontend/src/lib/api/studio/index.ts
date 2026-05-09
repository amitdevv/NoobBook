/**
 * Studio API - Re-exports all studio feature APIs
 * Educational Note: Centralized exports for clean imports across the app.
 *
 * Import usage:
 *   import { audioAPI, JobStatus, checkGeminiStatus } from '@/lib/api/studio';
 */

import axios from 'axios';
import { API_BASE_URL } from '../client';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-api');

// Shared types
//
// `'cancelled'` is the user-initiated terminal state set by the cancel
// route (POST /projects/<id>/studio/jobs/<id>/cancel). Every per-agent
// pollJobStatus must treat it as terminal so the polling loop exits and
// the section UI flips to the CancelledJobRow affordance with a
// "Generate again" action.
export type JobStatus = 'pending' | 'processing' | 'ready' | 'error' | 'cancelled';

/** Response shape from the studio cancel route. */
export interface CancelStudioJobResponse {
  success: boolean;
  /** Final status the row landed on. `'ready'` means the worker beat
   *  the cancel and the result was preserved. */
  status: JobStatus;
  /** Set when the worker finished `ready` after the user clicked Stop
   *  but before this route ran — UI should roll its optimistic
   *  "cancelling" state back and surface a "kept the result" pill. */
  late?: boolean;
  job?: Record<string, unknown>;
  error?: string;
}

/**
 * Cancel an in-flight studio generation. Race-safe — see
 * `backend/app/api/studio/job_actions.py` for the four status branches.
 */
export async function cancelStudioJob(
  projectId: string,
  jobId: string,
): Promise<CancelStudioJobResponse> {
  const response = await axios.post<CancelStudioJobResponse>(
    `${API_BASE_URL}/projects/${projectId}/studio/jobs/${jobId}/cancel`,
  );
  return response.data;
}

/**
 * Response for API status checks (TTS, Gemini, etc.)
 */
export interface APIStatusResponse {
  success: boolean;
  configured: boolean;
  message?: string;
}

/**
 * Check if Gemini API is configured
 * Educational Note: Shared utility for features that use Gemini Imagen (ads, social posts, infographics, emails)
 */
export async function checkGeminiStatus(): Promise<APIStatusResponse> {
  try {
    const response = await axios.get(`${API_BASE_URL}/studio/gemini/status`);
    return response.data;
  } catch (error) {
    log.error({ err: error }, 'failed to check Gemini status');
    return { success: false, configured: false };
  }
}

// Re-export all feature APIs and their types
export * from './audio';
export * from './ads';
export * from './flash-cards';
export * from './mind-maps';
export * from './quizzes';
export * from './social-posts';
export * from './infographics';
export * from './emails';
export * from './components';
export * from './videos';
export * from './websites';
export * from './flow-diagrams';
export * from './wireframes';
export * from './presentations';
export * from './prds';
export * from './marketingStrategies';
export * from './blogs';
export * from './businessReports';
