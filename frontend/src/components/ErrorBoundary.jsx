import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import Button from './Button';

/**
 * Catches JavaScript runtime errors in child components and prevents blank white screens.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('VirtualFit AI ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[450px] flex items-center justify-center p-6 text-center">
          <div className="max-w-md w-full rounded-3xl bg-white border border-rose-200 p-8 shadow-sm">
            <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-7 h-7" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 mb-2">Something went wrong</h2>
            <p className="text-xs text-slate-600 mb-6 leading-relaxed">
              We encountered an issue loading this section. You can reload the page or return to the home screen.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button
                variant="primary"
                size="sm"
                leftIcon={RefreshCw}
                onClick={this.handleReload}
              >
                Reload Page
              </Button>
              <Button
                to="/"
                variant="outline"
                size="sm"
                leftIcon={Home}
                onClick={() => this.setState({ hasError: false, error: null })}
              >
                Back to Home
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

