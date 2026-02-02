/**
 * useAudioGeneration Hook
 * Educational Note: Manages audio overview generation with ElevenLabs TTS.
 * Includes playback state management with a shared audio element.
 */

import { useState, useRef } from 'react';
import { audioAPI, type AudioJob } from '@/lib/api/studio';
import { getAuthUrl } from '@/lib/api/client';
import type { StudioSignal } from '../types';
import { useToast } from '../../ui/toast';

export const useAudioGeneration = (projectId: string) => {
  const { success: showSuccess, error: showError } = useToast();

  const [savedAudioJobs, setSavedAudioJobs] = useState<AudioJob[]>([]);
  const [currentAudioJob, setCurrentAudioJob] = useState<AudioJob | null>(null);
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [playingJobId, setPlayingJobId] = useState<string | null>(null);
  const [isPaused, setIsPaused] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const PLAYBACK_SPEEDS = [1, 1.25, 1.5, 1.75, 2] as const;

  const loadSavedJobs = async () => {
    const audioResponse = await audioAPI.listJobs(projectId);
    if (audioResponse.success && audioResponse.jobs) {
      const completedAudio = audioResponse.jobs.filter((job) => job.status === 'ready');
      setSavedAudioJobs(completedAudio);
    }
  };

  const handleAudioGeneration = async (signal: StudioSignal) => {
    console.log('[useAudioGeneration] handleAudioGeneration called with signal:', signal);
    const sourceId = signal.sources[0]?.source_id;
    console.log('[useAudioGeneration] Extracted sourceId:', sourceId);
    if (!sourceId) {
      console.error('[useAudioGeneration] No source_id found in signal.sources:', signal.sources);
      showError('No source specified for audio generation.');
      return;
    }

    setIsGeneratingAudio(true);
    setCurrentAudioJob(null);

    try {
      const ttsStatus = await audioAPI.checkTTSStatus();
      if (!ttsStatus.configured) {
        showError('ElevenLabs API key not configured. Please add it in App Settings.');
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
      console.error('Audio generation error:', error);
      showError(error instanceof Error ? error.message : 'Audio generation failed.');
    } finally {
      setIsGeneratingAudio(false);
      setCurrentAudioJob(null);
    }
  };

  const playAudio = (job: AudioJob) => {
    if (!job.audio_url) return;

    if (audioRef.current && playingJobId === job.id && isPaused) {
      audioRef.current.play();
      setIsPaused(false);
      return;
    }

    if (audioRef.current && playingJobId !== job.id) {
      audioRef.current.pause();
      setCurrentTime(0);
      setDuration(0);
    }

    if (audioRef.current) {
      audioRef.current.src = getAuthUrl(job.audio_url);
      audioRef.current.play();
      setPlayingJobId(job.id);
      setIsPaused(false);
    }
  };

  const pauseAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    setIsPaused(true);
  };

  const handleAudioEnd = () => {
    setPlayingJobId(null);
    setIsPaused(false);
    setCurrentTime(0);
    setDuration(0);
  };

  const seekTo = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
      audioRef.current.playbackRate = playbackRate;
    }
  };

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
      const response = await fetch(getAuthUrl(job.audio_url));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = url;
      link.download = job.audio_filename || 'audio_overview.mp3';
      link.click();

      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download audio:', error);
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
    playAudio,
    pauseAudio,
    seekTo,
    playbackRate,
    cyclePlaybackRate,
    downloadAudio,
    formatDuration,
  };
};
