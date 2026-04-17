/**
 * MixpanelTab Component
 * Educational Note: Adds a Mixpanel source to the project for live analytics
 * queries in chat. Similar to JiraTab — credentials are configured globally
 * in API Keys settings; this just flags the project.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { CircleNotch, Plus } from '@phosphor-icons/react';

interface MixpanelTabProps {
  isAtLimit: boolean;
  onAddMixpanel: (name?: string, description?: string) => Promise<void>;
}

export const MixpanelTab: React.FC<MixpanelTabProps> = ({ isAtLimit, onAddMixpanel }) => {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleAdd = async () => {
    setAdding(true);
    try {
      await onAddMixpanel(
        name.trim() || undefined,
        description.trim() || undefined
      );
      setName('');
      setDescription('');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm">
        Connect Mixpanel for live event, funnel, and retention queries in chat.
      </p>
      <p className="text-xs text-muted-foreground">
        Requires a Mixpanel Service Account configured in Admin Settings &rarr; API Keys.
      </p>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Display name (optional)</label>
        <Input
          placeholder="Mixpanel Analytics"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Description (optional)</label>
        <Input
          placeholder="Product analytics from Mixpanel"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      <Button
        onClick={handleAdd}
        disabled={isAtLimit || adding}
      >
        {adding ? (
          <>
            <CircleNotch size={16} className="mr-2 animate-spin" />
            Adding...
          </>
        ) : (
          <>
            <Plus size={16} className="mr-2" />
            Add Mixpanel Source
          </>
        )}
      </Button>
    </div>
  );
};
