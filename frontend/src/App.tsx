import { useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { Dashboard, CreateProjectDialog } from './components/dashboard';
import { ProjectWorkspace } from './components/project';
import { BrandPage } from './components/brand/BrandPage';
import { projectsAPI } from './lib/api';

/**
 * Main App Component for NoobBook
 * Educational Note: This component manages the overall application state
 * and controls which view is shown (project list, create dialog, or project workspace).
 * React Router is used for navigation to full-page views like Brand Kit.
 */

/**
 * Project Type
 * Educational Note: This interface defines the shape of a project object
 * returned from the API. It's used throughout the app for type safety.
 */
interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_accessed: string;
}

interface AppContentProps {
  showCreateDialog: boolean;
  setShowCreateDialog: (show: boolean) => void;
  selectedProject: Project | null;
  setSelectedProject: (project: Project | null) => void;
  refreshTrigger: number;
  setRefreshTrigger: (fn: (prev: number) => number) => void;
}

function AppContent({
  showCreateDialog,
  setShowCreateDialog,
  selectedProject,
  setSelectedProject,
  refreshTrigger,
  setRefreshTrigger,
}: AppContentProps) {
  const navigate = useNavigate();

  const handleProjectCreated = (project: Project) => {
    console.log('Project created/updated:', project);
    setShowCreateDialog(false);
    // Trigger refresh of project list
    setRefreshTrigger(prev => prev + 1);
  };

  const handleSelectProject = (project: Project) => {
    console.log('Project selected:', project);
    setSelectedProject(project);
  };

  const handleDeleteProject = async (projectId: string) => {
    try {
      await projectsAPI.delete(projectId);
      console.log('Project deleted successfully');
      setSelectedProject(null);
      setRefreshTrigger(prev => prev + 1);
    } catch (error) {
      console.error('Failed to delete project:', error);
    }
  };

  const handleNavigateToBrand = (projectId: string) => {
    navigate(`/projects/${projectId}/brand`);
  };

  // If a project is selected, show the project workspace
  if (selectedProject) {
    return (
      <ProjectWorkspace
        project={selectedProject}
        onBack={() => setSelectedProject(null)}
        onDeleteProject={handleDeleteProject}
        onNavigateToBrand={handleNavigateToBrand}
      />
    );
  }

  return (
    <>
      <Dashboard
        onSelectProject={handleSelectProject}
        onCreateNewProject={() => setShowCreateDialog(true)}
        refreshTrigger={refreshTrigger}
      />

      {showCreateDialog && (
        <CreateProjectDialog
          onClose={() => setShowCreateDialog(false)}
          onProjectCreated={handleProjectCreated}
        />
      )}
    </>
  );
}

function App() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  return (
    <BrowserRouter>
      <Routes>
        {/* Brand Kit Page - Full page for brand management */}
        <Route path="/projects/:projectId/brand" element={<BrandPage />} />

        {/* Main App - Dashboard and Project Workspace */}
        <Route
          path="*"
          element={
            <AppContent
              showCreateDialog={showCreateDialog}
              setShowCreateDialog={setShowCreateDialog}
              selectedProject={selectedProject}
              setSelectedProject={setSelectedProject}
              refreshTrigger={refreshTrigger}
              setRefreshTrigger={setRefreshTrigger}
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App
