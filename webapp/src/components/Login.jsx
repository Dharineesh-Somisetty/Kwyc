/**
 * Login page – email + password auth via Supabase.
 * Includes a link to the Signup page.
 */
import { useState } from 'react';
import { supabase } from '../services/supabaseClient';

export default function Login({ onSwitch }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    const { error: err } = await supabase.auth.signInWithPassword({ email, password });
    if (err) setError(err.message);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#f5f7fb] flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white border border-gray-100 rounded-3xl shadow-card p-8 w-full max-w-sm space-y-5 animate-fade-in"
      >
        <h1 className="text-2xl font-bold gradient-text text-center">Welcome Back</h1>
        <p className="text-gray-500 text-sm text-center">Sign in to LabelLens</p>

        {error && (
          <p className="text-red-500 text-sm bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-sm transition"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl border border-gray-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-sm transition"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-semibold text-sm hover:shadow-lg transition disabled:opacity-50"
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>

        <p className="text-center text-sm text-gray-400">
          Don&apos;t have an account?{' '}
          <button type="button" onClick={onSwitch} className="text-indigo-500 hover:underline font-medium">
            Sign Up
          </button>
        </p>
      </form>
    </div>
  );
}
