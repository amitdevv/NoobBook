/**
 * ProfileSection Component
 * Displays current user information (email, role) and sign out action.
 */

import React, { useState, useEffect } from 'react';
import { User, Crown, SignOut, Warning, ArrowsClockwise, ChartBar } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { usersAPI } from '@/lib/api/settings';
import type { UserUsage } from '@/lib/api/settings';
import { cn } from '@/lib/utils';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

// ---------------------------------------------------------------------------
// Usage card — shows the user's spending vs their admin-set limit
// ---------------------------------------------------------------------------

const FREQ_LABELS: Record<string, string> = {
  daily: 'daily',
  weekly: 'weekly',
  monthly: 'monthly',
};

const UsageCard: React.FC = () => {
  const [usage, setUsage] = useState<UserUsage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const data = await usersAPI.getMyUsage();
      setUsage(data);
      setLoading(false);
    })();
  }, []);

  if (loading) return null;
  if (!usage || !usage.cost_limit) return null; // No limit set — don't show card

  const pct = usage.usage_percent;
  const remaining = Math.max(usage.cost_limit - usage.current_spend, 0);
  const barColor = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500';
  const freq = usage.reset_frequency ? FREQ_LABELS[usage.reset_frequency] : null;

  return (
    <>
      <Separator />
      <div>
        <h3 className="text-sm font-medium text-stone-800 mb-3 flex items-center gap-2">
          <ChartBar size={16} weight="duotone" className="text-amber-600" />
          Your Usage
        </h3>
        <div className="rounded-lg border bg-gradient-to-br from-stone-50 to-amber-50/30 p-4 space-y-3">
          {/* Progress header */}
          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-stone-800 tabular-nums">
                ${usage.current_spend.toFixed(2)}
              </span>
              <span className="text-sm text-stone-400">/</span>
              <span className="text-sm font-semibold text-stone-600 tabular-nums">
                ${usage.cost_limit.toFixed(2)}
              </span>
            </div>
            <span className={cn(
              'text-xs font-semibold px-1.5 py-0.5 rounded tabular-nums',
              pct >= 90 ? 'bg-red-100 text-red-700'
                : pct >= 70 ? 'bg-amber-100 text-amber-700'
                : 'bg-emerald-100 text-emerald-700',
            )}>
              {pct.toFixed(1)}%
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-2 w-full bg-stone-200/60 rounded-full overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all duration-500', barColor)}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>

          {/* Stats row */}
          <div className="flex justify-between text-[11px] text-stone-500">
            <span>Remaining: <strong className="text-stone-700">${remaining.toFixed(2)}</strong></span>
            {freq && (
              <span className="flex items-center gap-1">
                <ArrowsClockwise size={10} />
                Resets {freq}
              </span>
            )}
          </div>

          {/* Lifetime total */}
          <div className="pt-2 border-t border-stone-200/50 flex justify-between text-[11px] text-stone-400">
            <span>Lifetime total</span>
            <span className="font-medium text-stone-600 tabular-nums">${usage.total_spend.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------

interface ProfileSectionProps {
  userEmail: string | null;
  userRole: string;
  onSignOut?: () => Promise<void>;
}

export const ProfileSection: React.FC<ProfileSectionProps> = ({
  userEmail,
  userRole,
  onSignOut,
}) => {
  const [signOutOpen, setSignOutOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">Profile</h2>
        <p className="text-sm text-muted-foreground">
          Your account information
        </p>
      </div>

      {/* Profile card */}
      <div className="flex items-center gap-4 p-4 rounded-lg border bg-muted/30">
        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
          <User size={24} className="text-amber-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-stone-900 truncate">
            {userEmail || 'Not available'}
          </p>
          {userRole === 'admin' ? (
            <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              <Crown size={12} weight="fill" />
              Admin
            </span>
          ) : (
            <p className="text-xs text-muted-foreground capitalize mt-0.5">
              {userRole}
            </p>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Account details are managed through your authentication provider.
      </p>

      <UsageCard />

      {onSignOut && (
        <>
          <Separator />
          <div>
            <Button
              variant="ghost"
              onClick={() => setSignOutOpen(true)}
              className="bg-red-50 text-red-600 hover:bg-red-100 hover:text-red-700"
            >
              <SignOut size={16} className="mr-2" />
              Sign out
            </Button>
          </div>

          <AlertDialog open={signOutOpen} onOpenChange={setSignOutOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="flex items-center gap-2">
                  <Warning size={20} className="text-destructive" />
                  Sign Out
                </AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to sign out? You'll need to log in again to access your projects.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <Button variant="soft" onClick={() => setSignOutOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    setSignOutOpen(false);
                    onSignOut();
                  }}
                >
                  Sign Out
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      )}
    </div>
  );
};
