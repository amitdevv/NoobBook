/**
 * Protected Route Component
 *
 * Educational Note: This component acts as a route guard.
 * It checks if the user is authenticated before rendering children.
 * If not authenticated, it redirects to the login page.
 * During the initial session check (loading), it shows a spinner.
 */

import { Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  // Show spinner during initial session check
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
