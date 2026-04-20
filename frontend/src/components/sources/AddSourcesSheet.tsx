/**
 * AddSourcesSheet Component
 * Educational Note: Sheet modal with tabs for different source upload methods.
 * Orchestrates UploadTab, LinkTab, and PasteTab components.
 */

import React from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { UploadTab } from './UploadTab';
import { LinkTab } from './LinkTab';
import { PasteTab } from './PasteTab';
import { GoogleDriveTab } from './GoogleDriveTab';
import { ResearchTab } from './ResearchTab';
import { DatabaseTab } from './DatabaseTab';
import { McpTab } from './McpTab';
import { FreshdeskTab } from './FreshdeskTab';
import { JiraTab } from './JiraTab';
import { MixpanelTab } from './MixpanelTab';
import { usePermissions } from '@/contexts/PermissionsContext';
import { MAX_SOURCES } from '../../lib/api/sources';

interface AddSourcesSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  sourcesCount: number;
  onUpload: (files: FileList | File[]) => Promise<void>;
  onAddUrl: (url: string) => Promise<void>;
  onAddText: (content: string, name: string) => Promise<void>;
  onAddResearch: (topic: string, description: string, links: string[]) => Promise<void>;
  onAddDatabase: (connectionId: string, name?: string, description?: string) => Promise<void>;
  onAddMcp: (connectionId: string, resourceUris: string[], name?: string, description?: string) => Promise<void>;
  onAddFreshdesk: (name?: string, description?: string) => Promise<void>;
  onAddJira: (name?: string, description?: string) => Promise<void>;
  onAddMixpanel: (name?: string, description?: string) => Promise<void>;
  onImportComplete: () => void;
  uploading: boolean;
}

