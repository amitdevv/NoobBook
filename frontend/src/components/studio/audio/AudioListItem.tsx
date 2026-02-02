/**
 * AudioListItem Component
 * Educational Note: Renders saved audio with inline playback controls.
 * Includes play/pause, progress bar, time display, speed control, and download.
 * When playing, expands to show full transport controls below the title row.
 */

import React from 'react';
import { SpeakerHigh, Play, Pause, DownloadSimple } from '@phosphor-icons/react';
import { Button } from '../../ui/button';
import type { AudioJob } from '@/lib/api/studio';

interface AudioListItemProps {
  job: AudioJob;
  playingJobId: string | null;
  currentTime: number;
  duration: number;
  playbackRate: number;
  onPlay: (job: AudioJob) => void;
  onPause: () => void;
  onDownload: (job: AudioJob) => void;
  onSeek: (time: number) => void;
  onCycleSpeed: () => void;
  formatDuration: (seconds: number) => string;
}

export const AudioListItem: React.FC<AudioListItemProps> = ({
  job,
  playingJobId,
  currentTime,
  duration,
  playbackRate,
  onPlay,
  onPause,
  onDownload,
  onSeek,
  onCycleSpeed,
  formatDuration,
}) => {
  const isPlaying = playingJobId === job.id;
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  /**
   * Handle clicking on the progress bar to seek
   */
  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const fraction = (e.clientX - rect.left) / rect.width;
    onSeek(fraction * duration);
  };

  return (
    <div className="bg-muted/50 rounded border hover:border-primary/50 transition-colors">
      {/* Top row: icon, name, play/download controls */}
      <div className="flex items-center gap-2 p-1.5">
        <div className="p-1 bg-primary/10 rounded flex-shrink-0">
          <SpeakerHigh size={12} className="text-primary" />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <p className="text-[10px] font-medium truncate max-w-[120px]">{job.source_name}</p>
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <Button
            size="sm"
            variant={isPlaying ? 'default' : 'ghost'}
            className="h-5 w-5 p-0"
            onClick={() => isPlaying ? onPause() : onPlay(job)}
          >
            {isPlaying ? (
              <Pause size={10} weight="fill" />
            ) : (
              <Play size={10} weight="fill" />
            )}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-5 w-5 p-0"
            onClick={() => onDownload(job)}
          >
            <DownloadSimple size={10} />
          </Button>
        </div>
      </div>

      {/* Transport controls - visible when this item is the active player */}
      {isPlaying && (
        <div className="px-2 pb-1.5 space-y-1">
          {/* Progress bar */}
          <div
            className="h-1 bg-muted rounded-full cursor-pointer group"
            onClick={handleProgressClick}
          >
            <div
              className="h-full bg-primary rounded-full transition-[width] duration-100"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Time + speed row */}
          <div className="flex items-center justify-between">
            <span className="text-[9px] text-muted-foreground tabular-nums">
              {formatDuration(currentTime)} / {formatDuration(duration)}
            </span>
            <button
              onClick={onCycleSpeed}
              className="text-[9px] font-medium text-muted-foreground hover:text-foreground transition-colors px-1 rounded"
            >
              {playbackRate}x
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
