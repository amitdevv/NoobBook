/**
 * GuidelinesSection Component
 * Educational Note: Manages brand guidelines, voice, and best practices.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Textarea } from '../../ui/textarea';
import { Badge } from '../../ui/badge';
import { Plus, X, CircleNotch, Check } from '@phosphor-icons/react';
import { brandAPI, type BrandVoice, type BestPractices } from '../../../lib/api/brand';

interface GuidelinesSectionProps {
  projectId: string;
}

export const GuidelinesSection: React.FC<GuidelinesSectionProps> = ({ projectId }) => {
  const [guidelines, setGuidelines] = useState('');
  const [voice, setVoice] = useState<BrandVoice>({
    tone: 'professional',
    personality: [],
    keywords: [],
  });
  const [bestPractices, setBestPractices] = useState<BestPractices>({
    dos: [],
    donts: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Input states for adding items
  const [newPersonality, setNewPersonality] = useState('');
  const [newKeyword, setNewKeyword] = useState('');
  const [newDo, setNewDo] = useState('');
  const [newDont, setNewDont] = useState('');

  const loadConfig = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig(projectId);
      if (response.data.success) {
        const config = response.data.config;
        setGuidelines(config.guidelines || '');
        setVoice(config.voice);
        setBestPractices(config.best_practices);
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig();
  }, [projectId]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateConfig(projectId, {
        guidelines,
        voice,
        best_practices: bestPractices,
      });
      if (response.data.success) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to save:', error);
    } finally {
      setSaving(false);
    }
  };

  const addPersonality = () => {
    if (!newPersonality.trim()) return;
    setVoice((prev) => ({
      ...prev,
      personality: [...prev.personality, newPersonality.trim()],
    }));
    setNewPersonality('');
  };

  const removePersonality = (index: number) => {
    setVoice((prev) => ({
      ...prev,
      personality: prev.personality.filter((_, i) => i !== index),
    }));
  };

  const addKeyword = () => {
    if (!newKeyword.trim()) return;
    setVoice((prev) => ({
      ...prev,
      keywords: [...prev.keywords, newKeyword.trim()],
    }));
    setNewKeyword('');
  };

  const removeKeyword = (index: number) => {
    setVoice((prev) => ({
      ...prev,
      keywords: prev.keywords.filter((_, i) => i !== index),
    }));
  };

  const addDo = () => {
    if (!newDo.trim()) return;
    setBestPractices((prev) => ({
      ...prev,
      dos: [...prev.dos, newDo.trim()],
    }));
    setNewDo('');
  };

  const removeDo = (index: number) => {
    setBestPractices((prev) => ({
      ...prev,
      dos: prev.dos.filter((_, i) => i !== index),
    }));
  };

  const addDont = () => {
    if (!newDont.trim()) return;
    setBestPractices((prev) => ({
      ...prev,
      donts: [...prev.donts, newDont.trim()],
    }));
    setNewDont('');
  };

  const removeDont = (index: number) => {
    setBestPractices((prev) => ({
      ...prev,
      donts: prev.donts.filter((_, i) => i !== index),
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <CircleNotch size={24} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Guidelines & Voice</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Define your brand voice, tone, and best practices.
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving} className="gap-2">
          {saving ? (
            <>
              <CircleNotch size={16} className="animate-spin" />
              Saving...
            </>
          ) : saved ? (
            <>
              <Check size={16} />
              Saved
            </>
          ) : (
            'Save Guidelines'
          )}
        </Button>
      </div>

      {/* Brand Voice */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Brand Voice</h3>

        {/* Tone */}
        <div className="space-y-2">
          <Label htmlFor="tone">Tone</Label>
          <Input
            id="tone"
            value={voice.tone}
            onChange={(e) => setVoice((prev) => ({ ...prev, tone: e.target.value }))}
            placeholder="e.g., professional, friendly, casual"
          />
          <p className="text-xs text-muted-foreground">
            How your brand should sound in communications
          </p>
        </div>

        {/* Personality Traits */}
        <div className="space-y-2">
          <Label>Personality Traits</Label>
          <div className="flex flex-wrap gap-2 mb-2">
            {voice.personality.map((trait, index) => (
              <Badge key={index} variant="secondary" className="gap-1 pr-1">
                {trait}
                <button
                  onClick={() => removePersonality(index)}
                  className="ml-1 hover:text-destructive"
                >
                  <X size={12} />
                </button>
              </Badge>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={newPersonality}
              onChange={(e) => setNewPersonality(e.target.value)}
              placeholder="Add a trait"
              onKeyDown={(e) => e.key === 'Enter' && addPersonality()}
            />
            <Button variant="soft" onClick={addPersonality} size="icon">
              <Plus size={16} />
            </Button>
          </div>
        </div>

        {/* Keywords */}
        <div className="space-y-2">
          <Label>Key Terms to Use</Label>
          <div className="flex flex-wrap gap-2 mb-2">
            {voice.keywords.map((keyword, index) => (
              <Badge key={index} variant="secondary" className="gap-1 pr-1">
                {keyword}
                <button
                  onClick={() => removeKeyword(index)}
                  className="ml-1 hover:text-destructive"
                >
                  <X size={12} />
                </button>
              </Badge>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="Add a keyword"
              onKeyDown={(e) => e.key === 'Enter' && addKeyword()}
            />
            <Button variant="soft" onClick={addKeyword} size="icon">
              <Plus size={16} />
            </Button>
          </div>
        </div>
      </div>

      {/* Written Guidelines */}
      <div className="bg-card border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Written Guidelines</h3>
        <Textarea
          value={guidelines}
          onChange={(e) => setGuidelines(e.target.value)}
          placeholder="Enter your brand guidelines here. Markdown formatting is supported."
          rows={8}
          className="font-mono text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Detailed brand guidelines that AI will follow when generating content.
          Markdown formatting is supported.
        </p>
      </div>

      {/* Best Practices */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Best Practices</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Do's */}
          <div className="space-y-4">
            <Label className="text-green-600">Do</Label>
            <ul className="space-y-2">
              {bestPractices.dos.map((item, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-sm bg-green-50 p-2 rounded"
                >
                  <span className="flex-1">{item}</span>
                  <button
                    onClick={() => removeDo(index)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <Input
                value={newDo}
                onChange={(e) => setNewDo(e.target.value)}
                placeholder="Add a 'do'"
                onKeyDown={(e) => e.key === 'Enter' && addDo()}
              />
              <Button variant="soft" onClick={addDo} size="icon">
                <Plus size={16} />
              </Button>
            </div>
          </div>

          {/* Don'ts */}
          <div className="space-y-4">
            <Label className="text-red-600">Don't</Label>
            <ul className="space-y-2">
              {bestPractices.donts.map((item, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-sm bg-red-50 p-2 rounded"
                >
                  <span className="flex-1">{item}</span>
                  <button
                    onClick={() => removeDont(index)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <Input
                value={newDont}
                onChange={(e) => setNewDont(e.target.value)}
                placeholder="Add a 'don't'"
                onKeyDown={(e) => e.key === 'Enter' && addDont()}
              />
              <Button variant="soft" onClick={addDont} size="icon">
                <Plus size={16} />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
