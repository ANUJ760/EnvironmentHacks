import Link from 'next/link';
import { Compass, Home } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mb-4">
        <Compass className="w-6 h-6" />
      </div>
      <h1 className="text-xl font-bold text-ink mb-2">Page or Resource Not Found</h1>
      <p className="text-xs text-muted max-w-md mb-6">
        The requested path does not exist, or the scenario/city you are looking for has been removed.
      </p>

      <Link
        href="/explore"
        className="flex items-center gap-2 bg-primary hover:bg-primary-hover text-white text-xs font-semibold py-2 px-4 rounded-lg transition-colors"
      >
        <Home className="w-4 h-4" />
        Explore Registered Cities
      </Link>
    </div>
  );
}
