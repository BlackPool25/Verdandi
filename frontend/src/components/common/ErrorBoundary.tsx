import { Component, type ErrorInfo, type ReactNode } from "react";

export interface ErrorBoundaryProps {
  readonly children: ReactNode;
  readonly fallback?: ReactNode;
}

interface ErrorBoundaryState {
  readonly hasError: boolean;
  readonly error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("ErrorBoundary caught an unhandled render error:", error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) {
        return this.props.fallback;
      }
      return (
        <div
          role="alert"
          data-testid="error-boundary-fallback"
          style={{
            padding: 24,
            margin: 16,
            backgroundColor: "#fff0f0",
            border: "1px solid #ef4444",
            borderRadius: 4,
            color: "#1c2127",
            fontFamily: "monospace",
          }}
        >
          <h2 style={{ margin: "0 0 12px 0", color: "#b91c1c" }}>Render Error</h2>
          <p style={{ margin: "0 0 12px 0" }}>
            {this.state.error?.message ?? "An unexpected rendering error occurred."}
          </p>
          <button
            type="button"
            className="px-btn"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
