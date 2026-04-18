import { Toaster } from "react-hot-toast";
import { AppRouter } from "./router";

export default function App() {
  return (
    <>
      <AppRouter />
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#0f172a",
            color: "#e2e8f0",
            border: "1px solid #1e293b",
          },
        }}
      />
    </>
  );
}
