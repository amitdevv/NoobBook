import React, { useMemo } from 'react';
import { Sparkle } from '@phosphor-icons/react';

/**
 * Live partial-image preview for streaming AI image generation.
 *
 * GPT Image 2 emits partial frames while the final image renders. This
 * component shows them as a stacked filmstrip — older frames recede
 * (smaller, dimmer, tilted back) and the newest sits in front under a
 * diagonal shimmer sweep, suggesting an image still materializing.
 *
 * Designed to be visually neutral so it sits cleanly inside the
 * amber/indigo/blue/cyan/purple-tinted progress indicators upstream.
 *
 * Empty state: renders nothing.
 */
export interface PartialImagesPreviewProps {
  urls?: string[];
  className?: string;
}

const STYLE_TAG = `
@keyframes ppi-rise {
  from { opacity: 0; transform: translateY(6px) scale(0.78); }
  to   { opacity: var(--ppi-final-opacity, 1); transform: translateY(0) scale(var(--ppi-final-scale, 1)) rotate(var(--ppi-final-tilt, 0deg)); }
}
@keyframes ppi-shimmer {
  0%   { transform: translateX(-160%) skewX(-18deg); opacity: 0; }
  18%  { opacity: 0.55; }
  62%  { opacity: 0.55; }
  100% { transform: translateX(260%) skewX(-18deg); opacity: 0; }
}
@keyframes ppi-spark {
  0%, 100% { opacity: 0.4;  transform: scale(1); }
  50%      { opacity: 1;    transform: scale(1.18); }
}
@keyframes ppi-edgeGlow {
  0%, 100% { box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }
  50%      { box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22), 0 4px 14px -6px rgba(0,0,0,0.18); }
}
`;

export const PartialImagesPreview: React.FC<PartialImagesPreviewProps> = ({
  urls,
  className,
}) => {
  // Show the most recent 3. Slicing in a memo keeps the array reference
  // stable across polls when nothing new arrived.
  const recent = useMemo(() => (urls ?? []).slice(-3), [urls]);
  if (recent.length === 0) return null;

  return (
    <div
      className={`mt-2 flex items-end gap-2 ${className ?? ''}`}
      aria-label={`Generating image — ${recent.length} preview frame${recent.length === 1 ? '' : 's'}`}
    >
      <style>{STYLE_TAG}</style>

      <div className="relative flex items-end -space-x-1.5">
        {recent.map((url, idx) => {
          const distanceFromLatest = recent.length - 1 - idx;
          const isLatest = distanceFromLatest === 0;
          // Older frames recede — smaller, dimmer, tilted back like a stack
          // of polaroids. Tuned for a 48px latest frame sitting beside a
          // ~280px progress indicator, so the whole strip lands ~120px wide.
          const finalScale = isLatest ? 1 : distanceFromLatest === 1 ? 0.84 : 0.7;
          const finalOpacity = isLatest ? 1 : distanceFromLatest === 1 ? 0.72 : 0.42;
          const finalTilt = isLatest ? 0 : distanceFromLatest === 1 ? -4 : -8;

          return (
            <div
              key={url}
              style={{
                ['--ppi-final-scale' as string]: finalScale,
                ['--ppi-final-opacity' as string]: finalOpacity,
                ['--ppi-final-tilt' as string]: `${finalTilt}deg`,
                animation: 'ppi-rise 360ms cubic-bezier(0.2, 0.7, 0.2, 1) both',
                transform: `scale(${finalScale}) rotate(${finalTilt}deg)`,
                opacity: finalOpacity,
                transformOrigin: 'bottom center',
                zIndex: 10 + idx,
              }}
              className="relative h-12 w-12 shrink-0 overflow-hidden rounded-[6px]
                ring-1 ring-stone-900/10 dark:ring-white/10
                bg-stone-200/70 dark:bg-stone-800/70
                shadow-[0_1px_2px_rgba(0,0,0,0.06)]
                transition-[transform,opacity] duration-500 ease-[cubic-bezier(0.2,0.7,0.2,1)]"
            >
              <img
                src={url}
                alt=""
                loading="lazy"
                draggable={false}
                decoding="async"
                className="h-full w-full select-none object-cover"
              />

              {/* Subtle film-grain veil so partials read as "developing" rather
                  than just low-res. Stays barely visible against any tint. */}
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 mix-blend-overlay"
                style={{
                  background:
                    'radial-gradient(120% 80% at 50% 0%, rgba(255,255,255,0.18), transparent 60%)',
                }}
              />

              {isLatest && (
                <>
                  {/* Diagonal shimmer — the materialization sweep. */}
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-y-[-20%] left-0 w-1/2
                      bg-gradient-to-r from-transparent via-white/55 to-transparent
                      mix-blend-overlay"
                    style={{ animation: 'ppi-shimmer 2.4s ease-in-out infinite' }}
                  />
                  {/* Soft inner ring breathing — frame is "active". */}
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-0 rounded-[6px]"
                    style={{ animation: 'ppi-edgeGlow 2.4s ease-in-out infinite' }}
                  />
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Lifecycle pip — single Sparkle pulsing in the host's tint via
          currentColor inheritance. Compact, no label, no clutter. */}
      <span
        aria-hidden
        className="mb-0.5 inline-flex h-3.5 w-3.5 items-center justify-center
          text-stone-500/80 dark:text-stone-400/80"
        style={{ animation: 'ppi-spark 1.6s ease-in-out infinite' }}
      >
        <Sparkle size={11} weight="fill" />
      </span>
    </div>
  );
};
