'use client';

import React, { useState } from 'react';
import { useSession, signIn, signOut } from 'next-auth/react';
import { User, LogIn, LogOut, ShieldCheck, Key, AlertCircle } from 'lucide-react';

export default function AccountPage() {
  const { data: session, status } = useSession();
  const [username, setUsername] = useState('local-developer');

  const handleDevLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    await signIn('dev-login', {
      username,
      callbackUrl: '/explore',
    });
  };

  return (
    <div className="flex-1 max-w-xl w-full mx-auto p-6 md:p-12 space-y-6">
      <div className="border-b border-border pb-4">
        <h1 className="text-2xl font-bold text-ink">Account & Session Identity</h1>
        <p className="text-xs text-muted mt-1">
          Server-side session management for authenticated scenario editing and simulation execution.
        </p>
      </div>

      {status === 'authenticated' ? (
        <div className="bg-white border border-border rounded-xl p-6 shadow-sm space-y-4 text-xs">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary-light text-primary flex items-center justify-center">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-sm text-ink">{session.user?.name || 'Authenticated User'}</h2>
              <p className="text-muted">{session.user?.email || 'Active Session'}</p>
            </div>
          </div>

          <div className="bg-slate-50 border border-border rounded-lg p-3 space-y-1 text-slate-700">
            <div className="flex justify-between">
              <span>Session State:</span>
              <span className="font-semibold text-emerald-700">Active</span>
            </div>
            <div className="flex justify-between">
              <span>Security Policy:</span>
              <span>Tokens kept HttpOnly on server BFF</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => signOut({ callbackUrl: '/' })}
            className="w-full flex items-center justify-center gap-2 bg-slate-100 hover:bg-rose-50 hover:text-rose-700 text-ink font-semibold py-2 px-4 rounded-lg transition-colors border border-border"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      ) : (
        <div className="bg-white border border-border rounded-xl p-6 shadow-sm space-y-5 text-xs">
          <div className="space-y-1">
            <h2 className="font-bold text-sm text-ink">Sign In to EcoTwin</h2>
            <p className="text-muted">
              Sign in to create scenarios, stage land-cover interventions, and trigger simulation runs.
            </p>
          </div>

          {/* Dev Mode Login Form */}
          <form onSubmit={handleDevLogin} className="space-y-3 pt-2">
            <div>
              <label htmlFor="login-username" className="block text-xs font-semibold text-ink mb-1">
                Developer Identity Subject
              </label>
              <input
                id="login-username"
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full text-xs px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                placeholder="e.g. local-developer"
              />
            </div>

            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white font-semibold py-2 px-4 rounded-lg transition-colors shadow-xs"
            >
              <LogIn className="w-4 h-4" />
              Sign In (Local Dev Session)
            </button>
          </form>

          <div className="bg-slate-50 border border-border rounded-lg p-3 text-[11px] text-muted space-y-1.5">
            <div className="font-semibold text-ink flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-primary" />
              Backend Token Requirement:
            </div>
            <p>
              In local development mode (<code>FRONTEND_AUTH_MODE=dev</code>), the server injects <code>ECOTWIN_DEV_BEARER_TOKEN</code> from your <code>frontend/.env.local</code>.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
