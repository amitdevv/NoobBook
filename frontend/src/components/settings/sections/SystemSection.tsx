/**
 * SystemSection Component
 * Manages processing settings (Anthropic tier) and per-category model overrides.
 */

import React, { useState, useEffect } from 'react';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CircleNotch } from '@phosphor-icons/react';
import { processingSettingsAPI, modelSettingsAPI } from '@/lib/api/settings';
import type {
  AvailableTier,
  ModelInfo,
  ModelCategory,
  ModelSettings,
} from '@/lib/api/settings';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('system-section');

// Sentinel value used by the Select component to represent "no override".
// We can't use an empty string because shadcn's SelectItem forbids it.
const DEFAULT_MODEL_VALUE = '__default__';

export const SystemSection: React.FC = () => {
  // Processing tier state
  const [availableTiers, setAvailableTiers] = useState<AvailableTier[]>([]);
  const [selectedTier, setSelectedTier] = useState<number>(1);
  const [tierSaving, setTierSaving] = useState(false);

  // Model settings state
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [modelCategories, setModelCategories] = useState<ModelCategory[]>([]);
  const [modelSelections, setModelSelections] = useState<ModelSettings>({});
  const [savingCategory, setSavingCategory] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  const { success, error } = useToast();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      // Fetch tier and model settings in parallel — both live in the System panel
      const [processing, models] = await Promise.all([
        processingSettingsAPI.getSettings(),
        modelSettingsAPI.getSettings(),
      ]);

      setAvailableTiers(processing.available_tiers);
      setSelectedTier(processing.settings.anthropic_tier);

      setAvailableModels(models.available_models);
      setModelCategories(models.categories);
      setModelSelections(models.settings);
    } catch (err) {
      log.error({ err }, 'failed to load system settings');
      error('Failed to load system settings');
    } finally {
      setLoading(false);
    }
  };

  const handleTierChange = async (tierValue: string) => {
    const tier = parseInt(tierValue, 10);
    setTierSaving(true);
    try {
      await processingSettingsAPI.updateSettings({ anthropic_tier: tier });
      setSelectedTier(tier);
      success('Processing tier updated');
    } catch (err) {
      log.error({ err }, 'failed to update tier');
      error('Failed to update processing tier');
    } finally {
      setTierSaving(false);
    }
  };

  const handleModelChange = async (categoryId: string, value: string) => {
    // DEFAULT_MODEL_VALUE means "clear override" — backend expects null
    const modelId = value === DEFAULT_MODEL_VALUE ? null : value;

    // Optimistic UI: update the dropdown immediately, roll back on failure
    const previous = modelSelections[categoryId] ?? null;
    setModelSelections((prev) => ({ ...prev, [categoryId]: modelId }));
    setSavingCategory(categoryId);

    try {
      await modelSettingsAPI.updateSettings({ [categoryId]: modelId });
      const categoryLabel =
        modelCategories.find((c) => c.id === categoryId)?.label ?? categoryId;
      success(`${categoryLabel} model updated`);
    } catch (err) {
      log.error({ err, categoryId }, 'failed to update model');
      setModelSelections((prev) => ({ ...prev, [categoryId]: previous }));
      error('Failed to update model');
    } finally {
      setSavingCategory(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <CircleNotch size={32} className="animate-spin" />
      </div>
    );
  }

  const currentTier = availableTiers.find((t) => t.tier === selectedTier);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">System</h2>
        <p className="text-sm text-muted-foreground">
          Configure processing and model settings
        </p>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">Processing Settings</h3>
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Anthropic Usage Tier</Label>
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
              {currentTier?.description || 'Controls parallel processing speed for PDF extraction'}
            </p>
            <p className="text-xs text-muted-foreground">
              Workers: {currentTier?.max_workers || 4} |
              Rate: {currentTier?.pages_per_minute || 10} pages/min
            </p>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1">Model Configuration</h3>
        <p className="text-xs text-muted-foreground mb-4">
          Choose a Claude model per use case. "Default" keeps each prompt's preconfigured model.
        </p>
        <div className="space-y-5">
          {modelCategories.map((category) => {
            const selected = modelSelections[category.id] ?? null;
            const selectValue = selected ?? DEFAULT_MODEL_VALUE;
            return (
              <div key={category.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>{category.label}</Label>
                  {savingCategory === category.id && (
                    <CircleNotch size={16} className="animate-spin text-muted-foreground" />
                  )}
                </div>
                <Select
                  value={selectValue}
                  onValueChange={(val) => handleModelChange(category.id, val)}
                  disabled={savingCategory !== null}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={DEFAULT_MODEL_VALUE}>
                      Default (use prompt config)
                    </SelectItem>
                    {availableModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">{category.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
