/**
 * SettingsPage – account settings and preferences.
 */
import { useAuth } from '../context/AuthContext';

export default function SettingsPage() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen bg-bg1 text-gray-800 pb-24">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <h1 className="text-2xl font-display font-extrabold text-gray-900 mb-1">Settings</h1>
        <p className="text-sm text-gray-400 mb-6">Manage your account</p>

        {/* Account info */}
        <div className="glass-strong p-5 mb-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-brandTint flex items-center justify-center">
              <span className="text-brandDeep font-bold text-lg">
                {(user?.email || '?')[0].toUpperCase()}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-gray-800 truncate">{user?.email || 'User'}</p>
              <p className="text-xs text-gray-400">Signed in</p>
            </div>
          </div>
        </div>

        {/* App info */}
        <div className="glass-strong p-5 mb-3">
          <h3 className="text-sm font-bold text-gray-700 mb-3">About</h3>
          <div className="space-y-2 text-sm text-gray-500">
            <div className="flex justify-between">
              <span>App</span>
              <span className="text-gray-700 font-medium">KWYC</span>
            </div>
            <div className="flex justify-between">
              <span>Version</span>
              <span className="text-gray-700 font-medium">2.0.0</span>
            </div>
            <div className="flex justify-between">
              <span>Description</span>
              <span className="text-gray-700 font-medium text-right text-xs max-w-[60%]">Know What You Consume</span>
            </div>
          </div>
        </div>

        {/* Sign out */}
        <button
          onClick={signOut}
          className="w-full glass-strong p-4 text-center text-sm font-medium text-red-500 hover:bg-red-50 transition rounded-3xl"
        >
          Sign Out
        </button>
      </div>
    </div>
  );
}
