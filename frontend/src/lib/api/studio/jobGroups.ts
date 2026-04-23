import axios from 'axios';

import { API_BASE_URL } from '../client';
import { createLogger } from '@/lib/logger';

const log = createLogger('studio-job-groups-api');

interface GroupedStudioJobsResponse {
  success: boolean;
  jobs_by_type?: Record<string, unknown[]>;
  count: number;
  error?: string;
}

interface CachedGroupedJobs {
  fetchedAt: number;
  promise?: Promise<Record<string, unknown[]>>;
  jobsByType?: Record<string, unknown[]>;
}

const groupedJobsCache = new Map<string, CachedGroupedJobs>();
const GROUPED_JOBS_CACHE_MS = 2000;

async function fetchGroupedStudioJobs(projectId: string): Promise<Record<string, unknown[]>> {
  const response = await axios.get<GroupedStudioJobsResponse>(
    `${API_BASE_URL}/projects/${projectId}/studio/job-groups`
  );
  if (!response.data.success) {
    throw new Error(response.data.error || 'Failed to list grouped studio jobs');
  }
  return response.data.jobs_by_type || {};
}

async function getGroupedStudioJobs(projectId: string): Promise<Record<string, unknown[]>> {
  const cached = groupedJobsCache.get(projectId);
  const now = Date.now();

  if (cached?.jobsByType && now - cached.fetchedAt < GROUPED_JOBS_CACHE_MS) {
    return cached.jobsByType;
  }

  if (cached?.promise) {
    return cached.promise;
  }

  const promise = fetchGroupedStudioJobs(projectId)
    .then((jobsByType) => {
      groupedJobsCache.set(projectId, {
        fetchedAt: Date.now(),
        jobsByType,
      });
      return jobsByType;
    })
    .catch((error) => {
      groupedJobsCache.delete(projectId);
      log.error({ err: error, projectId }, 'failed to fetch grouped studio jobs');
      throw error;
    });

  groupedJobsCache.set(projectId, {
    fetchedAt: now,
    jobsByType: cached?.jobsByType,
    promise,
  });

  return promise;
}

export async function listStudioJobsByType<T extends object>(
  projectId: string,
  jobType: string,
  sourceId?: string
): Promise<{ success: boolean; jobs: T[]; count: number; error?: string }> {
  try {
    const jobsByType = await getGroupedStudioJobs(projectId);
    const allJobs = ((jobsByType[jobType] as T[] | undefined) || []);
    const jobs = sourceId
      ? allJobs.filter((job) => (
          typeof (job as { source_id?: string | null }).source_id === 'string' &&
          (job as { source_id?: string | null }).source_id === sourceId
        ))
      : allJobs;
    return {
      success: true,
      jobs,
      count: jobs.length,
    };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data) {
      return error.response.data;
    }
    log.error({ err: error, projectId, jobType }, 'failed to list studio jobs by type');
    throw error;
  }
}
