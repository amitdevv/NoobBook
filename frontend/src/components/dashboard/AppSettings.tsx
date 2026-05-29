/**
 * AppSettings Component
 * Admin Settings dialog with Notion-style sidebar navigation.
 * Features: Profile, Team Management, API Keys, Integrations, System Settings.
 */

import React, { useState, useEffect, lazy, Suspense } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { SettingsSidebar, type SettingsSection } from '../settings/SettingsSidebar';

// Settings sections are lazy-loaded from their own files (not the barrel) so the
// heavy ones — DesignSection pulls @uiw/react-md-editor + the full refractor
// grammar set — aren't bundled into / modulepreloaded on the dashboard. Each
// section's code loads on first navigation to it.
const ProfileSection = lazy(() => import('../settings/sections/ProfileSection').then((m) => ({ default: m.ProfileSection })));
const TeamSection = lazy(() => import('../settings/sections/TeamSection').then((m) => ({ default: m.TeamSection })));
const ApiKeysSection = lazy(() => import('../settings/sections/ApiKeysSection').then((m) => ({ default: m.ApiKeysSection })));
const IntegrationsSection = lazy(() => import('../settings/sections/IntegrationsSection').then((m) => ({ default: m.IntegrationsSection })));
const SystemSection = lazy(() => import('../settings/sections/SystemSection').then((m) => ({ default: m.SystemSection })));
const DesignSection = lazy(() => import('../settings/sections/DesignSection').then((m) => ({ default: m.DesignSection })));
const ModelsSection = lazy(() => import('../settings/sections/ModelsSection').then((m) => ({ default: m.ModelsSection })));
const PromptsSection = lazy(() => import('../settings/sections/PromptsSection').then((m) => ({ default: m.PromptsSection })));
const LogsSection = lazy(() => import('../settings/sections/LogsSection').then((m) => ({ default: m.LogsSection })));

interface AppSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userEmail?: string | null;
  userRole?: string;
  userId?: string;
  onSignOut?: () => Promise<void>;
}

export const AppSettings: React.FC<AppSettingsProps> = ({
  open,
  onOpenChange,
  userEmail = null,
  userRole = 'user',
  userId = '',
  onSignOut,
}) => {
  const isAdmin = userRole === 'admin';
  const [activeSection, setActiveSection] = useState<SettingsSection>('profile');
  const [mountedSections, setMountedSections] = useState<Set<SettingsSection>>(
    () => new Set(['profile'])
  );

  // Handle section change with admin check
  const handleSectionChange = (section: SettingsSection) => {
    const adminOnlySections: SettingsSection[] = ['team', 'api-keys', 'models', 'prompts', 'design', 'system', 'logs'];
    if (!isAdmin && adminOnlySections.includes(section)) {
      return; // Prevent non-admins from switching to admin sections
    }
    setMountedSections((prev) => {
      if (prev.has(section)) return prev;
      const next = new Set(prev);
      next.add(section);
      return next;
    });
    setActiveSection(section);
  };

  // Cross-section navigation hook — PromptEditor's "Edit in Models →"
  // link dispatches this event so the user jumps from prompt editing
  // straight to the model picker without closing the dialog.
  useEffect(() => {
    const handler = (e: Event) => {
      const next = (e as CustomEvent<SettingsSection>).detail;
      if (!next) return;
      handleSectionChange(next);
    };
    window.addEventListener('noobbook:settings:switch-section', handler);
    return () => window.removeEventListener('noobbook:settings:switch-section', handler);
    // handleSectionChange is stable for our purposes (closes over isAdmin
    // which doesn't change during a single dialog session). Re-listening
    // on every isAdmin flip is fine and rare.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  // Reset to profile when closing (so next open starts fresh)
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setActiveSection('profile');
    }
    onOpenChange(isOpen);
  };

  const renderSection = (section: SettingsSection) => {
    switch (section) {
      case 'profile':
        return <ProfileSection userEmail={userEmail} userRole={userRole} onSignOut={onSignOut} />;
      case 'team':
        return isAdmin ? <TeamSection currentUserId={userId} /> : null;
      case 'api-keys':
        return isAdmin ? <ApiKeysSection /> : null;
      case 'models':
        return isAdmin ? <ModelsSection /> : null;
      case 'prompts':
        return isAdmin ? <PromptsSection /> : null;
      case 'integrations':
        return <IntegrationsSection isAdmin={isAdmin} />;
      case 'design':
        return isAdmin ? <DesignSection /> : null;
      case 'system':
        return isAdmin ? <SystemSection /> : null;
      case 'logs':
        return isAdmin ? <LogsSection /> : null;
      default:
        return null;
    }
  };

  const visibleSections = Array.from(mountedSections).filter((section) => {
    const adminOnlySections: SettingsSection[] = ['team', 'api-keys', 'models', 'prompts', 'design', 'system', 'logs'];
    return isAdmin || !adminOnlySections.includes(section);
  });

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-6xl h-[85vh] p-0 gap-0 overflow-hidden bg-card flex flex-col">
        {/* Header */}
        <DialogHeader className="flex-shrink-0 px-6 py-3 border-b">
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>

        {/* Main content with sidebar */}
        <div className="flex flex-1 min-h-0">
          {/* Sidebar */}
          <SettingsSidebar
            activeSection={activeSection}
            onSectionChange={handleSectionChange}
            isAdmin={isAdmin}
          />

          {/* Content area */}
          <div className="flex-1 overflow-y-auto p-6 bg-white">
            <div className="h-full">
              {visibleSections.map((section) => (
                <div
                  key={section}
                  className={section === activeSection ? 'h-full' : 'hidden'}
                >
                  {/* Per-section Suspense so a lazy section loading only shows a
                      spinner inside its own (often hidden) div — it never blanks
                      out the currently-visible section. */}
                  <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
                    {renderSection(section)}
                  </Suspense>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
