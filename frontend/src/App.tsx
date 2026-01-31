import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { Dashboard, CreateProjectDialog } from './components/dashboard';
import { ProjectWorkspace } from './components/project';
import { BrandPage } from './components/brand/BrandPage';
import { LoginPage, ProtectedRoute } from './components/auth';
import { AuthProvider } from './hooks/useAuth';
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
  refreshTrigger: number;
  setRefreshTrigger: (fn: (prev: number) => number) => void;
}

/**
 * AppContent Component
 * Educational Note: Handles the Dashboard view only.
 * Project workspace is now handled by /projects/:projectId route.
 */
function AppContent({
  showCreateDialog,
  setShowCreateDialog,
  refreshTrigger,
  setRefreshTrigger,
}: AppContentProps) {
  const navigate = useNavigate();

  const handleProjectCreated = (project: Project) => {
    console.log('Project created/updated:', project);
    setShowCreateDialog(false);
    setRefreshTrigger(prev => prev + 1);
  };

  const handleSelectProject = (project: Project) => {
    // Navigate to project URL - this updates the browser URL
    // and triggers the ProjectWorkspaceRoute to load
    navigate(`/projects/${project.id}`);
  };

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

/**
 * ProjectWorkspaceRoute Component
 * Educational Note: Wrapper that loads project from URL param and renders workspace.
 * This allows direct navigation to /projects/:projectId and proper URL-based routing.
 */
function ProjectWorkspaceRoute({
  setRefreshTrigger,
}: {
  setRefreshTrigger: (fn: (prev: number) => number) => void;
}) {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadProject = async () => {
      if (!projectId) {
        navigate('/');
        return;
      }

      try {
        const response = await projectsAPI.get(projectId);
        setProject(response.data.project);
      } catch (error) {
        console.error('Failed to load project:', error);
        navigate('/');
      } finally {
        setLoading(false);
      }
    };

    loadProject();
  }, [projectId, navigate]);

  const handleDeleteProject = async (id: string) => {
    try {
      await projectsAPI.delete(id);
      setRefreshTrigger(prev => prev + 1);
      navigate('/');
    } catch (error) {
      console.error('Failed to delete project:', error);
    }
  };

  const handleNavigateToBrand = (id: string) => {
    navigate(`/projects/${id}/brand`);
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!project) {
    return null;
  }

  return (
    <ProjectWorkspace
      project={project}
      onBack={() => navigate('/')}
      onDeleteProject={handleDeleteProject}
      onNavigateToBrand={handleNavigateToBrand}
    />
  );
}

function App() {
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route - Login/Signup */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes - require authentication */}
          <Route path="/projects/:projectId/brand" element={
            <ProtectedRoute><BrandPage /></ProtectedRoute>
          } />

          <Route
            path="/projects/:projectId"
            element={
              <ProtectedRoute>
                <ProjectWorkspaceRoute
                  setRefreshTrigger={setRefreshTrigger}
                />
              </ProtectedRoute>
            }
          />

          <Route
            path="*"
            element={
              <ProtectedRoute>
                <AppContent
                  showCreateDialog={showCreateDialog}
                  setShowCreateDialog={setShowCreateDialog}
                  refreshTrigger={refreshTrigger}
                  setRefreshTrigger={setRefreshTrigger}
                />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App
