/**
 * useAudioGeneration Hook
 * Educational Note: Manages audio overview generation with ElevenLabs TTS.
 * Includes playback state management with a shared audio element.
 */

import { useState, useRef } from 'react';
import { audioAPI, type AudioJob } from '@/lib/api/studio';
import { api, getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('audio-generation');

export const useAudioGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedAudioJobs, setSavedAudioJobs] = useState<AudioJob[]>([]);
  const [currentAudioJob, setCurrentAudioJob] = useState<AudioJob | null>(null);
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const pollingRef = useRef(false);
  const [playingJobId, setPlayingJobId] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [pendingEdit, setPendingEdit] = useState<{ jobId: string; input: string } | null>(null);
  const [editingJobId, setEditingJobId] = useState<string | null>(null);

  const PLAYBACK_SPEEDS = [1, 1.25, 1.5, 1.75, 2] as const;

  const loadSavedJobs = async () => {
    try {
      const audioResponse = await audioAPI.listJobs(projectId);
      if (audioResponse.success && audioResponse.jobs) {
        const finishedJobs = audioResponse.jobs.filter(
          (job) => job.status === 'ready' || job.status === 'error'
        );
        setSavedAudioJobs(finishedJobs);

        // Resume polling for in-progress jobs (survives refresh/navigation)
        if (!isGeneratingAudio && !pollingRef.current) {
          const inProgressJob = audioResponse.jobs.find(
            (job) => job.status === 'pending' || job.status === 'processing'
          );
          if (inProgressJob) {
            pollingRef.current = true;
            setIsGeneratingAudio(true);
            setCurrentAudioJob(inProgressJob);
            try {
              const finalJob = await audioAPI.pollJobStatus(
                projectId,
                inProgressJob.id,
                (job) => setCurrentAudioJob(job)
              );
              if (finalJob.status === 'ready' || finalJob.status === 'error') {
                if (finalJob.status === 'ready' && finalJob.parent_job_id) {
                  // Edit completed after refresh -- keep parent so user can view previous versions
                  setSavedAudioJobs((prev) => [finalJob, ...prev]);
                } else if (finalJob.status === 'error' && finalJob.parent_job_id) {
                  // Edit failed after refresh -- orphaned error job filtered by backend list
                } else {
                  setSavedAudioJobs((prev) => [finalJob, ...prev]);
                }
              }
            } catch {
              // Polling failed -- job stays visible via next load
            } finally {
              pollingRef.current = false;
              setIsGeneratingAudio(false);
              setCurrentAudioJob(null);
            }
          }
        }
      }
    } catch (error) {
      log.error({ err: error }, 'failed to load saved audio jobs');
    }
  };

  const handleAudioGeneration = async (signal: StudioSignal) => {
    const sourceId = signal.sources[0]?.source_id || "";

    setIsGeneratingAudio(true);
    setCurrentAudioJob(null);

    try {
      const ttsStatus = await audioAPI.checkTTSStatus();
      if (!ttsStatus.configured) {
        showError('ElevenLabs API key not configured. Please add it in Admin Settings.');
        setIsGeneratingAudio(false);
        return;
      }

      const startResponse = await audioAPI.startGeneration(projectId, sourceId, signal.direction);

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start audio generation.');
        setIsGeneratingAudio(false);
        return;
      }

      showSuccess(`Generating audio for ${startResponse.source_name}...`);

      const finalJob = await audioAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentAudioJob(job)
      );

      setCurrentAudioJob(finalJob);

      if (finalJob.status === 'ready') {
        showSuccess('Your audio overview is ready to play!');
        setSavedAudioJobs((prev) => [finalJob, ...prev]);
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Audio generation failed.');
      }
    } catch (error) {
      log.error({ err: error }, 'audio generation failed');
      showError(error instanceof Error ? error.message : 'Audio generation failed.');
    } finally {
      setIsGeneratingAudio(false);
      setCurrentAudioJob(null);
    }
  };

  /**
   * Edit an existing audio job -- regenerates with different instructions
   * while keeping the same source. The previous script is used as baseline.
   */
  const handleAudioEdit = async (parentJob: AudioJob, editInstructions: string) => {
    if (isGeneratingAudio) return;
    setIsGeneratingAudio(true);
    setPendingEdit({ jobId: parentJob.id, input: editInstructions });
    setEditingJobId(null);

    try {
      const startResponse = await audioAPI.startGeneration(
        projectId,
        parentJob.source_id,
        parentJob.direction,
        parentJob.id,        // parentJobId
        editInstructions     // editInstructions
      );

      if (!startResponse.success || !startResponse.job_id) {
        showError(startResponse.error || 'Failed to start audio edit.');
        setEditingJobId(parentJob.id); // restore so user can retry with instructions
        return;
      }

      showSuccess('Editing audio overview...');

      const finalJob = await audioAPI.pollJobStatus(
        projectId,
        startResponse.job_id,
        (job) => setCurrentAudioJob(job)
      );

      setCurrentAudioJob(finalJob);

      if (finalJob.status === 'ready') {
        setPendingEdit(null);
        showSuccess('Your edited audio overview is ready to play!');
        setSavedAudioJobs((prev) => [finalJob, ...prev]);
        // Parent job is kept so user can view previous versions
      } else if (finalJob.status === 'error') {
        showError(finalJob.error || 'Audio edit failed.');
        // Restore editing state so user can retry
        setEditingJobId(parentJob.id);
      }
    } catch (error) {
      log.error({ err: error }, 'audio edit failed');
      showError(error instanceof Error ? error.message : 'Audio edit failed.');
      setEditingJobId(parentJob.id);
    } finally {
      setIsGeneratingAudio(false);
      setCurrentAudioJob(null);
      // Note: pendingEdit is intentionally NOT cleared here -- on edit failure,
      // the user's instructions are preserved to pre-fill the input for easy retry.
    }
  };

  /**
   * Play a specific audio job, or resume if it's the same job that was paused
   */
  const playAudio = (job: AudioJob) => {
    if (!job.audio_url) return;

    // Resume if same job was paused -- don't reload the source
    if (audioRef.current && playingJobId === job.id && isPaused) {
      audioRef.current.play();
      setIsPaused(false);
      return;
    }

    // Switching to a different job -- stop current and reset
    if (audioRef.current && playingJobId !== job.id) {
      audioRef.current.pause();
      setCurrentTime(0);
      setDuration(0);
    }

    // Load new source and play
    if (audioRef.current) {
      audioRef.current.src = getAuthUrl(job.audio_url);
      audioRef.current.play();
      setPlayingJobId(job.id);
      setIsPaused(false);
    }
  };

  /**
   * Pause current playback -- keeps the job active so resume works
   */
  const pauseAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    setIsPaused(true);
  };

  /**
   * Handle audio end -- reset playback state
   */
  const handleAudioEnd = () => {
    setPlayingJobId(null);
    setIsPaused(false);
    setCurrentTime(0);
    setDuration(0);
  };

  /**
   * Seek to a specific time in the audio
   */
  const seekTo = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  /**
   * Track playback progress -- called by audio element's onTimeUpdate
   */
  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  /**
   * Capture duration once audio metadata is loaded
   */
  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
      // Apply current playback rate to newly loaded audio
      audioRef.current.playbackRate = playbackRate;
    }
  };

  /**
   * Cycle through playback speeds: 1x -> 1.25x -> 1.5x -> 1.75x -> 2x -> 1x
   */
  const cyclePlaybackRate = () => {
    const currentIndex = PLAYBACK_SPEEDS.indexOf(playbackRate as typeof PLAYBACK_SPEEDS[number]);
    const nextRate = PLAYBACK_SPEEDS[(currentIndex + 1) % PLAYBACK_SPEEDS.length];
    setPlaybackRate(nextRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextRate;
    }
  };

  const downloadAudio = async (job: AudioJob) => {
    if (!job.audio_url) return;

    try {
      const response = await api.get(job.audio_url, { responseType: 'blob' });
      const blob = new Blob([response.data]);
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = job.audio_filename || 'audio_overview.mp3';
      link.click();

      URL.revokeObjectURL(url);
    } catch (error) {
      log.error({ err: error }, 'failed to download audio');
      showError('Failed to download audio file');
    }
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return {
    savedAudioJobs,
    currentAudioJob,
    isGeneratingAudio,
    playingJobId,
    isPaused,
    currentTime,
    duration,
    audioRef,
    handleAudioEnd,
    handleTimeUpdate,
    handleLoadedMetadata,
    loadSavedJobs,
    handleAudioGeneration,
    handleAudioEdit,
    playAudio,
    pauseAudio,
    seekTo,
    playbackRate,
    cyclePlaybackRate,
    downloadAudio,
    formatDuration,
    editingJobId,
    setEditingJobId,
    pendingEditInput: pendingEdit !== null && pendingEdit.jobId === editingJobId ? pendingEdit.input : '',
  };
};
