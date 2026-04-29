/**
 * ImageView — renders a source image from a signed raw URL.
 *
 * Two display modes: fit-to-window (default) and actual-size. The
 * toggle lives in the toolbar; the parent passes the current mode.
 */
import React from 'react';

interface ImageViewProps {
  url: string;
  alt: string;
  fitMode: 'fit' | 'actual';
}

export const ImageView: React.FC<ImageViewProps> = ({ url, alt, fitMode }) => {
  return (
    <div className="w-full flex justify-center">
      <img
        src={url}
        alt={alt}
        className={
          fitMode === 'fit'
            ? 'max-w-full max-h-[75vh] object-contain rounded-md shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.18)]'
            : 'rounded-md shadow-[0_1px_2px_rgba(0,0,0,0.04),0_8px_24px_-12px_rgba(0,0,0,0.18)]'
        }
      />
    </div>
  );
};
