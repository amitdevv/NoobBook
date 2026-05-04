/**
 * TeamSection Component
 * Full team management: list users, create, delete, reset password, change roles.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  CircleNotch,
  Plus,
  DotsThreeVertical,
  Key,
  Trash,
  Sliders,
  Infinity as InfinityIcon,
  PencilSimple,
  ArrowCounterClockwise,
  Info,
} from '@phosphor-icons/react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { usersAPI } from '@/lib/api/settings';
import type { UserSummary, ResetFrequency } from '@/lib/api/settings';
import { useToast } from '@/components/ui/use-toast';
import { CreateUserDialog } from '../team/CreateUserDialog';
import { DeleteUserDialog } from '../team/DeleteUserDialog';
import { PasswordDisplay } from '../team/PasswordDisplay';
import { PermissionsModal } from './PermissionsModal';
import { createLogger } from '@/lib/logger';
import { cn } from '@/lib/utils';

const log = createLogger('team-section');

// ---------------------------------------------------------------------------
// Spend limit cell — OpenRouter-inspired with progress bar + popover editor
// ---------------------------------------------------------------------------

const FREQ_LABELS: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
};

const SpendLimitCell: React.FC<{
  userId: string;
  value: number | null;
  resetFrequency: ResetFrequency;
  periodSpend: number;
  onSaved: (userId: string, updates: Partial<UserSummary>) => void;
}> = ({ userId, value, resetFrequency, periodSpend, onSaved }) => {
  const [open, setOpen] = useState(false);
  const [draftLimit, setDraftLimit] = useState('');
  const [draftFreq, setDraftFreq] = useState<string>('none');
  const [saving, setSaving] = useState(false);
  const [confirmingReset, setConfirmingReset] = useState(false);
  const [resetting, setResetting] = useState(false);
  // Track the arming-window timer so we can cancel it on close / re-arm.
  // Without this, a stale 4s timer from a previous open could fire mid-way
  // through a fresh confirmation window and silently disarm the button.
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { success: showSuccess, error: showError } = useToast();

  const cancelResetTimer = () => {
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
  };

  // Cancel any pending arming-window timer when this row unmounts so it
  // doesn't fire against a torn-down state setter.
  useEffect(() => () => cancelResetTimer(), []);

  // Sync draft when popover opens. Also clear the reset confirm-state so a
  // half-armed confirmation from a previous open doesn't carry over, and
  // cancel any in-flight arming timer on close.
  const handleOpen = (isOpen: boolean) => {
    if (isOpen) {
      setDraftLimit(value != null ? String(value) : '');
      setDraftFreq(resetFrequency || 'none');
    } else {
      cancelResetTimer();
    }
    setConfirmingReset(false);
    setOpen(isOpen);
  };

  const handleSave = async () => {
    const newLimit = draftLimit.trim() === '' ? null : parseFloat(draftLimit);
    if (newLimit !== null && (isNaN(newLimit) || newLimit < 0)) {
      showError('Enter a valid dollar amount');
      return;
    }
    const newFreq: ResetFrequency = draftFreq === 'none' ? null : (draftFreq as ResetFrequency);

    setSaving(true);
    try {
      await usersAPI.updateCostLimit(userId, newLimit, newFreq);
      onSaved(userId, {
        cost_limit: newLimit,
        reset_frequency: newFreq,
        period_spend: newFreq !== resetFrequency ? 0 : periodSpend,
      });
      showSuccess(newLimit != null ? `Limit set to $${newLimit}` : 'Limit removed');
      setOpen(false);
    } catch {
      showError('Failed to update');
    } finally {
      setSaving(false);
    }
  };

  // Two-click confirm pattern (matches the LogsModal "Clear logs" flow):
  // first click flips the button into a destructive armed state; a second
  // click within 4s fires the API. After 4s without a follow-up click the
  // button reverts to its neutral state, so an admin who walks away
  // doesn't return to a primed nuke button.
  const handleReset = async () => {
    if (!confirmingReset) {
      cancelResetTimer();
      setConfirmingReset(true);
      resetTimerRef.current = setTimeout(() => {
        setConfirmingReset(false);
        resetTimerRef.current = null;
      }, 4000);
      return;
    }
    cancelResetTimer();
    setConfirmingReset(false);
    setResetting(true);
    try {
      const result = await usersAPI.resetCostPeriod(userId);
      onSaved(userId, {
        cost_limit: result.cost_limit,
        reset_frequency: result.reset_frequency,
        period_spend: result.period_spend,
      });
      showSuccess(`Reset $${result.prior_period_spend.toFixed(2)} spend to $0`);
      setOpen(false);
    } catch {
      showError('Failed to reset spend');
    } finally {
      setResetting(false);
    }
  };

  // Calculate progress
  const currentSpend = resetFrequency ? periodSpend : periodSpend;
  const pct = value && value > 0 ? Math.min((currentSpend / value) * 100, 100) : 0;
  const barColor = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500';

  if (value == null) {
    return (
      <Popover open={open} onOpenChange={handleOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="group/limit inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md text-xs font-medium text-stone-400 hover:bg-stone-100 cursor-pointer transition-all"
          >
            <InfinityIcon size={13} className="flex-shrink-0 opacity-60" />
            <span>Unlimited</span>
            <PencilSimple size={10} className="opacity-0 group-hover/limit:opacity-50 transition-opacity" />
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[240px] p-3 space-y-3">
          <p className="text-xs font-semibold text-stone-700">Set Spending Limit</p>
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-stone-400 select-none">$</span>
            <input
              type="number" min="0" step="1" autoFocus
              value={draftLimit} onChange={(e) => setDraftLimit(e.target.value)}
              placeholder="e.g. 20"
              className="w-full h-8 pl-6 pr-2 text-sm rounded-md border border-stone-200 bg-white text-stone-800 tabular-nums outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-200"
            />
          </div>
          <div>
            <label className="text-[11px] text-stone-500 font-medium">Reset every...</label>
            <select
              value={draftFreq} onChange={(e) => setDraftFreq(e.target.value)}
              className="mt-1 w-full h-8 px-2 text-sm rounded-md border border-stone-200 bg-white text-stone-800 outline-none focus:border-amber-400"
            >
              <option value="none">N/A (lifetime)</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <Button size="sm" className="w-full h-7 text-xs" onClick={handleSave} disabled={saving}>
            {saving ? <CircleNotch size={12} className="animate-spin mr-1" /> : null}
            Save
          </Button>
        </PopoverContent>
      </Popover>
    );
  }

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <button type="button" className="group/limit text-left cursor-pointer hover:bg-stone-50 rounded-md px-2 py-1.5 -mx-2 transition-colors">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-medium text-stone-700 tabular-nums">
              ${currentSpend.toFixed(2)}
            </span>
            <span className="text-[10px] text-stone-400">/</span>
            <span className="text-xs font-semibold text-stone-800 tabular-nums">${value}</span>
            <span className={cn(
              'text-[10px] font-medium px-1 py-0.5 rounded tabular-nums',
              pct >= 90 ? 'bg-red-50 text-red-600' : pct >= 70 ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-600',
            )}>
              {pct.toFixed(0)}%
            </span>
            <PencilSimple size={9} className="opacity-0 group-hover/limit:opacity-40 transition-opacity ml-auto" />
          </div>
          <div className="mt-1 h-1 w-full bg-stone-100 rounded-full overflow-hidden">
            <div className={cn('h-full rounded-full transition-all', barColor)} style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-0.5 text-[10px] text-stone-400">
            {resetFrequency ? `Resets ${FREQ_LABELS[resetFrequency]?.toLowerCase()}` : 'Lifetime'}
          </p>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[240px] p-3 space-y-3">
        <p className="text-xs font-semibold text-stone-700">Edit Spending Limit</p>
        <div className="relative">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-stone-400 select-none">$</span>
          <input
            type="number" min="0" step="1" autoFocus
            value={draftLimit} onChange={(e) => setDraftLimit(e.target.value)}
            placeholder="e.g. 20"
            className="w-full h-8 pl-6 pr-2 text-sm rounded-md border border-stone-200 bg-white text-stone-800 tabular-nums outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-200"
          />
        </div>
        <div>
          <label className="text-[11px] text-stone-500 font-medium">Reset every...</label>
          <select
            value={draftFreq} onChange={(e) => setDraftFreq(e.target.value)}
            className="mt-1 w-full h-8 px-2 text-sm rounded-md border border-stone-200 bg-white text-stone-800 outline-none focus:border-amber-400"
          >
            <option value="none">N/A (lifetime)</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="soft" className="flex-1 h-7 text-xs" onClick={() => {
            setDraftLimit('');
            setDraftFreq('none');
          }}>
            Clear
          </Button>
          <Button size="sm" className="flex-1 h-7 text-xs" onClick={handleSave} disabled={saving}>
            {saving ? <CircleNotch size={12} className="animate-spin mr-1" /> : null}
            Save
          </Button>
        </div>

        {/* Hard-reset row — separated by a divider so it reads as a
            distinct destructive action, not a sibling of "Save". Only
            shown when the user actually has accumulated spend; if
            period_spend is already $0 there's nothing to reset. */}
        {periodSpend > 0 && (
          <div className="pt-3 border-t border-stone-100 space-y-2">
            <p className="text-[11px] text-stone-500">
              Current period: <span className="tabular-nums text-stone-700 font-medium">${periodSpend.toFixed(2)}</span> spent
            </p>
            <button
              type="button"
              onClick={handleReset}
              disabled={resetting}
              className={cn(
                'w-full h-7 inline-flex items-center justify-center gap-1.5 rounded-md text-xs font-medium transition-colors',
                confirmingReset
                  ? 'bg-rose-50 text-rose-700 ring-1 ring-rose-200 hover:bg-rose-100'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900',
                resetting && 'opacity-60 cursor-not-allowed',
              )}
            >
              {resetting ? (
                <CircleNotch size={12} className="animate-spin" />
              ) : (
                <ArrowCounterClockwise size={12} />
              )}
              {confirmingReset
                ? `Click again to confirm — resets $${periodSpend.toFixed(2)}`
                : 'Reset spend now'}
            </button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

interface TeamSectionProps {
  currentUserId: string;
}

export const TeamSection: React.FC<TeamSectionProps> = ({ currentUserId }) => {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState<{ [key: string]: boolean }>({});

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [resetPasswordDialogOpen, setResetPasswordDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resettingPassword, setResettingPassword] = useState(false);
  const [editingPermissionsUser, setEditingPermissionsUser] = useState<UserSummary | null>(null);

  // Default-limit banner state. `defaultConfig === null` means we haven't
  // fetched yet (avoid a flash of the banner on first paint). Once
  // fetched, the banner only renders when there are unlimited users AND
  // the operator hasn't opted out via NOOBBOOK_DEFAULT_USER_COST_LIMIT=0.
  // The same payload also carries the standardized reset anchor (default
  // Sunday 09:00 IST) and the count of users currently on a reset
  // frequency — drives the schedule subtitle + "Realign now" link.
  const [defaultConfig, setDefaultConfig] = useState<{
    default_limit: number | null;
    default_frequency: ResetFrequency;
    unlimited_count: number;
    opted_out: boolean;
    anchor?: {
      tz: string;
      hour: number;
      weekday_name: string;
      weekly_label: string;
      [key: string]: unknown;
    };
    users_with_frequency?: number;
  } | null>(null);
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [applying, setApplying] = useState(false);
  const [realignDialogOpen, setRealignDialogOpen] = useState(false);
  const [realigning, setRealigning] = useState(false);

  const { success, error } = useToast();

  useEffect(() => {
    loadUsers();
    loadDefaultConfig();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const list = await usersAPI.listUsers();
      setUsers(list);
    } catch (err) {
      log.error({ err }, 'failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const loadDefaultConfig = async () => {
    try {
      const cfg = await usersAPI.getDefaultCostLimit();
      setDefaultConfig(cfg);
    } catch (err) {
      // Non-fatal — banner just doesn't appear. Don't toast; failing to
      // load this is informational, not blocking.
      log.error({ err }, 'failed to load default cost limit config');
    }
  };

  const handleApplyDefault = async () => {
    setApplying(true);
    try {
      const result = await usersAPI.applyDefaultCostLimit();
      if (result.opted_out) {
        error(
          'Default spending limit is opted-out via NOOBBOOK_DEFAULT_USER_COST_LIMIT=0',
        );
        return;
      }
      success(
        `Applied $${result.default_limit} / ${result.default_frequency} to ${result.updated} ${result.updated === 1 ? 'user' : 'users'}`,
      );
      setApplyDialogOpen(false);
      // Refresh both the user list (rows now show their new limits) and
      // the default-config (unlimited_count drops, hiding the banner).
      await Promise.all([loadUsers(), loadDefaultConfig()]);
    } catch (err) {
      log.error({ err }, 'failed to apply default cost limit');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to apply default limit');
    } finally {
      setApplying(false);
    }
  };

  const handleRealignSpendingPeriods = async () => {
    setRealigning(true);
    try {
      const result = await usersAPI.realignSpendingPeriods();
      success(
        `Realigned ${result.updated} ${result.updated === 1 ? 'user' : 'users'} to ${result.anchor.weekly_label}`,
      );
      setRealignDialogOpen(false);
      // Refresh both — rows now show $0 spend with the new aligned start.
      await Promise.all([loadUsers(), loadDefaultConfig()]);
    } catch (err) {
      log.error({ err }, 'failed to realign spending periods');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to realign spending periods');
    } finally {
      setRealigning(false);
    }
  };

  const handleRoleChange = async (userId: string, role: 'admin' | 'user') => {
    setRoleSaving((prev) => ({ ...prev, [userId]: true }));
    try {
      const updated = await usersAPI.updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      success('Role updated');
    } catch (err) {
      log.error({ err }, 'failed to update role');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to update user role');
    } finally {
      setRoleSaving((prev) => ({ ...prev, [userId]: false }));
    }
  };

  const handleUserCreated = (user: UserSummary) => {
    setUsers((prev) => [...prev, user]);
  };

  const handleUserDeleted = (userId: string) => {
    setUsers((prev) => prev.filter((u) => u.id !== userId));
  };

  const handleResetPassword = async () => {
    if (!selectedUser) return;

    setResettingPassword(true);
    try {
      const { password } = await usersAPI.resetPassword(selectedUser.id);
      setResetPassword(password);
      success('Password reset successfully');
    } catch (err) {
      log.error({ err }, 'failed to reset password');
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to reset password');
    } finally {
      setResettingPassword(false);
    }
  };

  const openDeleteDialog = (user: UserSummary) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const openResetPasswordDialog = (user: UserSummary) => {
    setSelectedUser(user);
    setResetPassword('');
    setResetPasswordDialogOpen(true);
  };

  const closeResetPasswordDialog = () => {
    setResetPasswordDialogOpen(false);
    setSelectedUser(null);
    setResetPassword('');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <CircleNotch size={32} className="animate-spin" />
      </div>
    );
  }

  // Banner is shown when:
  //  • we've loaded the default config
  //  • the operator hasn't opted out via env (NOOBBOOK_DEFAULT_USER_COST_LIMIT=0)
  //  • at least one user has no spending limit set
  const showApplyDefaultBanner =
    defaultConfig !== null &&
    !defaultConfig.opted_out &&
    defaultConfig.unlimited_count > 0;

  // Schedule subtitle is shown when at least one user is on a reset
  // frequency. Surfaces the global anchor (e.g. "Resets every Sunday
  // at 09:00 Asia/Kolkata") and a small "Realign now" link the admin
  // can use to bulk-snap existing users to the schedule and zero
  // their period_spend.
  const showScheduleSubtitle =
    defaultConfig !== null &&
    defaultConfig.anchor !== undefined &&
    (defaultConfig.users_with_frequency ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-medium text-stone-900 mb-1">Team</h2>
          <p className="text-sm text-muted-foreground">
            Manage users and their access levels
          </p>
          {showScheduleSubtitle && defaultConfig?.anchor && (
            <p className="mt-1.5 text-[12px] text-stone-500 leading-relaxed">
              <span className="text-stone-600">Spending limits reset:</span>{' '}
              <span className="text-stone-700 tabular-nums">
                {defaultConfig.anchor.weekly_label}
              </span>
              <span className="mx-1.5 text-stone-300">·</span>
              <button
                type="button"
                onClick={() => setRealignDialogOpen(true)}
                className="text-stone-700 underline underline-offset-4 decoration-amber-600 decoration-1 hover:decoration-stone-900 transition-colors"
              >
                Realign existing users
              </button>
            </p>
          )}
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus size={16} className="mr-2" />
          Add User
        </Button>
      </div>

      {showApplyDefaultBanner && defaultConfig && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 py-3 rounded-md border border-amber-200/80 bg-amber-50/60">
          <div className="flex items-start gap-2.5 text-sm">
            <Info size={16} className="text-amber-700 flex-shrink-0 mt-0.5" weight="fill" />
            <div className="text-stone-700 leading-relaxed">
              <span className="font-medium text-stone-900">
                {defaultConfig.unlimited_count}{' '}
                {defaultConfig.unlimited_count === 1 ? 'user has' : 'users have'} no spending limit set.
              </span>
              <span className="block sm:inline text-stone-500 sm:ml-1.5">
                Apply the default of{' '}
                <span className="font-medium tabular-nums text-stone-700">
                  ${defaultConfig.default_limit}
                </span>{' '}
                / {defaultConfig.default_frequency} to keep spend tracked across the team.
              </span>
            </div>
          </div>
          <Button
            size="sm"
            variant="default"
            onClick={() => setApplyDialogOpen(true)}
            className="self-start sm:self-auto flex-shrink-0"
          >
            Apply default
          </Button>
        </div>
      )}

      {users.length === 0 ? (
        <div className="text-center py-8 border rounded-lg bg-muted/20">
          <p className="text-muted-foreground">No users found.</p>
          <p className="text-sm text-muted-foreground mt-1">
            Create an account to get started.
          </p>
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Spend Limit</TableHead>
                <TableHead>Permissions</TableHead>
                <TableHead className="w-[70px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {user.email || user.id}
                    {user.id === currentUserId && (
                      <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={user.role as string}
                      onValueChange={(v) => handleRoleChange(user.id, v as 'admin' | 'user')}
                      disabled={roleSaving[user.id]}
                    >
                      <SelectTrigger className="w-[120px]">
                        {roleSaving[user.id] ? (
                          <CircleNotch size={14} className="animate-spin" />
                        ) : (
                          <SelectValue />
                        )}
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="user">User</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <SpendLimitCell
                      userId={user.id}
                      value={user.cost_limit}
                      resetFrequency={user.reset_frequency}
                      periodSpend={user.period_spend ?? 0}
                      onSaved={(uid, updates) => {
                        setUsers((prev) =>
                          prev.map((u) => (u.id === uid ? { ...u, ...updates } : u))
                        );
                      }}
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="soft"
                      size="sm"
                      className="h-7 text-xs gap-1.5"
                      onClick={() => setEditingPermissionsUser(user)}
                    >
                      <Sliders size={14} />
                      Edit
                    </Button>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <DotsThreeVertical size={18} />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openResetPasswordDialog(user)}>
                          <Key size={16} className="mr-2" />
                          Reset Password
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => openDeleteDialog(user)}
                          disabled={user.id === currentUserId}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash size={16} className="mr-2" />
                          Delete User
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create User Dialog */}
      <CreateUserDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onUserCreated={handleUserCreated}
      />

      {/* Delete User Dialog */}
      {selectedUser && (
        <DeleteUserDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          userId={selectedUser.id}
          userEmail={selectedUser.email || selectedUser.id}
          onUserDeleted={handleUserDeleted}
        />
      )}

      {/* Edit Permissions Modal */}
      {editingPermissionsUser && (
        <PermissionsModal
          open={!!editingPermissionsUser}
          onOpenChange={(open) => { if (!open) setEditingPermissionsUser(null); }}
          userId={editingPermissionsUser.id}
          userEmail={editingPermissionsUser.email || ''}
        />
      )}

      {/* Reset Password Dialog */}
      <Dialog open={resetPasswordDialogOpen} onOpenChange={closeResetPasswordDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
            <DialogDescription>
              {resetPassword
                ? 'Share this new password with the user securely.'
                : `Generate a new password for ${selectedUser?.email || 'this user'}.`}
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            {resetPassword ? (
              <PasswordDisplay
                password={resetPassword}
                email={selectedUser?.email || selectedUser?.id || ''}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                The user will need to use this new password to log in.
                Make sure to share it with them securely.
              </p>
            )}
          </div>

          <DialogFooter>
            {resetPassword ? (
              <Button onClick={closeResetPasswordDialog}>Done</Button>
            ) : (
              <>
                <Button variant="soft" onClick={closeResetPasswordDialog} disabled={resettingPassword}>
                  Cancel
                </Button>
                <Button onClick={handleResetPassword} disabled={resettingPassword}>
                  {resettingPassword ? (
                    <>
                      <CircleNotch size={16} className="animate-spin mr-2" />
                      Generating...
                    </>
                  ) : (
                    'Generate New Password'
                  )}
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Apply-default-cost-limit confirm dialog. Defensive guard on
          defaultConfig (the banner already requires it to be loaded
          before opening, but a typing-level null check keeps TS happy). */}
      {defaultConfig && !defaultConfig.opted_out && (
        <Dialog open={applyDialogOpen} onOpenChange={(o) => !applying && setApplyDialogOpen(o)}>
          <DialogContent className="sm:max-w-[460px]">
            <DialogHeader>
              <DialogTitle>Apply default spending limit</DialogTitle>
              <DialogDescription className="leading-relaxed">
                Set{' '}
                <span className="font-medium text-stone-800 tabular-nums">
                  ${defaultConfig.default_limit}
                </span>{' '}
                / {defaultConfig.default_frequency} as the spending limit for all{' '}
                <span className="font-medium text-stone-800">
                  {defaultConfig.unlimited_count}{' '}
                  {defaultConfig.unlimited_count === 1 ? 'user' : 'users'}
                </span>{' '}
                without one. Their period spend starts at $0 and resets{' '}
                {defaultConfig.default_frequency} from now.
              </DialogDescription>
            </DialogHeader>
            <p className="text-xs text-stone-500 leading-relaxed">
              Existing users with a limit (any value) are skipped. You can adjust
              individual limits afterward from the Spend Limit column.
            </p>
            <DialogFooter>
              <Button
                variant="soft"
                onClick={() => setApplyDialogOpen(false)}
                disabled={applying}
              >
                Cancel
              </Button>
              <Button onClick={handleApplyDefault} disabled={applying}>
                {applying ? (
                  <>
                    <CircleNotch size={14} className="animate-spin mr-2" />
                    Applying…
                  </>
                ) : (
                  <>
                    Apply to {defaultConfig.unlimited_count}{' '}
                    {defaultConfig.unlimited_count === 1 ? 'user' : 'users'}
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Realign-spending-periods confirm dialog. Bulk-snaps every user
          with a reset_frequency to the standardized anchor (default
          Sunday 09:00 IST) and zeroes period_spend — the "full reset"
          semantic the operator opted into. */}
      {defaultConfig?.anchor && (
        <Dialog open={realignDialogOpen} onOpenChange={(o) => !realigning && setRealignDialogOpen(o)}>
          <DialogContent className="sm:max-w-[480px]">
            <DialogHeader>
              <DialogTitle>Realign spending periods</DialogTitle>
              <DialogDescription className="leading-relaxed">
                Snap every user with a reset frequency to the global
                schedule and zero out their current period spend.
              </DialogDescription>
            </DialogHeader>
            <div className="rounded-md border border-amber-100/80 bg-amber-50/40 px-3.5 py-2.5 text-[12px] text-stone-600 leading-relaxed space-y-1.5">
              <p>
                <span className="text-stone-500">Schedule:</span>{' '}
                <span className="font-medium text-stone-800">
                  {defaultConfig.anchor.weekly_label}
                </span>
              </p>
              <p>
                <span className="text-stone-500">Affected users:</span>{' '}
                <span className="font-medium text-stone-800 tabular-nums">
                  {defaultConfig.users_with_frequency ?? 0}
                </span>{' '}
                <span className="text-stone-500">
                  ({defaultConfig.users_with_frequency === 1 ? 'has' : 'have'} a daily / weekly / monthly reset)
                </span>
              </p>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Each user's <span className="font-medium text-stone-700">period_spend</span> resets to <span className="tabular-nums">$0</span> and their next auto-reset will fire at the same wall-clock instant as everyone else. Users without a reset frequency (lifetime caps, unlimited) are skipped. Idempotent — running twice produces the same state.
            </p>
            <DialogFooter>
              <Button
                variant="soft"
                onClick={() => setRealignDialogOpen(false)}
                disabled={realigning}
              >
                Cancel
              </Button>
              <Button onClick={handleRealignSpendingPeriods} disabled={realigning}>
                {realigning ? (
                  <>
                    <CircleNotch size={14} className="animate-spin mr-2" />
                    Realigning…
                  </>
                ) : (
                  <>
                    Realign {defaultConfig.users_with_frequency ?? 0}{' '}
                    {defaultConfig.users_with_frequency === 1 ? 'user' : 'users'}
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};
