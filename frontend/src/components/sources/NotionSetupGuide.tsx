/**
 * NotionSetupGuide — step-by-step instructions for getting a Notion
 * integration token created, wired into NoobBook, and granted access to
 * the pages the user wants to import.
 *
 * Two variants:
 *  - "full"    : all 9 steps. Used in the Notion tab's "Not Configured"
 *                empty state so a first-time admin can complete setup
 *                without leaving the app.
 *  - "sharing" : just the per-page sharing reminder (steps 6–9). Used
 *                when the integration token IS configured but the search
 *                returned no results — almost always because the user
 *                hasn't shared any pages with the integration yet.
 *
 * We don't try to deep-link into Admin Settings → API Keys: that surface
 * lives in another sheet (AppSettings) and chaining sheet-over-sheet is
 * fiddly. The guide references the path in text instead — users can close
 * Add Sources and use the existing admin nav.
 */
import React from 'react';
import { ArrowSquareOut, Info, NotionLogo } from '@phosphor-icons/react';

interface NotionSetupGuideProps {
  variant: 'full' | 'sharing';
}

const NOTION_INTEGRATIONS_URL = 'https://www.notion.so/profile/integrations';

const Step: React.FC<{ n: number; children: React.ReactNode }> = ({ n, children }) => (
  <li className="flex gap-3">
    <span
      aria-hidden="true"
      className="shrink-0 mt-0.5 inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-600 text-white text-xs font-semibold"
    >
      {n}
    </span>
    <div className="text-sm leading-relaxed text-stone-700">{children}</div>
  </li>
);

const ExternalLinkButton: React.FC<{ href: string; children: React.ReactNode }> = ({
  href,
  children,
}) => (
  <a
    href={href}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-amber-600 bg-amber-600 text-white text-xs font-medium hover:bg-amber-700 hover:border-amber-700 transition-colors"
  >
    {children}
    <ArrowSquareOut size={12} weight="bold" />
  </a>
);

const SharingSteps: React.FC = () => (
  <ol className="space-y-3">
    <Step n={1}>
      In Notion, open the page or database you want to import.
    </Step>
    <Step n={2}>
      Click the <strong>•••</strong> menu in the top-right of the page.
    </Step>
    <Step n={3}>
      Pick <strong>Connections</strong> → search for your integration (e.g.{' '}
      <em>NoobBook</em>) → <strong>Confirm</strong>.
    </Step>
    <Step n={4}>
      <span className="inline-flex items-start gap-1.5">
        <Info size={14} weight="fill" className="text-amber-600 shrink-0 mt-0.5" />
        <span>
          <strong>Tip:</strong> sharing a parent page auto-grants access to
          every nested child. Sharing your workspace root once is usually
          enough.
        </span>
      </span>
    </Step>
  </ol>
);

export const NotionSetupGuide: React.FC<NotionSetupGuideProps> = ({ variant }) => {
  if (variant === 'sharing') {
    return (
      <div className="text-left rounded-md border border-stone-200 bg-stone-50 px-4 py-4 space-y-3">
        <div className="flex items-center gap-2">
          <NotionLogo size={18} weight="duotone" className="text-stone-700" />
          <h4 className="text-sm font-semibold text-stone-900">
            Share pages with the integration to see them here
          </h4>
        </div>
        <SharingSteps />
      </div>
    );
  }

  return (
    <div className="text-left rounded-md border border-stone-200 bg-stone-50 px-5 py-5 space-y-5">
      {/* Section 1: integration token setup (admin) */}
      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-stone-900">
            Once per deployment (admin)
          </h4>
          <ExternalLinkButton href={NOTION_INTEGRATIONS_URL}>
            Open Notion integrations
          </ExternalLinkButton>
        </div>
        <ol className="space-y-3">
          <Step n={1}>
            Go to{' '}
            <a
              href={NOTION_INTEGRATIONS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-700 underline hover:text-amber-800"
            >
              notion.so/profile/integrations
            </a>{' '}
            and click <strong>+ New integration</strong>.
          </Step>
          <Step n={2}>
            Name it (e.g. <em>NoobBook</em>), pick your workspace, set type
            to <strong>Internal</strong>.
          </Step>
          <Step n={3}>
            Under <strong>Capabilities</strong>, enable{' '}
            <strong>Read content</strong>. Read-only is enough — NoobBook
            never writes back to Notion.
          </Step>
          <Step n={4}>
            Copy the <strong>Internal Integration Secret</strong> (starts
            with <code className="text-[11px] px-1 py-0.5 rounded bg-stone-200">ntn_…</code>{' '}
            or <code className="text-[11px] px-1 py-0.5 rounded bg-stone-200">secret_…</code>).
          </Step>
          <Step n={5}>
            Paste it into <strong>Admin Settings → API Keys → Notion Integration</strong>{' '}
            and click <strong>Validate &amp; Save</strong>.
          </Step>
        </ol>
      </section>

      {/* Section 2: per-page sharing (every user, every resource) */}
      <section className="space-y-3 pt-1 border-t border-stone-200">
        <h4 className="text-sm font-semibold text-stone-900 pt-3">
          For each page or database you want to import
        </h4>
        <p className="text-xs text-stone-500 leading-relaxed -mt-1">
          The token alone doesn&apos;t expose anything — you have to share
          each resource with the integration explicitly. This is also how
          you keep private pages out of NoobBook.
        </p>
        <SharingSteps />
      </section>
    </div>
  );
};
