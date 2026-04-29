/**
 * AudioView — native <audio> player + ElevenLabs transcript below.
 *
 * The transcript piggybacks on MarkdownView so search highlighting
 * works the same way it does for any other text-based source.
 */
import React from 'react';
import { MarkdownView } from './MarkdownView';
import type { DocSearchAPI } from './useDocSearch';

interface AudioViewProps {
  url: string;
  transcript: string | null;
  search: DocSearchAPI;
}

export const AudioView: React.FC<AudioViewProps> = ({ url, transcript, search }) => {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-stone-200 bg-gradient-to-br from-amber-50/40 to-stone-50 p-5">
        <audio src={url} controls className="w-full" />
      </div>

      {transcript ? (
        <div>
          <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-400">
            <span className="h-px flex-1 bg-stone-200" />
            <span>Transcript</span>
            <span className="h-px flex-1 bg-stone-200" />
          </div>
          <MarkdownView content={transcript} search={search} />
        </div>
      ) : (
        <p className="text-sm text-stone-500 text-center py-8">
          Transcript unavailable.
        </p>
      )}
    </div>
  );
};
