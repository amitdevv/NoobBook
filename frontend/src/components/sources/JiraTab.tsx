/**
 * JiraTab Component
 * Educational Note: Adds a Jira source to the project for live issue queries in chat.
 * Similar to FreshdeskTab — Jira credentials are configured globally in API Keys settings.
 */

import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { CircleNotch, Plus } from '@phosphor-icons/react';

interface JiraTabProps {
  isAtLimit: boolean;
  onAddJira: (name?: string, description?: string) => Promise<void>;
}

export const JiraTab: React.FC<JiraTabProps> = ({ isAtLimit, onAddJira }) => {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const handleAdd = async () => {
    setAdding(true);
    try {
      await onAddJira(
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
        Connect your Jira projects for live issue queries in chat.
      </p>
      <p className="text-xs text-muted-foreground">
        Requires Jira API Key configured in Admin Settings &rarr; API Keys.
      </p>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Display name (optional)</label>
        <Input
          placeholder="Jira Issues"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isAtLimit || adding}
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium block">Description (optional)</label>
        <Input
          placeholder="Issues from Jira"
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
            Add Jira Source
          </>
        )}
      </Button>
    </div>
  );
};
