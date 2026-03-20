/**
 * MarketingStrategyViewerModal Component
 * Educational Note: Modal for viewing marketing strategy markdown content.
 * Renders markdown with proper styling for tables, lists, headings.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { ChartLine, DownloadSimple, SpinnerGap, PencilSimple } from '@phosphor-icons/react';
import { marketingStrategiesAPI, type MarketingStrategyJob } from '@/lib/api/studio';
import { Input } from '../../ui/input';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarketingStrategyViewerModalProps {
  projectId: string;
  viewingMarketingStrategyJob: MarketingStrategyJob | null;
  onClose: () => void;
  onDownload: (jobId: string) => void;
  onEdit?: (instructions: string) => void;
}

const MarketingStrategyContent: React.FC<{
  projectId: string;
  jobId: string;
}> = ({ projectId, jobId }) => {
  const [markdownContent, setMarkdownContent] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    marketingStrategiesAPI.getPreview(projectId, jobId)
      .then((response) => {
        if (cancelled) return;
        if (response.success && response.markdown_content) {
          setMarkdownContent(response.markdown_content);
        } else {
          setMarkdownContent('*Failed to load marketing strategy content*');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMarkdownContent('*Error loading marketing strategy content*');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, jobId]);

  if (markdownContent === null) {
    return (
      <div className="flex items-center justify-center py-12">
        <SpinnerGap size={24} className="animate-spin text-emerald-500" />
        <span className="ml-2 text-muted-foreground">Loading marketing strategy content...</span>
      </div>
    );
  }

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-2xl font-bold mt-6 mb-4 text-foreground">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-semibold mt-5 mb-3 text-foreground border-b pb-2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-lg font-medium mt-4 mb-2 text-foreground">{children}</h3>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-4">
              <table className="min-w-full border border-border rounded">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 bg-muted text-left text-sm font-medium border-b">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 text-sm border-b border-border">{children}</td>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-inside my-2 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-inside my-2 space-y-1">{children}</ol>
          ),
          p: ({ children }) => (
            <p className="my-2 text-foreground/90 leading-relaxed">{children}</p>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-emerald-500 pl-4 my-4 italic text-muted-foreground">
              {children}
            </blockquote>
          ),
          code: ({ className, children }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
                  {children}
                </code>
              );
            }
            return (
              <code className="block bg-muted p-3 rounded text-sm font-mono overflow-x-auto">
                {children}
              </code>
            );
          },
          hr: () => <hr className="my-6 border-border" />,
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
        }}
      >
        {markdownContent}
      </ReactMarkdown>
    </div>
  );
};

const MarketingStrategyEditBar: React.FC<{ onEdit: (instructions: string) => void }> = ({ onEdit }) => {
  const [editInput, setEditInput] = useState('');

  const handleEdit = () => {
    const trimmed = editInput.trim();
    if (!trimmed) return;
    onEdit(trimmed);
    setEditInput('');
  };

  return (
    <div className="flex gap-2 px-6 py-3 border-t-2 border-orange-200 bg-orange-50/30 flex-shrink-0">
      <Input
        value={editInput}
        onChange={(e) => setEditInput(e.target.value)}
        placeholder="Describe changes... (e.g., 'target enterprise customers', 'add social media channels')"
        className="flex-1"
        onKeyDown={(e) => e.key === 'Enter' && editInput.trim() && handleEdit()}
      />
      <Button onClick={handleEdit} disabled={!editInput.trim()} size="sm">
        <PencilSimple size={14} className="mr-1" />
        Edit
      </Button>
    </div>
  );
};

export const MarketingStrategyViewerModal: React.FC<MarketingStrategyViewerModalProps> = ({
  projectId,
  viewingMarketingStrategyJob,
  onClose,
  onDownload,
  onEdit,
}) => {
  return (
    <Dialog open={viewingMarketingStrategyJob !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl h-[85vh] p-0 flex flex-col">
        <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between pr-6">
            <div className="flex items-center gap-2">
              <ChartLine size={20} className="text-emerald-600" />
              <DialogTitle>
                {viewingMarketingStrategyJob?.document_title || 'Marketing Strategy Document'}
              </DialogTitle>
            </div>
            {viewingMarketingStrategyJob && (
              <Button
                variant="soft"
                size="sm"
                onClick={() => onDownload(viewingMarketingStrategyJob.id)}
                className="flex items-center gap-1"
              >
                <DownloadSimple size={14} />
                Download
              </Button>
            )}
          </div>
          {viewingMarketingStrategyJob?.product_name && (
            <DialogDescription>
              {viewingMarketingStrategyJob.product_name} - {viewingMarketingStrategyJob.sections_written} sections
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Markdown Content */}
        <ScrollArea className="flex-1">
          <div className="px-6 py-4">
            {viewingMarketingStrategyJob && (
              <MarketingStrategyContent
                key={viewingMarketingStrategyJob.id}
                projectId={projectId}
                jobId={viewingMarketingStrategyJob.id}
              />
            )}
          </div>
        </ScrollArea>

        {onEdit && (
          <MarketingStrategyEditBar
            key={viewingMarketingStrategyJob?.id || 'marketing-strategy-edit'}
            onEdit={onEdit}
          />
        )}
      </DialogContent>
    </Dialog>
  );
};
