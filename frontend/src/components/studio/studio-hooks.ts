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
    // validSourceIds derives from studioSignals, which resets to [] every
    // time the active chat changes. While it's empty we have no information
    // about which sources are still valid — show every job unfiltered rather
    // than blink them out (and cause sections, which short-circuit to `null`
    // when filteredJobs is empty, to disappear from the panel entirely until
    // signals reload).
    if (validSourceIds.size === 0) return jobs;
    return jobs.filter((job) => !job.source_id || validSourceIds.has(job.source_id));
  }, [jobs, validSourceIds]);
};
