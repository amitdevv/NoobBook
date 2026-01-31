/**
 * SocialSection Component
 * Educational Note: Self-contained section for social post generation.
 * Note: Social posts use studio_item signal check instead of source_id filtering.
 */

import React, { useEffect, useCallback } from 'react';
import { useStudioContext } from '../StudioContext';
import { useSocialPostGeneration } from '../social/useSocialPostGeneration';
import { SocialPostListItem } from '../social/SocialPostListItem';
import { SocialPostProgressIndicator } from '../social/SocialPostProgressIndicator';
import { SocialPostViewerModal } from '../social/SocialPostViewerModal';
import { ConfigErrorBanner } from '../shared/ConfigErrorBanner';
import { LinkedinLogo, InstagramLogo, TwitterLogo } from '@phosphor-icons/react';

export const SocialSection: React.FC = () => {
  const { projectId, signals, registerGenerationHandler } = useStudioContext();

  const {
    savedSocialPostJobs,
    currentSocialPostJob,
    isGeneratingSocialPosts,
    viewingSocialPostJob,
    setViewingSocialPostJob,
    configError,
    selectedPlatforms,
    setSelectedPlatforms,
    loadSavedJobs,
    handleSocialPostGeneration,
  } = useSocialPostGeneration(projectId);

  const togglePlatform = (platform: string) => {
    setSelectedPlatforms((prev: string[]) => {
      if (prev.includes(platform)) {
        // Don't allow deselecting all platforms
        if (prev.length === 1) return prev;
        return prev.filter((p: string) => p !== platform);
      }
      return [...prev, platform];
    });
  };

  const hasSocialSignal = signals.some((s) => s.studio_item === 'social');

  useEffect(() => {
    loadSavedJobs();
  }, [projectId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleGenerate = useCallback(async (signal: Parameters<typeof handleSocialPostGeneration>[0]) => {
    await handleSocialPostGeneration(signal);
  }, [handleSocialPostGeneration]);

  useEffect(() => {
    registerGenerationHandler('social', handleGenerate);
  }, [registerGenerationHandler, handleGenerate]);

  if (!hasSocialSignal && savedSocialPostJobs.length === 0 && !isGeneratingSocialPosts && !configError) {
    return null;
  }

  return (
    <>
      <ConfigErrorBanner message={configError} />

      {/* Platform Selection Toggles */}
      {hasSocialSignal && !isGeneratingSocialPosts && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-muted-foreground mr-1">Platforms:</span>
          {([
            { id: 'linkedin', label: 'LinkedIn', icon: LinkedinLogo, selectedClass: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 ring-1 ring-blue-300 dark:ring-blue-700' },
            { id: 'instagram', label: 'Instagram', icon: InstagramLogo, selectedClass: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300 ring-1 ring-pink-300 dark:ring-pink-700' },
            { id: 'twitter', label: 'Twitter', icon: TwitterLogo, selectedClass: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300 ring-1 ring-sky-300 dark:ring-sky-700' },
          ] as const).map(({ id, label, icon: Icon, selectedClass }) => {
            const isSelected = selectedPlatforms.includes(id);
            return (
              <button
                key={id}
                onClick={() => togglePlatform(id)}
                className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                  isSelected ? selectedClass : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                }`}
              >
                <Icon size={14} weight={isSelected ? 'fill' : 'regular'} />
                {label}
              </button>
            );
          })}
        </div>
      )}

      {isGeneratingSocialPosts && (
        <SocialPostProgressIndicator currentSocialPostJob={currentSocialPostJob} />
      )}

      {hasSocialSignal && savedSocialPostJobs.map((job) => (
        <SocialPostListItem
          key={job.id}
          job={job}
          onClick={() => setViewingSocialPostJob(job)}
        />
      ))}

      <SocialPostViewerModal
        viewingSocialPostJob={viewingSocialPostJob}
        onClose={() => setViewingSocialPostJob(null)}
      />
    </>
  );
};
