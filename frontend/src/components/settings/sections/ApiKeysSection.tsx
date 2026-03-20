/**
 * ApiKeysSection Component
 * Manages API keys for AI Models, Storage, and Utility services.
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
// Separator no longer used — categories now rendered as distinct cards
import {
  Eye,
  EyeSlash,
  Trash,
  Warning,
  CheckCircle,
  XCircle,
  CircleNotch,
  Robot,
  Database,
  Wrench,
  Plugs,
  Binoculars,
  ShieldCheck,
  Key,
} from '@phosphor-icons/react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { settingsAPI } from '@/lib/api/settings';
import type { ApiKey } from '@/lib/api/settings';
import { useToast } from '@/components/ui/toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('api-keys-section');

interface ValidationState {
  [key: string]: {
    validating: boolean;
    valid?: boolean;
    message?: string;
  };
}

// Category metadata for rendering — icon, description, accent color
const CATEGORY_META: Record<string, {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon: React.FC<any>;
  description: string;
  accent: string;
  iconBg: string;
}> = {
  ai: {
    icon: Robot,
    description: 'LLM providers for chat, extraction, and generation',
    accent: 'border-amber-200',
    iconBg: 'bg-amber-50 text-amber-700',
  },
  storage: {
    icon: Database,
    description: 'Vector database and storage services',
    accent: 'border-blue-200',
    iconBg: 'bg-blue-50 text-blue-700',
  },
  utility: {
    icon: Wrench,
    description: 'Search, OAuth, and proxy services',
    accent: 'border-stone-200',
    iconBg: 'bg-stone-100 text-stone-600',
  },
  integrations: {
    icon: Plugs,
    description: 'Connect external platforms to NoobBook',
    accent: 'border-purple-200',
    iconBg: 'bg-purple-50 text-purple-700',
  },
  observability: {
    icon: Binoculars,
    description: 'Monitor and trace LLM calls across the app',
    accent: 'border-teal-200',
    iconBg: 'bg-teal-50 text-teal-700',
  },
};

export const ApiKeysSection: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [modifiedKeys, setModifiedKeys] = useState<{ [key: string]: string }>({});
  const [showApiKeys, setShowApiKeys] = useState<{ [key: string]: boolean }>({});
  const [loading, setLoading] = useState(false);
  const [validationState, setValidationState] = useState<ValidationState>({});
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const { success, error, info } = useToast();

  useEffect(() => {
    loadApiKeys();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadApiKeys = async () => {
    setLoading(true);
    try {
      const keys = await settingsAPI.getApiKeys();
      setApiKeys(keys);
      setModifiedKeys({});
    } catch (err) {
      log.error({ err }, 'failed to load API keys');
      error('Failed to load API keys');
    } finally {
      setLoading(false);
    }
  };

  const updateApiKey = (id: string, value: string) => {
    setModifiedKeys(prev => ({ ...prev, [id]: value }));
    setApiKeys(prev => prev.map(key =>
      key.id === id ? { ...key, value } : key
    ));
  };

  const toggleShowApiKey = (id: string) => {
    setShowApiKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const deleteApiKey = async (id: string) => {
    try {
      await settingsAPI.deleteApiKey(id);
      setModifiedKeys(prev => {
        const newKeys = { ...prev };
        delete newKeys[id];
        return newKeys;
      });
      setApiKeys(prev => prev.map(key =>
        key.id === id ? { ...key, value: '', is_set: false } : key
      ));
      success('API key deleted successfully');
    } catch (err) {
      log.error({ err }, 'failed to delete API key');
      error('Failed to delete API key');
    }
  };

  const validateApiKey = async (id: string) => {
    const value = modifiedKeys[id] || apiKeys.find(k => k.id === id)?.value || '';
    const keyName = apiKeys.find(k => k.id === id)?.name || id;

    if (value.includes('***')) {
      info('Cannot validate a masked API key. Please enter a new key.');
      return;
    }

    setValidationState(prev => ({
      ...prev,
      [id]: { validating: true }
    }));

    try {
      const result = await settingsAPI.validateApiKey(id, value);

      if (result.valid) {
        try {
          await settingsAPI.updateApiKeys([{ id, value }]);
          setModifiedKeys(prev => {
            const newKeys = { ...prev };
            delete newKeys[id];
            return newKeys;
          });
          setValidationState(prev => ({
            ...prev,
            [id]: {
              validating: false,
              valid: true,
              message: result.message
            }
          }));
          success(`${keyName} validated and saved successfully!`);
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

  const configuredCount = apiKeys.filter(k => k.is_set).length;

  const renderApiKeyField = (apiKey: ApiKey) => {
    const isModified = !!modifiedKeys[apiKey.id];
    const isConfigured = apiKey.is_set && !isModified;
    const validation = validationState[apiKey.id];

    return (
      <div
        key={apiKey.id}
        className={`group relative rounded-lg border px-4 py-3.5 transition-all duration-150 ${
          isConfigured
            ? 'border-green-200 bg-green-50/30'
            : isModified
              ? 'border-amber-300 bg-amber-50/20'
              : 'border-stone-200 bg-white'
        }`}
      >
        {/* Header row: name + status + actions */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <Label className="text-[13px] font-semibold text-stone-800">
              {apiKey.name}
            </Label>
            {apiKey.required && (
              <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">
                Required
              </span>
            )}
            {isConfigured && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                <CheckCircle size={11} weight="fill" />
                Active
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={() => toggleShowApiKey(apiKey.id)}
              className="p-1.5 rounded-md text-stone-400 hover:text-stone-600 hover:bg-stone-100 transition-colors"
              title={showApiKeys[apiKey.id] ? 'Hide key' : 'Show key'}
            >
              {showApiKeys[apiKey.id] ? <EyeSlash size={15} /> : <Eye size={15} />}
            </button>
            <button
              type="button"
              onClick={() => setDeleteConfirmId(apiKey.id)}
              disabled={!apiKey.value && !apiKey.is_set}
              className="p-1.5 rounded-md text-stone-400 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="Delete key"
            >
              <Trash size={15} />
            </button>
          </div>
        </div>

        {/* Input row */}
        <div className="flex gap-2">
          <Input
            type={showApiKeys[apiKey.id] ? 'text' : 'password'}
            placeholder={`Enter ${apiKey.name} key...`}
            value={modifiedKeys[apiKey.id] !== undefined ? modifiedKeys[apiKey.id] : apiKey.value}
            onChange={(e) => updateApiKey(apiKey.id, e.target.value)}
            className="font-mono text-[12px] flex-1 h-9 bg-white border-stone-200 focus:border-amber-400"
          />
          <Button
            variant="default"
            size="sm"
            onClick={() => validateApiKey(apiKey.id)}
            disabled={!modifiedKeys[apiKey.id] || modifiedKeys[apiKey.id].includes('***') || validation?.validating}
            className="h-9 px-3.5 text-[12px] font-semibold min-w-[115px]"
          >
            {validation?.validating ? (
              <>
                <CircleNotch size={14} className="animate-spin mr-1.5" />
                Saving...
              </>
            ) : (
              <>
                <ShieldCheck size={14} className="mr-1.5" />
                Validate & Save
              </>
            )}
          </Button>
        </div>

        {/* Description + validation feedback */}
        <div className="mt-2 space-y-1">
          <p className="text-[11px] text-stone-400 leading-relaxed">{apiKey.description}</p>
          {validation?.message && (
            <div className={`flex items-center gap-1.5 text-[11px] font-medium ${
              validation.valid ? 'text-green-600' : 'text-red-500'
            }`}>
              {validation.valid ? <CheckCircle size={12} weight="fill" /> : <XCircle size={12} weight="fill" />}
              <span>{validation.message}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderCategorySection = (title: string, category: 'ai' | 'storage' | 'utility' | 'integrations' | 'observability') => {
    const categoryKeys = apiKeys.filter(k => k.category === category);
    if (categoryKeys.length === 0) return null;

    const meta = CATEGORY_META[category];
    const Icon = meta?.icon || Key;
    const configured = categoryKeys.filter(k => k.is_set).length;

    return (
      <div className={`rounded-xl border ${meta?.accent || 'border-stone-200'} bg-white overflow-hidden`}>
        {/* Category header */}
        <div className="flex items-center gap-3 px-5 py-3.5 border-b border-stone-100 bg-stone-50/50">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${meta?.iconBg || 'bg-stone-100 text-stone-600'}`}>
            <Icon size={17} weight="duotone" />
          </div>
          <div className="flex-1">
            <h3 className="text-[13px] font-semibold text-stone-800">{title}</h3>
            <p className="text-[11px] text-stone-400">{meta?.description}</p>
          </div>
          <span className="text-[11px] font-medium text-stone-400 bg-stone-100 px-2 py-0.5 rounded-full">
            {configured}/{categoryKeys.length}
          </span>
        </div>

        {/* Key fields */}
        <div className="p-3 space-y-2.5">
          {categoryKeys.map(renderApiKeyField)}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <CircleNotch size={28} className="animate-spin text-amber-600" />
          <span className="text-sm text-stone-400">Loading API keys...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
            <Key size={20} weight="duotone" className="text-amber-600" />
            API Keys
          </h2>
          <p className="text-sm text-stone-500 mt-0.5">
            Configure credentials for AI models, storage, and integrations
          </p>
        </div>
        <span className="text-[11px] font-medium text-amber-700 bg-amber-100 px-2.5 py-1 rounded-full">
          {configuredCount}/{apiKeys.length} configured
        </span>
      </div>

      {/* Security notice */}
      <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-lg bg-stone-50 border border-stone-200">
        <ShieldCheck size={16} className="text-stone-400 flex-shrink-0" />
        <p className="text-[12px] text-stone-500">
          Keys are stored server-side in your <code className="text-[11px] font-mono bg-stone-200/60 px-1 py-0.5 rounded">backend/.env</code> file. Masked values are never sent to the browser.
        </p>
      </div>

      {/* Category sections */}
      <div className="space-y-4">
        {renderCategorySection('AI Models', 'ai')}
        {renderCategorySection('Storage & Database', 'storage')}
        {renderCategorySection('Utility Services', 'utility')}
        {renderCategorySection('Integrations', 'integrations')}
        {renderCategorySection('Observability', 'observability')}
      </div>

      {/* Delete confirmation dialog — unchanged */}
      <AlertDialog open={!!deleteConfirmId} onOpenChange={(open) => !open && setDeleteConfirmId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Warning size={20} className="text-destructive" />
              Delete API Key
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{apiKeys.find(k => k.id === deleteConfirmId)?.name}</strong>? You'll need to re-enter it to use this service again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <Button variant="soft" onClick={() => setDeleteConfirmId(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteConfirmId) {
                  deleteApiKey(deleteConfirmId);
                  setDeleteConfirmId(null);
                }
              }}
            >
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
