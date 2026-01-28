/**
 * ColorsSection Component
 * Educational Note: Manages brand color palette configuration.
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { Plus, Trash, CircleNotch, Check } from '@phosphor-icons/react';
import { brandAPI, type ColorPalette, type CustomColor, getDefaultColors } from '../../../lib/api/brand';
import { ColorPicker } from '../ColorPicker';

interface ColorsSectionProps {
  projectId: string;
}

export const ColorsSection: React.FC<ColorsSectionProps> = ({ projectId }) => {
  const [colors, setColors] = useState<ColorPalette>(getDefaultColors());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [newColorName, setNewColorName] = useState('');
  const [newColorValue, setNewColorValue] = useState('#000000');

  const loadColors = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig(projectId);
      if (response.data.success) {
        setColors(response.data.config.colors);
      }
    } catch (error) {
      console.error('Failed to load colors:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadColors();
  }, [projectId]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateColors(projectId, colors);
      if (response.data.success) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to save colors:', error);
    } finally {
      setSaving(false);
    }
  };

  const updateColor = (key: keyof Omit<ColorPalette, 'custom'>, value: string) => {
    setColors((prev) => ({ ...prev, [key]: value }));
  };

  const addCustomColor = () => {
    if (!newColorName.trim()) return;

    setColors((prev) => ({
      ...prev,
      custom: [...prev.custom, { name: newColorName.trim(), value: newColorValue }],
    }));
    setNewColorName('');
    setNewColorValue('#000000');
  };

  const removeCustomColor = (index: number) => {
    setColors((prev) => ({
      ...prev,
      custom: prev.custom.filter((_, i) => i !== index),
    }));
  };

  const updateCustomColor = (index: number, field: keyof CustomColor, value: string) => {
    setColors((prev) => ({
      ...prev,
      custom: prev.custom.map((c, i) =>
        i === index ? { ...c, [field]: value } : c
      ),
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
          <h2 className="text-xl font-semibold">Colors</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Define your brand color palette for consistent styling across generated content.
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
            'Save Colors'
          )}
        </Button>
      </div>

      {/* Primary Colors */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Primary Colors</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ColorPicker
            label="Primary"
            value={colors.primary}
            onChange={(v) => updateColor('primary', v)}
            description="Main brand color for buttons and CTAs"
          />
          <ColorPicker
            label="Secondary"
            value={colors.secondary}
            onChange={(v) => updateColor('secondary', v)}
            description="Supporting color for secondary elements"
          />
          <ColorPicker
            label="Accent"
            value={colors.accent}
            onChange={(v) => updateColor('accent', v)}
            description="Highlight color for emphasis"
          />
          <ColorPicker
            label="Background"
            value={colors.background}
            onChange={(v) => updateColor('background', v)}
            description="Page background color"
          />
          <ColorPicker
            label="Text"
            value={colors.text}
            onChange={(v) => updateColor('text', v)}
            description="Primary text color"
          />
        </div>
      </div>

      {/* Custom Colors */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Custom Colors</h3>

        {colors.custom.length > 0 && (
          <div className="space-y-4">
            {colors.custom.map((color, index) => (
              <div key={index} className="flex items-end gap-3">
                <div className="flex-1 space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={color.name}
                    onChange={(e) => updateCustomColor(index, 'name', e.target.value)}
                    placeholder="Color name"
                  />
                </div>
                <div className="flex-1">
                  <ColorPicker
                    label="Color"
                    value={color.value}
                    onChange={(v) => updateCustomColor(index, 'value', v)}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10 text-destructive hover:text-destructive"
                  onClick={() => removeCustomColor(index)}
                >
                  <Trash size={16} />
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Add Custom Color */}
        <div className="flex items-end gap-3 pt-4 border-t">
          <div className="flex-1 space-y-2">
            <Label>New Color Name</Label>
            <Input
              value={newColorName}
              onChange={(e) => setNewColorName(e.target.value)}
              placeholder="e.g., Brand Red"
            />
          </div>
          <div className="flex-1">
            <ColorPicker
              label="Color Value"
              value={newColorValue}
              onChange={setNewColorValue}
            />
          </div>
          <Button
            variant="soft"
            onClick={addCustomColor}
            disabled={!newColorName.trim()}
            className="gap-2"
          >
            <Plus size={16} />
            Add
          </Button>
        </div>
      </div>

      {/* Preview */}
      <div className="bg-card border rounded-lg p-6 space-y-4">
        <h3 className="font-medium">Preview</h3>
        <div className="flex flex-wrap gap-4">
          <div className="text-center">
            <div
              className="w-16 h-16 rounded-lg border"
              style={{ backgroundColor: colors.primary }}
            />
            <p className="text-xs text-muted-foreground mt-1">Primary</p>
          </div>
          <div className="text-center">
            <div
              className="w-16 h-16 rounded-lg border"
              style={{ backgroundColor: colors.secondary }}
            />
            <p className="text-xs text-muted-foreground mt-1">Secondary</p>
          </div>
          <div className="text-center">
            <div
              className="w-16 h-16 rounded-lg border"
              style={{ backgroundColor: colors.accent }}
            />
            <p className="text-xs text-muted-foreground mt-1">Accent</p>
          </div>
          <div className="text-center">
            <div
              className="w-16 h-16 rounded-lg border"
              style={{ backgroundColor: colors.background }}
            />
            <p className="text-xs text-muted-foreground mt-1">Background</p>
          </div>
          <div className="text-center">
            <div
              className="w-16 h-16 rounded-lg border"
              style={{ backgroundColor: colors.text }}
            />
            <p className="text-xs text-muted-foreground mt-1">Text</p>
          </div>
          {colors.custom.map((color, index) => (
            <div key={index} className="text-center">
              <div
                className="w-16 h-16 rounded-lg border"
                style={{ backgroundColor: color.value }}
              />
              <p className="text-xs text-muted-foreground mt-1 truncate max-w-16">
                {color.name}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