export const AddSourcesSheet: React.FC<AddSourcesSheetProps> = ({
  open,
  onOpenChange,
  projectId,
  sourcesCount,
  onUpload,
  onAddUrl,
  onAddText,
  onAddResearch,
  onAddDatabase,
  onAddMcp,
  onAddFreshdesk,
  onAddJira,
  onAddMixpanel,
  onImportComplete,
  uploading,
}) => {
  const isAtLimit = sourcesCount >= MAX_SOURCES;
  const { hasPermission } = usePermissions();

  // Permission checks for each source tab
  // Upload covers PDF, DOCX, PPTX, Image, Audio — show if any document_sources sub-type is allowed
  const canUpload = ['pdf', 'docx', 'pptx', 'image', 'audio'].some(
    (item) => hasPermission('document_sources', item)
  );
  const canLink = hasPermission('document_sources', 'url_youtube');
  const canPaste = hasPermission('document_sources', 'text');
  const canDrive = hasPermission('document_sources', 'google_drive');
  const canDatabase = hasPermission('data_sources', 'database');
  const canFreshdesk = hasPermission('data_sources', 'freshdesk');
  const canJira = hasPermission('integrations', 'jira');
  const canMixpanel = hasPermission('integrations', 'mixpanel');
  // Note: CSV permission exists (hasPermission('data_sources', 'csv')) but no CSV tab yet

  // Research and MCP are always shown (no dedicated permission key) — gated at category level
  const canResearch = hasPermission('document_sources');
  const canMcp = hasPermission('data_sources');

  // Pick the first visible tab as default
  const defaultTab = canUpload ? 'upload'
    : canLink ? 'link'
    : canPaste ? 'paste'
    : canDrive ? 'drive'
    : canResearch ? 'research'
    : canDatabase ? 'database'
    : canMcp ? 'mcp'
    : canFreshdesk ? 'freshdesk'
    : canJira ? 'jira'
    : canMixpanel ? 'mixpanel'
    : 'upload';

  const tabTriggerClass = "px-4 py-2 rounded-md border border-stone-300 bg-stone-100 text-stone-700 cursor-pointer transition-all hover:bg-stone-200 data-[state=active]:border-amber-600 data-[state=active]:bg-amber-600 data-[state=active]:text-white";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[500px] sm:w-[600px]">
        <SheetHeader>
          <SheetTitle>Add sources</SheetTitle>
        </SheetHeader>

        <div className="mt-6">
          <p className="text-sm text-muted-foreground mb-4">
            Sources let NoobBook base its responses on the information that
            matters most to you. ({sourcesCount}/{MAX_SOURCES} used)
          </p>

          <Tabs defaultValue={defaultTab} className="w-full">
            <TabsList className="w-full h-auto flex flex-wrap gap-2 bg-transparent p-0">
              {canUpload && (
                <TabsTrigger value="upload" className={tabTriggerClass}>
                  Upload
                </TabsTrigger>
              )}
              {canLink && (
                <TabsTrigger value="link" className={tabTriggerClass}>
                  Link
                </TabsTrigger>
              )}
              {canPaste && (
                <TabsTrigger value="paste" className={tabTriggerClass}>
                  Paste
                </TabsTrigger>
              )}
              {canDrive && (
                <TabsTrigger value="drive" className={tabTriggerClass}>
                  Drive
                </TabsTrigger>
              )}
              {canResearch && (
                <TabsTrigger value="research" className={tabTriggerClass}>
                  Research
                </TabsTrigger>
              )}
              {canDatabase && (
                <TabsTrigger value="database" className={tabTriggerClass}>
                  Database
                </TabsTrigger>
              )}
              {canMcp && (
                <TabsTrigger value="mcp" className={tabTriggerClass}>
                  MCP
                </TabsTrigger>
              )}
              {canFreshdesk && (
                <TabsTrigger value="freshdesk" className={tabTriggerClass}>
                  Freshdesk
                </TabsTrigger>
              )}
              {canJira && (
                <TabsTrigger value="jira" className={tabTriggerClass}>
                  Jira
                </TabsTrigger>
              )}
              {canMixpanel && (
                <TabsTrigger value="mixpanel" className={tabTriggerClass}>
                  Mixpanel
                </TabsTrigger>
              )}
            </TabsList>

            {canUpload && (
              <TabsContent value="upload" className="mt-6">
                <UploadTab
                  onUpload={onUpload}
                  uploading={uploading}
                  isAtLimit={isAtLimit}
                />
              </TabsContent>
            )}

            {canLink && (
              <TabsContent value="link" className="mt-6">
                <LinkTab onAddUrl={onAddUrl} isAtLimit={isAtLimit} />
              </TabsContent>
            )}

            {canPaste && (
              <TabsContent value="paste" className="mt-6">
                <PasteTab onAddText={onAddText} isAtLimit={isAtLimit} />
              </TabsContent>
            )}

            {canDrive && (
              <TabsContent value="drive" className="mt-6">
                <GoogleDriveTab
                  projectId={projectId}
                  onImportComplete={() => {
                    onImportComplete();
                    onOpenChange(false); // Close sheet after import
                  }}
                  isAtLimit={isAtLimit}
                />
              </TabsContent>
            )}

            {canResearch && (
              <TabsContent value="research" className="mt-6">
                <ResearchTab
                  onAddResearch={onAddResearch}
                  isAtLimit={isAtLimit}
                />
              </TabsContent>
            )}

            {canDatabase && (
              <TabsContent value="database" className="mt-6">
                <DatabaseTab
                  isAtLimit={isAtLimit}
                  onAddDatabase={async (connectionId, name, description) => {
                    await onAddDatabase(connectionId, name, description);
                    onImportComplete();
                    onOpenChange(false);
                  }}
                />
              </TabsContent>
            )}

            {canMcp && (
              <TabsContent value="mcp" className="mt-6">
                <McpTab
                  isAtLimit={isAtLimit}
                  onAddMcp={async (connectionId, resourceUris, name, description) => {
                    await onAddMcp(connectionId, resourceUris, name, description);
                    onImportComplete();
                    onOpenChange(false);
                  }}
                />
              </TabsContent>
            )}

            {canFreshdesk && (
              <TabsContent value="freshdesk" className="mt-6">
                <FreshdeskTab
                  isAtLimit={isAtLimit}
                  onAddFreshdesk={async (name, description) => {
                    await onAddFreshdesk(name, description);
                    onImportComplete();
                    onOpenChange(false);
                  }}
                />
              </TabsContent>
            )}

            {canJira && (
              <TabsContent value="jira" className="mt-6">
                <JiraTab
                  isAtLimit={isAtLimit}
                  onAddJira={async (name, description) => {
                    await onAddJira(name, description);
                    onImportComplete();
                    onOpenChange(false);
                  }}
                />
              </TabsContent>
            )}

            {canMixpanel && (
              <TabsContent value="mixpanel" className="mt-6">
                <MixpanelTab
                  isAtLimit={isAtLimit}
                  onAddMixpanel={async (name, description) => {
                    await onAddMixpanel(name, description);
                    onImportComplete();
                    onOpenChange(false);
                  }}
                />
              </TabsContent>
            )}
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
};
