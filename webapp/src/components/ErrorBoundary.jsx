import { Component } from 'react';

/**
 * ErrorBoundary – catches JS errors in child components and shows
 * a friendly fallback instead of crashing the whole app.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 text-center min-h-[200px]">
          <div className="w-14 h-14 mb-4 rounded-2xl bg-red-50 flex items-center justify-center">
            <svg className="w-7 h-7 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-gray-800 mb-1">Something went wrong</h3>
          <p className="text-sm text-gray-500 mb-4 max-w-xs">
            {this.props.fallbackMessage || 'This section encountered an error. Try refreshing.'}
          </p>
          <button
            onClick={this.handleRetry}
            className="btn-primary text-sm px-5 py-2"
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
