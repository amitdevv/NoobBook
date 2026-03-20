import { useContext, useMemo } from 'react';
import { StudioContext } from './StudioContext.shared';
import type { StudioContextValue } from './StudioContext.shared';

export const useStudioContext = (): StudioContextValue => {
  const context = useContext(StudioContext);
  if (!context) {
    throw new Error('useStudioContext must be used within a StudioProvider');
  }
  return context;
};

export const useFilteredJobs = <T extends { source_id: string | null }>(jobs: T[]): T[] => {
  const { validSourceIds } = useStudioContext();

  return useMemo(() => {
    return jobs.filter((job) => !job.source_id || validSourceIds.has(job.source_id));
  }, [jobs, validSourceIds]);
};
