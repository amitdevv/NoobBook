/**
 * AppSettings Component
 * Admin Settings dialog with Notion-style sidebar navigation.
 * Features: Profile, Team Management, API Keys, Integrations, System Settings.
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { X } from '@phosphor-icons/react';
import { Button } from '../ui/button';
import { SettingsSidebar, type SettingsSection } from '../settings/SettingsSidebar';
import {
  ProfileSection,
  TeamSection,
  ApiKeysSection,
  IntegrationsSection,
  SystemSection,
} from '../settings/sections';

interface AppSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userEmail?: string | null;
  userRole?: string;
  userId?: string;
}

export const AppSettings: React.FC<AppSettingsProps> = ({
  open,
  onOpenChange,
  userEmail = null,
  userRole = 'user',
  userId = '',
}) => {
  const isAdmin = userRole === 'admin';
  const [activeSection, setActiveSection] = useState<SettingsSection>('profile');

  // Handle section change with admin check
  const handleSectionChange = (section: SettingsSection) => {
    const adminOnlySections: SettingsSection[] = ['team', 'api-keys', 'system'];
    if (!isAdmin && adminOnlySections.includes(section)) {
      return; // Prevent non-admins from switching to admin sections
    }
    setActiveSection(section);
  };

  // Reset to profile when closing (so next open starts fresh)
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setActiveSection('profile');
    }
    onOpenChange(isOpen);
  };

  const renderSection = () => {
    switch (activeSection) {
      case 'profile':
        return <ProfileSection userEmail={userEmail} userRole={userRole} />;
      case 'team':
        return isAdmin ? <TeamSection currentUserId={userId} /> : null;
      case 'api-keys':
        return isAdmin ? <ApiKeysSection /> : null;
      case 'integrations':
        return <IntegrationsSection />;
      case 'system':
        return isAdmin ? <SystemSection /> : null;
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] p-0 gap-0 overflow-hidden bg-card">
        {/* Header */}
        <DialogHeader className="flex-shrink-0 px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <DialogTitle>Settings</DialogTitle>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => handleOpenChange(false)}
            >
              <X size={18} />
            </Button>
          </div>
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
            {renderSection()}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
