/**
 * ProfileSection Component
 * Displays current user information (email, role).
 */

import React from 'react';
import { User, ShieldCheck } from '@phosphor-icons/react';

interface ProfileSectionProps {
  userEmail: string | null;
  userRole: string;
}

export const ProfileSection: React.FC<ProfileSectionProps> = ({
  userEmail,
  userRole,
}) => {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-stone-900 mb-1">Profile</h2>
        <p className="text-sm text-muted-foreground">
          Your account information
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex items-start gap-4 p-4 rounded-lg border bg-muted/30">
          <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
            <User size={24} className="text-amber-600" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-stone-500 uppercase tracking-wide">
                  Email
                </label>
                <p className="text-sm font-medium text-stone-900 mt-0.5">
                  {userEmail || 'Not available'}
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-stone-500 uppercase tracking-wide">
                  Role
                </label>
                <div className="flex items-center gap-2 mt-0.5">
                  {userRole === 'admin' && (
                    <ShieldCheck size={16} className="text-amber-600" />
                  )}
                  <p className="text-sm font-medium text-stone-900 capitalize">
                    {userRole}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Account details are managed through your authentication provider.
        </p>
      </div>
    </div>
  );
};
