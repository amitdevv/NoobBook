/**
 * StudioToolItem Component
 * Educational Note: Renders a single studio tool button with active/inactive state.
 * Active items (with signals) are highlighted and clickable.
 * Inactive items are dimmed but still visible for context.
 */

import React from 'react';
import { Button } from '../ui/button';
import { cn } from '@/lib/utils';
import { usePermissions } from '@/contexts/PermissionsContext';
import type { GenerationOption, StudioSignal, StudioItemId } from './types';

interface StudioToolItemProps {
  option: GenerationOption;
  signals: StudioSignal[];
  onClick: (optionId: StudioItemId, signals: StudioSignal[]) => void;
}

/**
 * Maps studio option IDs (singular/shorthand) to permission item keys (plural/full).
 * Only entries where the two names differ are listed — identical keys fall through.
 */
const STUDIO_PERMISSION_MAP: Partial<Record<StudioItemId, string>> = {
  quiz: 'quizzes',
  mind_map: 'mind_maps',
  business_report: 'business_reports',
  marketing_strategy: 'marketing_strategies',
  ads_creative: 'ad_creative',
  prd: 'prds',
  flow_diagram: 'flow_diagrams',
  presentation: 'presentations',
  blog: 'blogs',
  social: 'social_posts',
  website: 'websites',
  email_templates: 'emails',
  video: 'videos',
};

export const StudioToolItem: React.FC<StudioToolItemProps> = ({
  option,
  signals,
  onClick,
}) => {
  const { hasPermission } = usePermissions();
  const permissionKey = STUDIO_PERMISSION_MAP[option.id] ?? option.id;

  // Hide the item entirely when the user lacks permission
  if (!hasPermission('studio', permissionKey)) return null;

  const Icon = option.icon;
  const isActive = signals.length > 0;

  return (
    <Button
      variant="soft"
      className={cn(
        'h-8 px-2 py-1 justify-start text-left relative text-xs',
        isActive
          ? 'hover:bg-accent border-primary/30 bg-primary/5'
          : 'opacity-50 hover:opacity-70 hover:bg-muted cursor-default'
      )}
      onClick={() => {
        console.error('[Studio] Button clicked:', option.id, 'isActive:', isActive, 'signals:', signals.length, 'sources:', JSON.stringify(signals.map(s => s.sources)));
        if (isActive) onClick(option.id, signals);
      }}
      disabled={!isActive}
    >
      <Icon
        size={14}
        className={cn(
          'mr-1.5 flex-shrink-0',
          isActive ? 'text-primary' : 'text-muted-foreground'
        )}
      />
      <span className={cn('truncate', isActive ? 'text-foreground' : 'text-muted-foreground')}>
        {option.title}
      </span>

      {/* Active indicator dot */}
      {isActive && (
        <span className="absolute right-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 bg-primary rounded-full" />
      )}
    </Button>
  );
};
