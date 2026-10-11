'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, RotateCcw, Home } from 'lucide-react';

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled application error:', error);
  }, [error]);

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
      <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <h1 className="text-xl font-bold text-ink mb-2">Something went wrong</h1>
      <p className="text-xs text-muted max-w-md mb-6">
        {error.message || 'An unexpected error occurred while rendering this page.'}
      </p>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => reset()}
          className="flex items-center gap-2 bg-primary hover:bg-primary-hover text-white text-xs font-semibold py-2 px-4 rounded-lg transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          Try Again
        </button>
        <Link
          href="/explore"
          className="flex items-center gap-2 bg-slate-100 hover:bg-slate-200 text-ink text-xs font-semibold py-2 px-4 rounded-lg transition-colors"
        >
          <Home className="w-4 h-4" />
          Return to Explore
        </Link>
      </div>
    </div>
  );
}
