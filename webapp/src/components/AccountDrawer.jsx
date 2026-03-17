/**
 * AccountDrawer – slide-in side drawer for account menu.
 * Shows: user email, Manage Profiles link, Sign Out.
 */
import { useEffect, useRef } from 'react';

export default function AccountDrawer({ email, onClose, onManageProfiles, onSignOut }) {
  const drawerRef = useRef(null);

  useEffect(() => {
    document.body.style.overflow = 'hidden';

    // Focus trap: focus the drawer when it opens
    const timer = setTimeout(() => {
      drawerRef.current?.focus();
    }, 100);

    // Close on Escape
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = '';
      clearTimeout(timer);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal="true" aria-label="Account menu">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />

      {/* Drawer panel (right side) */}
      <div ref={drawerRef} tabIndex={-1} className="ml-auto relative z-10 w-72 max-w-[85vw] bg-white h-full shadow-xl flex flex-col animate-slide-in-right outline-none">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-800">Account</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label="Close account menu">&#x2715;</button>
        </div>

        {/* User info */}
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-brandTint flex items-center justify-center">
              <span className="text-brandDeep font-bold text-sm">
                {(email || '?')[0].toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-800 truncate">{email || 'User'}</p>
              <p className="text-xs text-gray-400">Signed in</p>
            </div>
          </div>
        </div>

        {/* Menu items */}
        <nav className="flex-1 px-3 py-3 space-y-1">
          <button
            onClick={() => { onManageProfiles(); onClose(); }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
          >
            <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
            </svg>
            Manage Profiles
          </button>
        </nav>

        {/* Sign out */}
        <div className="px-3 py-4 border-t border-gray-100">
          <button
            onClick={() => { onSignOut(); onClose(); }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-500 hover:bg-red-50 transition"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
