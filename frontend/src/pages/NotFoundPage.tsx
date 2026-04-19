import { Link } from "react-router-dom";
import { Button } from "../components/ui";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 text-slate-900 px-6">
      <div className="text-6xl font-bold tracking-tight text-brand-400">
        404
      </div>
      <p className="mt-4 text-slate-600">
        We couldn&apos;t find that page.
      </p>
      <Link to="/" className="mt-6">
        <Button variant="primary">Back to home</Button>
      </Link>
    </div>
  );
}
