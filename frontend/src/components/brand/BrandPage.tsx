/**
 * BrandPage Component
 * Educational Note: Full-page brand editor with sidebar navigation.
 * This page is accessible via React Router at /projects/:projectId/brand
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import { ArrowLeft, CircleNotch, Palette } from '@phosphor-icons/react';
import { projectsAPI } from '../../lib/api';
import { BrandSidebar, type BrandSection } from './BrandSidebar';
import {
  LogosSection,
  IconsSection,
  ColorsSection,
  TypographySection,
  GuidelinesSection,
  FeatureSettingsSection,
} from './sections';

interface Project {
  id: string;
  name: string;
  description?: string;
}

export const BrandPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<BrandSection>('logos');

  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) return;

      try {
        setLoading(true);
        const response = await projectsAPI.get(projectId);
        if (response.data.success) {
          setProject(response.data.project);
        }
      } catch (error) {
        console.error('Failed to load project:', error);
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId]);

  const handleBack = () => {
    // Navigate back to project workspace with project ID in URL
    // This ensures the project state is preserved
    navigate(`/projects/${projectId}`);
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <CircleNotch size={32} className="animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!project || !projectId) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-background">
        <p className="text-muted-foreground mb-4">Project not found</p>
        <Button variant="soft" onClick={() => navigate('/')}>
          Go to Dashboard
        </Button>
      </div>
    );
  }

  const renderSection = () => {
    switch (activeSection) {
      case 'logos':
        return <LogosSection projectId={projectId} />;
      case 'icons':
        return <IconsSection projectId={projectId} />;
      case 'colors':
        return <ColorsSection projectId={projectId} />;
      case 'typography':
        return <TypographySection projectId={projectId} />;
      case 'guidelines':
        return <GuidelinesSection projectId={projectId} />;
      case 'features':
        return <FeatureSettingsSection projectId={projectId} />;
      default:
        return <LogosSection projectId={projectId} />;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Header */}
      <header className="h-14 flex items-center justify-between px-4 border-b bg-card shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="soft"
            size="icon"
            onClick={handleBack}
            className="h-8 w-8"
          >
            <ArrowLeft size={16} />
          </Button>

          <div className="flex items-center gap-2">
            <Palette size={20} className="text-primary" />
            <div>
              <h1 className="text-lg font-semibold">Brand Kit</h1>
              <p className="text-xs text-muted-foreground">{project.name}</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <BrandSidebar
          activeSection={activeSection}
          onSectionChange={setActiveSection}
        />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {renderSection()}
          </div>
        </main>
      </div>
    </div>
  );
};
