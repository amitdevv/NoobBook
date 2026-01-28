/**
 * BrandSidebar Component
 * Educational Note: Left navigation for brand page sections.
 */
import React from 'react';
import { cn } from '../../lib/utils';
import {
  Image,
  Palette,
  TextT,
  FileText,
  ToggleLeft,
  SquaresFour,
} from '@phosphor-icons/react';

export type BrandSection =
  | 'logos'
  | 'colors'
  | 'typography'
  | 'icons'
  | 'guidelines'
  | 'features';

interface BrandSidebarProps {
  activeSection: BrandSection;
  onSectionChange: (section: BrandSection) => void;
}

interface SectionItem {
  id: BrandSection;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const sections: SectionItem[] = [
  {
    id: 'logos',
    label: 'Logos',
    icon: <Image size={20} />,
    description: 'Upload and manage brand logos',
  },
  {
    id: 'colors',
    label: 'Colors',
    icon: <Palette size={20} />,
    description: 'Define your color palette',
  },
  {
    id: 'typography',
    label: 'Typography',
    icon: <TextT size={20} />,
    description: 'Configure fonts and text styles',
  },
  {
    id: 'icons',
    label: 'Icons',
    icon: <SquaresFour size={20} />,
    description: 'Upload brand icons',
  },
  {
    id: 'guidelines',
    label: 'Guidelines',
    icon: <FileText size={20} />,
    description: 'Brand voice and best practices',
  },
  {
    id: 'features',
    label: 'Feature Settings',
    icon: <ToggleLeft size={20} />,
    description: 'Control brand per feature',
  },
];

export const BrandSidebar: React.FC<BrandSidebarProps> = ({
  activeSection,
  onSectionChange,
}) => {
  return (
    <div className="w-64 h-full bg-card border-r flex flex-col">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-lg">Brand Kit</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Configure your brand assets
        </p>
      </div>

      <nav className="flex-1 p-2">
        <ul className="space-y-1">
          {sections.map((section) => (
            <li key={section.id}>
              <button
                onClick={() => onSectionChange(section.id)}
                className={cn(
                  'w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                  activeSection === section.id
                    ? 'bg-primary/10 text-primary'
                    : 'hover:bg-muted text-foreground'
                )}
              >
                <span
                  className={cn(
                    'mt-0.5',
                    activeSection === section.id
                      ? 'text-primary'
                      : 'text-muted-foreground'
                  )}
                >
                  {section.icon}
                </span>
                <div className="min-w-0">
                  <div className="font-medium text-sm">{section.label}</div>
                  <div className="text-xs text-muted-foreground truncate">
                    {section.description}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
};
