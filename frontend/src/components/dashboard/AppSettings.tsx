import React, { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Separator } from '../ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  Eye,
  EyeSlash,
  Trash,
  Warning,
  CheckCircle,
  XCircle,
  CircleNotch,
  GoogleDriveLogo,
  SignOut,
  ArrowSquareOut,
} from '@phosphor-icons/react';
import { settingsAPI, processingSettingsAPI, googleDriveAPI, databasesAPI, usersAPI } from '@/lib/api/settings';
import type { ApiKey, AvailableTier, GoogleStatus, DatabaseConnection, DatabaseType, UserSummary } from '@/lib/api/settings';
import { useToast } from '../ui/toast';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';

/**
 * AppSettings Component
 * Educational Note: Manages API keys and application settings in a dialog.
 * Extracted from Dashboard to follow the principle of component modularity.
 *
 * Features:
 * - API key CRUD operations
 * - Real-time validation
 * - Masked display for security
 * - Organized by category (AI, Storage, Utility)
 */

interface AppSettingsProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface ValidationState {
  [key: string]: {
    validating: boolean;
    valid?: boolean;
    message?: string;
  };
}

export const AppSettings: React.FC<AppSettingsProps> = ({ open, onOpenChange }) => {
  // UI State
  const [showApiKeys, setShowApiKeys] = useState<{ [key: string]: boolean }>({});

  // API Keys State
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [modifiedKeys, setModifiedKeys] = useState<{ [key: string]: string }>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationState, setValidationState] = useState<ValidationState>({});

  // Database Connections State
  const [dbConnections, setDbConnections] = useState<DatabaseConnection[]>([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbCreating, setDbCreating] = useState(false);
  const [dbValidating, setDbValidating] = useState(false);
  const [showDbUri, setShowDbUri] = useState(false);
  const [dbValidation, setDbValidation] = useState<{ valid?: boolean; message?: string }>({});
  const [dbForm, setDbForm] = useState<{
    name: string;
    db_type: DatabaseType;
    connection_uri: string;
    description: string;
  }>({
    name: '',
    db_type: 'postgresql',
    connection_uri: '',
    description: '',
  });

  // Processing Settings State
  const [availableTiers, setAvailableTiers] = useState<AvailableTier[]>([]);
  const [selectedTier, setSelectedTier] = useState<number>(1);
  const [tierSaving, setTierSaving] = useState(false);

  // Google Drive State
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus>({
    configured: false,
    connected: false,
    email: null,
  });
  const [googleLoading, setGoogleLoading] = useState(false);

  // User Roles State
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [roleSaving, setRoleSaving] = useState<{ [key: string]: boolean }>({});

  // Toast notifications
  const { success, error, info } = useToast();

  // Load API keys, processing settings, and Google status when dialog opens
  useEffect(() => {
    if (open) {
      loadApiKeys();
      loadProcessingSettings();
      loadGoogleStatus();
      loadDatabases();
      loadUsers();
    }
  }, [open]);

  /**
   * Load Google Drive connection status
   * Educational Note: Checks if OAuth is configured and if user is connected
   */
  const loadGoogleStatus = async () => {
    try {
      const status = await googleDriveAPI.getStatus();
      setGoogleStatus(status);
    } catch (err) {
      console.error('Failed to load Google status:', err);
    }
  };

  /**
   * Handle Google Drive connection
   * Educational Note: Opens Google OAuth in new window for user to grant access
   */
  const handleGoogleConnect = async () => {
    setGoogleLoading(true);
    try {
      const authUrl = await googleDriveAPI.getAuthUrl();
      if (authUrl) {
        // Open Google OAuth in new window
        window.open(authUrl, '_blank', 'width=500,height=600');
        info('Complete authentication in the new window');
        // Poll for status change
        const pollInterval = setInterval(async () => {
          const status = await googleDriveAPI.getStatus();
          if (status.connected) {
            clearInterval(pollInterval);
            setGoogleStatus(status);
            setGoogleLoading(false);
            success(`Connected as ${status.email}`);
          }
        }, 2000);
        // Stop polling after 2 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setGoogleLoading(false);
        }, 120000);
      } else {
        error('Failed to get Google auth URL. Check your credentials.');
        setGoogleLoading(false);
      }
    } catch (err) {
      console.error('Error connecting Google:', err);
      error('Failed to connect Google Drive');
      setGoogleLoading(false);
    }
  };

  /**
   * Handle Google Drive disconnection
   * Educational Note: Removes stored OAuth tokens
   */
  const handleGoogleDisconnect = async () => {
    setGoogleLoading(true);
    try {
      const disconnected = await googleDriveAPI.disconnect();
      if (disconnected) {
        setGoogleStatus({ configured: googleStatus.configured, connected: false, email: null });
        success('Google Drive disconnected');
      } else {
        error('Failed to disconnect Google Drive');
      }
    } catch (err) {
      console.error('Error disconnecting Google:', err);
      error('Failed to disconnect Google Drive');
    } finally {
      setGoogleLoading(false);
    }
  };

  /**
   * Load processing settings from backend
   * Educational Note: Fetches tier configuration for parallel processing
   */
  const loadProcessingSettings = async () => {
    try {
      const { settings, available_tiers } = await processingSettingsAPI.getSettings();
      setAvailableTiers(available_tiers);
      setSelectedTier(settings.anthropic_tier);
    } catch (err) {
      console.error('Failed to load processing settings:', err);
      // Don't show error toast - processing settings are optional
    }
  };

  /**
   * Handle tier change
   * Educational Note: Saves the selected tier immediately
   */
  const handleTierChange = async (tierValue: string) => {
    const tier = parseInt(tierValue, 10);
    setTierSaving(true);
    try {
      await processingSettingsAPI.updateSettings({ anthropic_tier: tier });
      setSelectedTier(tier);
      success('Processing tier updated');
    } catch (err) {
      console.error('Failed to update tier:', err);
      error('Failed to update processing tier');
    } finally {
      setTierSaving(false);
    }
  };

  /**
   * Load API keys from backend
   * Educational Note: Fetches current API key status with masked values
   */
  const loadApiKeys = async () => {
    setLoading(true);
    try {
      const keys = await settingsAPI.getApiKeys();
      setApiKeys(keys);
      // Clear modified keys when loading fresh data
      setModifiedKeys({});
    } catch (err) {
      console.error('Failed to load API keys:', err);
      error('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load database connections from backend
   */
  const loadDatabases = async () => {
    setDbLoading(true);
    try {
      const dbs = await databasesAPI.listDatabases();
      setDbConnections(dbs);
    } catch (err) {
      console.error('Failed to load databases:', err);
      // Don't block settings UI for DB failures
    } finally {
      setDbLoading(false);
    }
  };

  const loadUsers = async () => {
    setUsersLoading(true);
    try {
      const list = await usersAPI.listUsers();
      setUsers(list);
    } catch (err) {
      console.error('Failed to load users:', err);
      // Admin-only endpoint; ignore if unavailable
    } finally {
      setUsersLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, role: 'admin' | 'user') => {
    setRoleSaving((prev) => ({ ...prev, [userId]: true }));
    try {
      const updated = await usersAPI.updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      success('Role updated');
    } catch (err) {
      console.error('Failed to update role:', err);
      error('Failed to update user role');
    } finally {
      setRoleSaving((prev) => ({ ...prev, [userId]: false }));
    }
  };

  const handleValidateDatabase = async () => {
    setDbValidating(true);
    try {
      const result = await databasesAPI.validateDatabase(dbForm.db_type, dbForm.connection_uri);
      setDbValidation(result);
      if (result.valid) {
        success(result.message || 'Connection successful');
      } else {
        error(result.message || 'Validation failed');
      }
    } finally {
      setDbValidating(false);
    }
  };

  const handleCreateDatabase = async () => {
    setDbCreating(true);
    try {
      await databasesAPI.createDatabase({
        name: dbForm.name.trim(),
        db_type: dbForm.db_type,
        connection_uri: dbForm.connection_uri.trim(),
        description: dbForm.description.trim() || undefined,
      });
      success('Database connection saved');
      setDbForm({ name: '', db_type: 'postgresql', connection_uri: '', description: '' });
      setDbValidation({});
      await loadDatabases();
    } catch (err) {
      console.error('Failed to create database:', err);
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to save database connection');
    } finally {
      setDbCreating(false);
    }
  };

  const handleDeleteDatabase = async (connectionId: string) => {
    try {
      await databasesAPI.deleteDatabase(connectionId);
      success('Database connection deleted');
      await loadDatabases();
    } catch (err) {
      console.error('Failed to delete database:', err);
      const axiosErr = err as { response?: { data?: { error?: string } } };
      error(axiosErr.response?.data?.error || 'Failed to delete database connection');
    }
  };

  /**
   * Save all modified API keys to backend
   * Educational Note: Only sends keys that were actually modified to reduce
   * unnecessary writes to the .env file
   */
  const handleSave = async () => {
    setSaving(true);
    try {
      // Prepare updates - only send modified keys
      const updates = Object.entries(modifiedKeys).map(([id, value]) => ({
        id,
        value
      }));

      if (updates.length > 0) {
        await settingsAPI.updateApiKeys(updates);
        success(`Successfully saved ${updates.length} API key${updates.length > 1 ? 's' : ''}`);

        // Clear modified keys after successful save
        setModifiedKeys({});
        // Clear validation states after save
        setValidationState({});

        // Reload to get fresh masked values
        await loadApiKeys();
      } else {
        info('No changes to save');
      }

      onOpenChange(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error('Failed to save API keys:', err);
      error(`Failed to save API keys: ${errorMessage}`);
    } finally {
      setSaving(false);
    }
  };

  /**
   * Update an API key value in local state
   * Educational Note: Tracks changes locally without immediately saving,
   * allowing users to make multiple edits before saving
   */
  const updateApiKey = (id: string, value: string) => {
    // Track modified keys separately
    setModifiedKeys(prev => ({ ...prev, [id]: value }));
    // Update display immediately
    setApiKeys(prev => prev.map(key =>
      key.id === id ? { ...key, value } : key
    ));
  };

  /**
   * Toggle visibility of an API key (show/hide)
   */
  const toggleShowApiKey = (id: string) => {
    setShowApiKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  /**
   * Delete an API key from backend
   * Educational Note: This removes the key from .env file
   */
  const deleteApiKey = async (id: string) => {
    try {
      await settingsAPI.deleteApiKey(id);
      // Clear from modified keys
      setModifiedKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[id];
        return newKeys;
      });
      // Update display
      setApiKeys(prev => prev.map(key =>
        key.id === id ? { ...key, value: '', is_set: false } : key
      ));
      success('API key deleted successfully');
    } catch (err) {
      console.error('Failed to delete API key:', err);
      error('Failed to delete API key');
    }
  };

  /**
   * Validate an API key by making a test request, then auto-save if valid
   * Educational Note: This combines validation and saving in one step for better UX.
   * If the key works, we immediately save it to the .env file.
   */
  const validateApiKey = async (id: string) => {
    const value = modifiedKeys[id] || apiKeys.find(k => k.id === id)?.value || '';
    const keyName = apiKeys.find(k => k.id === id)?.name || id;

    // Don't validate masked values
    if (value.includes('***')) {
      info('Cannot validate a masked API key. Please enter a new key.');
      return;
    }

    setValidationState(prev => ({
      ...prev,
      [id]: { validating: true }
    }));

    try {
      // Step 1: Validate the API key
      const result = await settingsAPI.validateApiKey(id, value);

      if (result.valid) {
        // Step 2: If validation succeeds, immediately save the key
        try {
          await settingsAPI.updateApiKeys([{ id, value }]);

          // Remove from modified keys since it's now saved
          setModifiedKeys(prev => {
            const newKeys = { ...prev };
            delete newKeys[id];
            return newKeys;
          });

          // Update validation state to show success
          setValidationState(prev => ({
            ...prev,
            [id]: {
              validating: false,
              valid: true,
              message: result.message
            }
          }));

          // Show success message
          success(`${keyName} validated and saved successfully!`);

          // Reload API keys to get fresh masked values
          await loadApiKeys();
        } catch (saveErr) {
          const saveErrorMessage = saveErr instanceof Error ? saveErr.message : 'Failed to save';
          setValidationState(prev => ({
            ...prev,
            [id]: {
              validating: false,
              valid: false,
              message: `Validation succeeded but save failed: ${saveErrorMessage}`
            }
          }));
          error(`Failed to save ${keyName}: ${saveErrorMessage}`);
        }
      } else {
        // Validation failed
        setValidationState(prev => ({
          ...prev,
          [id]: {
            validating: false,
            valid: false,
            message: result.message
          }
        }));
        error(`${keyName} validation failed: ${result.message}`);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Validation failed';
      setValidationState(prev => ({
        ...prev,
        [id]: {
          validating: false,
          valid: false,
          message: errorMessage
        }
      }));
      error(`Failed to validate ${keyName}: ${errorMessage}`);
    }
  };

  /**
   * Render a single API key input field with controls
   * Educational Note: Extracted to a separate function to follow DRY principle
   * and make the component more maintainable
   */
  const renderApiKeyField = (apiKey: ApiKey) => (
    <div key={apiKey.id} className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="flex items-center gap-2">
          {apiKey.name}
          {apiKey.required && (
            <span className="text-xs text-destructive">*Required</span>
          )}
        </Label>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => toggleShowApiKey(apiKey.id)}
          >
            {showApiKeys[apiKey.id] ? (
              <EyeSlash size={16} />
            ) : (
              <Eye size={16} />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => deleteApiKey(apiKey.id)}
            disabled={!apiKey.value && !apiKey.is_set}
          >
            <Trash size={16} />
          </Button>
        </div>
      </div>
      <div className="flex gap-2">
        <Input
          type={showApiKeys[apiKey.id] ? 'text' : 'password'}
          placeholder={`Enter ${apiKey.name} key...`}
          value={modifiedKeys[apiKey.id] !== undefined ? modifiedKeys[apiKey.id] : apiKey.value}
          onChange={(e) => updateApiKey(apiKey.id, e.target.value)}
          className="font-mono text-sm flex-1"
        />
        <Button
          variant="default"
          size="sm"
          onClick={() => validateApiKey(apiKey.id)}
          disabled={!modifiedKeys[apiKey.id] || modifiedKeys[apiKey.id].includes('***') || validationState[apiKey.id]?.validating}
          className="min-w-[120px]"
        >
          {validationState[apiKey.id]?.validating ? (
            <>
              <CircleNotch size={16} className="animate-spin mr-1" />
              Saving...
            </>
          ) : (
            'Validate & Save'
          )}
        </Button>
      </div>
      <div className="space-y-1">
        <p className="text-xs text-muted-foreground">{apiKey.description}</p>
        {validationState[apiKey.id]?.message && (
          <div className={`flex items-center gap-1 text-xs ${
            validationState[apiKey.id]?.valid ? 'text-green-600' : 'text-red-600'
          }`}>
            {validationState[apiKey.id]?.valid ? (
              <CheckCircle size={12} />
            ) : (
              <XCircle size={12} />
            )}
            <span>{validationState[apiKey.id]?.message}</span>
          </div>
        )}
        {apiKey.is_set && !modifiedKeys[apiKey.id] && (
          <div className="flex items-center gap-1 text-xs text-green-600">
            <CheckCircle size={12} />
            <span>Configured</span>
          </div>
        )}
      </div>
    </div>
  );

  /**
   * Render API keys grouped by category
   * Educational Note: This provides better organization and UX by grouping
   * related settings together
   */
  const renderCategorySection = (title: string, category: 'ai' | 'storage' | 'utility') => {
    const categoryKeys = apiKeys.filter(k => k.category === category);
    if (categoryKeys.length === 0) return null;

    return (
      <div>
        <h3 className="text-sm font-semibold mb-3">{title}</h3>
        <div className="space-y-3">
          {categoryKeys.map(renderApiKeyField)}
        </div>
      </div>
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col bg-card">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle>Admin Settings</DialogTitle>
          <DialogDescription>
            Configure API keys and application settings. Keys are automatically saved after successful validation.
          </DialogDescription>
        </DialogHeader>

        {/* Scrollable content */}
        <div className="flex-1 min-h-0 overflow-y-auto max-h-[60vh] pr-2">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <CircleNotch size={32} className="animate-spin" />
            </div>
          ) : (
            <div className="space-y-6 pr-2 pb-12">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Warning size={16} />
                  <p>API keys are securely stored in your backend .env file</p>
                </div>

                {/* User Roles Section */}
                <div>
                  <h3 className="text-sm font-semibold mb-3">User Roles</h3>
                  {usersLoading ? (
                    <div className="flex items-center justify-center py-6">
                      <CircleNotch size={20} className="animate-spin" />
                    </div>
                  ) : users.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No users found yet. Create accounts to manage roles.
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Email</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead className="text-right">Updated</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {users.map((user) => (
                          <TableRow key={user.id}>
                            <TableCell className="font-medium">
                              {user.email || user.id}
                            </TableCell>
                            <TableCell>
                              <Select
                                value={user.role as string}
                                onValueChange={(v) => handleRoleChange(user.id, v as 'admin' | 'user')}
                                disabled={roleSaving[user.id]}
                              >
                                <SelectTrigger className="w-[140px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="admin">Admin</SelectItem>
                                  <SelectItem value="user">User</SelectItem>
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell className="text-right text-xs text-muted-foreground">
                              {new Date(user.updated_at).toLocaleDateString()}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>

                <Separator />

                {/* AI Models Section */}
                {renderCategorySection('AI Models', 'ai')}

                <Separator />

                {/* Storage Section */}
                {renderCategorySection('Storage & Database', 'storage')}

                <Separator />

                {/* Database Connections Section */}
                <div>
                  <h3 className="text-sm font-semibold mb-3">Database Connections</h3>
                  <div className="space-y-4">
                    {dbLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <CircleNotch size={20} className="animate-spin" />
                      </div>
                    ) : (
                      <>
                        {dbConnections.length === 0 ? (
                          <p className="text-xs text-muted-foreground">
                            No database connections yet. Add one below to attach it as a DATABASE source in a project.
                          </p>
                        ) : (
                          <div className="space-y-2">
                            {dbConnections.map((db) => (
                              <div
                                key={db.id}
                                className="flex items-start justify-between gap-4 rounded-lg border p-3 bg-muted/20"
                              >
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2">
                                    <p className="text-sm font-medium truncate">{db.name}</p>
                                    <span className="text-[11px] text-muted-foreground">
                                      {db.db_type}
                                    </span>
                                  </div>
                                  {db.description ? (
                                    <p className="text-xs text-muted-foreground">{db.description}</p>
                                  ) : null}
                                  <p className="text-xs text-muted-foreground font-mono break-all">
                                    {db.connection_uri_masked}
                                  </p>
                                </div>
                                <Button
                                  variant="soft"
                                  size="sm"
                                  onClick={() => handleDeleteDatabase(db.id)}
                                >
                                  <Trash size={16} className="mr-1" />
                                  Delete
                                </Button>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="rounded-lg border p-4 space-y-3">
                          <p className="text-sm font-medium">Add connection</p>

                          <div className="grid gap-2">
                            <Label>Name</Label>
                            <Input
                              value={dbForm.name}
                              onChange={(e) => {
                                setDbForm((s) => ({ ...s, name: e.target.value }));
                              }}
                              placeholder="Analytics DB"
                            />
                          </div>

                          <div className="grid gap-2">
                            <Label>Type</Label>
                            <Select
                              value={dbForm.db_type}
                              onValueChange={(v) => {
                                setDbForm((s) => ({ ...s, db_type: v as DatabaseType }));
                                setDbValidation({});
                              }}
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select database type" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="postgresql">PostgreSQL</SelectItem>
                                <SelectItem value="mysql">MySQL</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="grid gap-2">
                            <div className="flex items-center justify-between">
                              <Label>Connection URI</Label>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowDbUri((s) => !s)}
                                type="button"
                              >
                                {showDbUri ? <EyeSlash size={16} /> : <Eye size={16} />}
                              </Button>
                            </div>
                            <Input
                              type={showDbUri ? 'text' : 'password'}
                              value={dbForm.connection_uri}
                              onChange={(e) => {
                                setDbForm((s) => ({ ...s, connection_uri: e.target.value }));
                                setDbValidation({});
                              }}
                              placeholder="postgresql://user:pass@host:5432/db"
                            />
                            {dbValidation.message ? (
                              <p className={`text-xs ${dbValidation.valid ? 'text-green-600' : 'text-red-600'}`}>
                                {dbValidation.message}
                              </p>
                            ) : null}
                            <p className="text-xs text-muted-foreground">
                              Credentials are stored server-side. The UI will only display a masked URI after saving.
                            </p>
                          </div>

                          <div className="grid gap-2">
                            <Label>Description (optional)</Label>
                            <Input
                              value={dbForm.description}
                              onChange={(e) => setDbForm((s) => ({ ...s, description: e.target.value }))}
                              placeholder="Read-only reporting database"
                            />
                          </div>

                          <div className="flex gap-2">
                            <Button
                              variant="soft"
                              onClick={handleValidateDatabase}
                              disabled={dbValidating || !dbForm.connection_uri.trim()}
                            >
                              {dbValidating ? (
                                <>
                                  <CircleNotch size={16} className="mr-2 animate-spin" />
                                  Testing...
                                </>
                              ) : (
                                'Test connection'
                              )}
                            </Button>
                            <Button
                              onClick={handleCreateDatabase}
                              disabled={
                                dbCreating ||
                                !dbForm.name.trim() ||
                                !dbForm.connection_uri.trim()
                              }
                            >
                              {dbCreating ? (
                                <>
                                  <CircleNotch size={16} className="mr-2 animate-spin" />
                                  Saving...
                                </>
                              ) : (
                                'Save'
                              )}
                            </Button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Utility Services Section */}
                {renderCategorySection('Utility Services', 'utility')}

                <Separator />

                {/* Processing Settings Section */}
                <div>
                  <h3 className="text-sm font-semibold mb-3">Processing Settings</h3>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>
                          Anthropic Usage Tier
                        </Label>
                        {tierSaving && (
                          <CircleNotch size={16} className="animate-spin text-muted-foreground" />
                        )}
                      </div>
                      <Select
                        value={selectedTier.toString()}
                        onValueChange={handleTierChange}
                        disabled={tierSaving}
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select tier" />
                        </SelectTrigger>
                        <SelectContent>
                          {availableTiers.map((tier) => (
                            <SelectItem key={tier.tier} value={tier.tier.toString()}>
                              {tier.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {availableTiers.find(t => t.tier === selectedTier)?.description ||
                          'Controls parallel processing speed for PDF extraction'}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Workers: {availableTiers.find(t => t.tier === selectedTier)?.max_workers || 4} |
                        Rate: {availableTiers.find(t => t.tier === selectedTier)?.pages_per_minute || 10} pages/min
                      </p>
                    </div>
                  </div>
                </div>

                <Separator />

                {/* Google Drive Integration Section */}
                <div>
                  <h3 className="text-sm font-semibold mb-3">Google Drive Integration</h3>
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 p-4 rounded-lg border bg-muted/30">
                      <GoogleDriveLogo size={32} weight="duotone" className="text-primary" />
                      <div className="flex-1">
                        {googleStatus.connected ? (
                          <>
                            <p className="text-sm font-medium">Connected</p>
                            <p className="text-xs text-muted-foreground">{googleStatus.email}</p>
                          </>
                        ) : googleStatus.configured ? (
                          <>
                            <p className="text-sm font-medium">Not Connected</p>
                            <p className="text-xs text-muted-foreground">Click connect to authorize Google Drive access</p>
                          </>
                        ) : (
                          <>
                            <p className="text-sm font-medium">Not Configured</p>
                            <p className="text-xs text-muted-foreground">Add Google Client ID and Secret above first</p>
                          </>
                        )}
                      </div>
                      {googleStatus.connected ? (
                        <Button
                          variant="soft"
                          size="sm"
                          onClick={handleGoogleDisconnect}
                          disabled={googleLoading}
                        >
                          {googleLoading ? (
                            <CircleNotch size={16} className="animate-spin" />
                          ) : (
                            <>
                              <SignOut size={16} className="mr-1" />
                              Disconnect
                            </>
                          )}
                        </Button>
                      ) : (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={handleGoogleConnect}
                          disabled={googleLoading || !googleStatus.configured}
                        >
                          {googleLoading ? (
                            <CircleNotch size={16} className="animate-spin" />
                          ) : (
                            <>
                              <ArrowSquareOut size={16} className="mr-1" />
                              Connect
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Import files directly from Google Drive. Supports Google Docs, Sheets, Slides, PDFs, images, and audio.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Setup: Create OAuth 2.0 credentials at{' '}
                      <a
                        href="https://console.cloud.google.com/apis/credentials"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Google Cloud Console
                      </a>
                      {' '}and add{' '}
                      <code className="text-xs bg-muted px-1 rounded">http://localhost:5001/api/v1/google/callback</code>
                      {' '}as a redirect URI.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-shrink-0 border-t pt-4">
          {Object.keys(modifiedKeys).length > 0 ? (
            <>
              <Button variant="soft" onClick={() => onOpenChange(false)} disabled={saving}>
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={saving || loading}
                variant="default"
              >
                {saving ? (
                  <>
                    <CircleNotch size={16} className="mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    Save {Object.keys(modifiedKeys).length} Unsaved Key{Object.keys(modifiedKeys).length > 1 ? 's' : ''}
                  </>
                )}
              </Button>
            </>
          ) : (
            <Button variant="soft" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
