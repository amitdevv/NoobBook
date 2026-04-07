/**
 * ModelsSection Component
 *
 * Admin-only model selector. Lets the admin override which Claude model
 * each use-case category uses (chat, studio, query agents, source extraction).
 *
 * Selecting "Per-prompt defaults" for a category clears the override and
 * each prompt's JSON-baked model is used. The UI shows the per-prompt
 * breakdown explicitly so "Default" isn't ambiguous — admins can see that
 * Chat actually means Sonnet for the main prompt and Haiku for chat_naming
 * and memory, etc.
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
import { modelSettingsAPI } from '@/lib/api/settings';
import type {
  ModelInfo,
  ModelCategory,
  ModelSettings,
  ModelDefaults,
} from '@/lib/api/settings';
import { useToast } from '@/components/ui/use-toast';
import { createLogger } from '@/lib/logger';

const log = createLogger('models-section');

// Sentinel value used by shadcn's Select to represent "no override".
// shadcn's SelectItem doesn't allow an empty string value.
const DEFAULT_MODEL_VALUE = '__default__';

// Friendly labels for prompt names so the breakdown reads naturally.
// Anything not in this map falls back to the prompt name itself.
const PROMPT_LABELS: Record<string, string> = {
  default: 'main chat',
  chat_naming: 'chat naming',
  memory: 'memory updates',
  audio_script: 'audio overview',
  video: 'video',
  mind_map: 'mind map',
  quiz: 'quiz',
  flash_cards: 'flash cards',
  social_posts: 'social posts',
  infographic: 'infographic',
  flow_diagram: 'flow diagram',
  ad_creative: 'ad creative',
  component_agent: 'component generation',
  wireframe_agent: 'wireframe agent',
  wireframe: 'wireframe',
  website_agent: 'website generation',
  presentation_agent: 'presentation generation',
  email_agent: 'email generation',
  blog_agent: 'blog',
  prd_agent: 'PRD',
  business_report_agent: 'business report',
  marketing_strategy_agent: 'marketing strategy',
  database_analyzer_agent: 'database analyzer',
  csv_analyzer_agent: 'CSV analyzer',
  freshdesk_analyzer_agent: 'Freshdesk analyzer',
  pdf_extraction: 'PDF extraction',
  pptx_extraction: 'PPTX extraction',
  image_extraction: 'image extraction',
  csv_processor: 'CSV processing',
  summary: 'source summary',
};

const labelForPrompt = (name: string) => PROMPT_LABELS[name] ?? name;

export const ModelsSection: React.FC = () => {
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [categories, setCategories] = useState<ModelCategory[]>([]);
  const [selections, setSelections] = useState<ModelSettings>({});
  const [defaults, setDefaults] = useState<ModelDefaults>({});
  const [loading, setLoading] = useState(false);
  const [savingCategory, setSavingCategory] = useState<string | null>(null);

  const { success, error } = useToast();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await modelSettingsAPI.getSettings();
      setAvailableModels(response.available_models);
      setCategories(response.categories);
      setSelections(response.settings);
      setDefaults(response.defaults ?? {});
    } catch (err) {
      log.error({ err }, 'failed to load model settings');
      error('Failed to load model settings');
    } finally {
      setLoading(false);
    }
  };

  const handleModelChange = async (categoryId: string, value: string) => {
    const modelId = value === DEFAULT_MODEL_VALUE ? null : value;
    const previous = selections[categoryId] ?? null;

    // Optimistic update; roll back on failure
    setSelections((prev) => ({ ...prev, [categoryId]: modelId }));
    setSavingCategory(categoryId);

    try {
      await modelSettingsAPI.updateSettings({ [categoryId]: modelId });
      const categoryLabel =
        categories.find((c) => c.id === categoryId)?.label ?? categoryId;
      success(`${categoryLabel} model updated`);
    } catch (err) {
      log.error({ err, categoryId }, 'failed to update model');
      setSelections((prev) => ({ ...prev, [categoryId]: previous }));
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

  // Build a quick lookup so we can show "Sonnet 4.6" instead of the raw id
  const modelNameById = new Map(availableModels.map((m) => [m.id, m.name]));
  const friendlyModelName = (id: string) => modelNameById.get(id) ?? id;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-medium text-stone-900 mb-1">Models</h2>
        <p className="text-sm text-muted-foreground">
          Choose which Claude model each use case runs on. Overrides apply
          immediately and persist across restarts.
        </p>
      </div>

      <div className="space-y-6">
        {categories.map((category) => {
          const selected = selections[category.id] ?? null;
          const selectValue = selected ?? DEFAULT_MODEL_VALUE;
          const breakdown = defaults[category.id] ?? {};
          const breakdownEntries = Object.entries(breakdown);
          // Sort so the model that covers the most prompts shows first
          breakdownEntries.sort((a, b) => b[1].length - a[1].length);

          return (
            <div
              key={category.id}
              className="space-y-2 border border-stone-200 rounded-md p-4"
            >
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm font-medium">{category.label}</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {category.description}
                  </p>
                </div>
                {savingCategory === category.id && (
                  <CircleNotch
                    size={16}
                    className="animate-spin text-muted-foreground"
                  />
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
                    Per-prompt defaults
                  </SelectItem>
                  {availableModels.map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* What "Per-prompt defaults" actually resolves to */}
              {breakdownEntries.length > 0 && (
                <div className="text-xs text-muted-foreground bg-stone-50 border border-stone-200 rounded px-3 py-2 mt-2">
                  <div className="font-medium text-stone-600 mb-1">
                    Per-prompt defaults:
                  </div>
                  <ul className="space-y-0.5">
                    {breakdownEntries.map(([modelId, prompts]) => (
                      <li key={modelId}>
                        <span className="font-medium text-stone-700">
                          {friendlyModelName(modelId)}
                        </span>
                        {' — '}
                        {prompts.map(labelForPrompt).join(', ')}
                      </li>
                    ))}
                  </ul>
                  {selected === null && (
                    <p className="mt-1 italic">
                      Selecting a single model above forces every prompt in
                      this category to use it.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
