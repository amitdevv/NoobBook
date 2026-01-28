/**
 * TypographySection Component
 * Educational Note: Manages brand typography configuration (fonts, sizes).
 */
import React, { useState, useEffect } from 'react';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { CircleNotch, Check } from '@phosphor-icons/react';
import { brandAPI, type Typography, getDefaultTypography } from '../../../lib/api/brand';

interface TypographySectionProps {
  projectId: string;
}

export const TypographySection: React.FC<TypographySectionProps> = ({ projectId }) => {
  const [typography, setTypography] = useState<Typography>(getDefaultTypography());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const loadTypography = async () => {
    try {
      setLoading(true);
      const response = await brandAPI.getConfig(projectId);
      if (response.data.success) {
        setTypography(response.data.config.typography);
      }
    } catch (error) {
      console.error('Failed to load typography:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTypography();
  }, [projectId]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await brandAPI.updateTypography(projectId, typography);
      if (response.data.success) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to save typography:', error);
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof Omit<Typography, 'heading_sizes'>, value: string) => {
    setTypography((prev) => ({ ...prev, [field]: value }));
  };

  const updateHeadingSize = (level: 'h1' | 'h2' | 'h3', value: string) => {
    setTypography((prev) => ({
      ...prev,
      heading_sizes: { ...prev.heading_sizes, [level]: value },
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
          <h2 className="text-xl font-semibold">Typography</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Configure fonts and text sizing for your brand.
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
            'Save Typography'
          )}
        </Button>
      </div>

      {/* Font Families */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Font Families</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="headingFont">Heading Font</Label>
            <Input
              id="headingFont"
              value={typography.heading_font}
              onChange={(e) => updateField('heading_font', e.target.value)}
              placeholder="Inter, sans-serif"
            />
            <p className="text-xs text-muted-foreground">
              Used for H1, H2, H3, and other headings
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bodyFont">Body Font</Label>
            <Input
              id="bodyFont"
              value={typography.body_font}
              onChange={(e) => updateField('body_font', e.target.value)}
              placeholder="Inter, sans-serif"
            />
            <p className="text-xs text-muted-foreground">
              Used for paragraphs and body text
            </p>
          </div>
        </div>
      </div>

      {/* Heading Sizes */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Heading Sizes</h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="space-y-2">
            <Label htmlFor="h1Size">H1 Size</Label>
            <Input
              id="h1Size"
              value={typography.heading_sizes.h1}
              onChange={(e) => updateHeadingSize('h1', e.target.value)}
              placeholder="2.5rem"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="h2Size">H2 Size</Label>
            <Input
              id="h2Size"
              value={typography.heading_sizes.h2}
              onChange={(e) => updateHeadingSize('h2', e.target.value)}
              placeholder="2rem"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="h3Size">H3 Size</Label>
            <Input
              id="h3Size"
              value={typography.heading_sizes.h3}
              onChange={(e) => updateHeadingSize('h3', e.target.value)}
              placeholder="1.5rem"
            />
          </div>
        </div>
      </div>

      {/* Body Text Settings */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Body Text</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label htmlFor="bodySize">Body Size</Label>
            <Input
              id="bodySize"
              value={typography.body_size}
              onChange={(e) => updateField('body_size', e.target.value)}
              placeholder="1rem"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="lineHeight">Line Height</Label>
            <Input
              id="lineHeight"
              value={typography.line_height}
              onChange={(e) => updateField('line_height', e.target.value)}
              placeholder="1.6"
            />
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="bg-card border rounded-lg p-6 space-y-6">
        <h3 className="font-medium">Preview</h3>

        <div
          className="space-y-4 p-4 bg-muted/30 rounded-lg"
          style={{ fontFamily: typography.body_font }}
        >
          <h1
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h1,
              fontWeight: 'bold',
              lineHeight: '1.2',
            }}
          >
            Heading 1
          </h1>
          <h2
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h2,
              fontWeight: 'bold',
              lineHeight: '1.3',
            }}
          >
            Heading 2
          </h2>
          <h3
            style={{
              fontFamily: typography.heading_font,
              fontSize: typography.heading_sizes.h3,
              fontWeight: 'bold',
              lineHeight: '1.4',
            }}
          >
            Heading 3
          </h3>
          <p
            style={{
              fontSize: typography.body_size,
              lineHeight: typography.line_height,
            }}
          >
            This is body text. Lorem ipsum dolor sit amet, consectetur adipiscing
            elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
          </p>
        </div>
      </div>
    </div>
  );
};
