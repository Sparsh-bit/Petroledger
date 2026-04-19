import { Toaster } from "react-hot-toast";
import { AppRouter } from "./router";
import { ErrorBoundary } from "./components/ErrorBoundary";

export default function App() {
  return (
    <ErrorBoundary>
      <AppRouter />
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#ffffff",
            color: "#0f172a",
            border: "1px solid #e2e8f0",
            boxShadow: "0 4px 12px -4px rgba(15,23,42,0.08)",
          },
          success: {
            iconTheme: { primary: "#4f46e5", secondary: "#ffffff" },
          },
          error: {
            iconTheme: { primary: "#dc2626", secondary: "#ffffff" },
          },
        }}
      />
    </ErrorBoundary>
  );
}
