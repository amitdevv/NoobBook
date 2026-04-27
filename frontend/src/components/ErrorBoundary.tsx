import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ArrowClockwise, House, Warning } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { createLogger } from '@/lib/logger';

const log = createLogger('error-boundary');

interface ErrorBoundaryProps {
  children: ReactNode;
  /**
   * Optional UI override. When omitted the default fallback shows a clear
   * "Something went wrong" panel with reload + go-home actions instead of a
   * blank white screen.
   */
  fallback?: ReactNode;
  /**
   * Stable key — when it changes, the boundary resets its error state. Pass
   * the active route param (e.g. projectId) so navigating to a different
   * project recovers automatically without forcing a full refresh.
   */
  resetKey?: string | number;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Top-level error boundary so a single render-time exception (e.g. a malformed
 * citation, a missing field on a streamed message, a thrown markdown token)
 * doesn't unmount the entire React tree and leave a blank cream-colored page.
 *
 * Class component is required by React's error boundary contract — there is no
 * hook equivalent. Keep this component lean and dependency-free; if it itself
 * throws, the user really does see a blank screen.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    log.error({ err: error, componentStack: errorInfo.componentStack }, 'render error caught');
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  private handleReset = () => {
    this.setState({ error: null });
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-background p-6">
        <div className="max-w-md w-full rounded-2xl border border-amber-600/20 bg-card p-8 shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-full bg-amber-100/60 text-amber-700">
              <Warning size={22} weight="duotone" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-stone-900">Something went wrong</h2>
              <p className="text-xs text-stone-500">
                The page hit an unexpected error while rendering.
              </p>
            </div>
          </div>

          <pre className="text-[11px] leading-relaxed text-stone-600 bg-stone-50 border border-stone-200 rounded-md p-3 overflow-auto max-h-32 whitespace-pre-wrap">
            {this.state.error.message || String(this.state.error)}
          </pre>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button onClick={this.handleReset} variant="default" size="sm">
              Try again
            </Button>
            <Button onClick={this.handleReload} variant="outline" size="sm">
              <ArrowClockwise size={14} className="mr-1.5" />
              Reload page
            </Button>
            <Button onClick={this.handleGoHome} variant="ghost" size="sm">
              <House size={14} className="mr-1.5" />
              Home
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
