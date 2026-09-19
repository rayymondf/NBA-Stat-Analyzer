import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "./ui";

interface Props {
  children: ReactNode;
  /** Optional callback fired when the user resets the boundary. */
  onReset?: () => void;
}

interface State {
  error: Error | null;
}

/**
 * Route-level error boundary. If a rendering error escapes a page (e.g. an
 * unexpected data shape), it shows an accessible, on-brand fallback instead of a
 * blank screen, and lets the user recover without a full reload. Keyed by route
 * in App so navigating away clears the error automatically.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface for local debugging/observability; never expose internals to users.
    console.error("UI ErrorBoundary caught an error", error, info.componentStack);
  }

  private reset = (): void => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div role="alert" className="card p-8 text-center max-w-lg mx-auto mt-6 section-in">
        <h1 className="font-display text-2xl font-bold">Something went wrong</h1>
        <p className="text-ink-2 text-sm mt-2">
          This section hit an unexpected error. Your data is safe — try again, or
          reload the page.
        </p>
        <p className="text-ink-muted text-xs mt-2 break-words">{error.message}</p>
        <div className="flex flex-wrap gap-2 justify-center mt-5">
          <Button variant="filled" size="sm" onClick={this.reset}>Try again</Button>
          <Button variant="outlined" size="sm" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </div>
      </div>
    );
  }
}
