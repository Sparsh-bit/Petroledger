import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (!this.state.error) return this.props.children;

    const message = this.state.error.message || "Something went wrong.";

    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-6 py-12">
        <div className="w-full max-w-md rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            <h1 className="text-base font-semibold">
              This page crashed while rendering
            </h1>
          </div>
          <p className="mt-2 text-sm text-slate-600">
            We logged the error to your browser console. You can try reloading
            — if it keeps happening, copy the message below and send it to
            support.
          </p>
          <pre className="mt-4 max-h-40 overflow-auto rounded-xl border border-red-100 bg-red-50 p-3 text-xs text-red-700 whitespace-pre-wrap">
            {message}
          </pre>
          <div className="mt-5 flex gap-2">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-indigo-200 hover:bg-indigo-500"
            >
              <RefreshCw className="h-4 w-4" /> Reload
            </button>
            <button
              type="button"
              onClick={this.reset}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }
}
