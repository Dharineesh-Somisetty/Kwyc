/**
 * ProfileSelector – horizontal pill bar showing household profiles.
 */
import { useState, useEffect, useCallback } from 'react';
import { listProfiles, createProfile, updateProfile, deleteProfile } from '../services/profileApi';
import { useAuth } from '../context/AuthContext';
import EditProfileModal from './EditProfileModal';

export default function ProfileSelector({ selectedId, onSelect }) {
  const { session, loading: authLoading } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editTarget, setEditTarget] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const data = await listProfiles();
      setProfiles(data);
      setError('');
      if (!selectedId && data.length > 0) {
        const def = data.find((p) => p.is_default) || data[0];
        onSelect(def.id, def.name);
      }
    } catch (err) {
      // Never call signOut here – a 401 may be a transient race condition.
      // The response interceptor in api.js already retries once automatically.
      setError('Could not load profiles');
    } finally {
      setLoading(false);
    }
  }, [selectedId, onSelect]);

  // Only fetch once we have a confirmed session (avoids firing before token is ready)
  useEffect(() => {
    if (!authLoading && session) refresh();
  }, [authLoading, session, refresh]);

  const handleSave = async (data, profileId) => {
    try {
      if (profileId) {
        await updateProfile(profileId, data);
      } else {
        const p = await createProfile(data);
        onSelect(p.id, p.name);
      }
      setShowModal(false);
      setEditTarget(null);
      setError('');
      await refresh();
    } catch (err) {
      const status = err.response?.status;
      if (status === 403) {
        setError('Upgrade to add more profiles.');
        return;
      }
      if (status === 422) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Please check your input (name is required).');
        return;
      }
      setError(err.response?.data?.detail || 'Could not save profile');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this profile?')) return;
    try {
      await deleteProfile(id);
      await refresh();
      if (selectedId === id) {
        const remaining = profiles.filter((p) => p.id !== id);
        if (remaining.length > 0) onSelect(remaining[0].id, remaining[0].name);
        else onSelect(null, '');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not delete profile');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 px-1 py-2">
        <div className="h-8 w-20 bg-gray-100 rounded-full animate-pulse" />
        <div className="h-8 w-20 bg-gray-100 rounded-full animate-pulse" />
      </div>
    );
  }

  if (profiles.length === 0 && !showModal) {
    return (
      <div className="space-y-2">
        {error && (
          <div className="flex items-center gap-2 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-1.5">
            <span className="flex-1">{error}</span>
            <button onClick={() => { setError(''); setLoading(true); refresh(); }} className="text-brandDeep font-medium hover:underline shrink-0">Retry</button>
            <button onClick={() => setError('')} className="text-red-400">&#x2715;</button>
          </div>
        )}
        <div className="flex items-start gap-3 bg-brandTint border border-brandLine rounded-xl p-3">
          <svg className="w-5 h-5 text-brandDeep shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          <div>
            <p className="text-sm text-brandDeep font-medium">Set up your health profile for personalized results</p>
            <p className="text-xs text-gray-500 mt-0.5">Add your allergies and dietary preferences to get tailored ingredient analysis.</p>
          </div>
        </div>
        <button
          onClick={() => { setEditTarget({}); setShowModal(true); }}
          className="text-sm text-brandDeep hover:text-brand font-medium min-h-[44px]"
        >
          + Create your first profile
        </button>
        {showModal && (
          <EditProfileModal
            profile={null}
            onSave={handleSave}
            onClose={() => { setShowModal(false); setEditTarget(null); }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-1.5">
          <span className="flex-1">{error}</span>
          <button
            onClick={() => { setError(''); setLoading(true); refresh(); }}
            className="text-brandDeep font-medium hover:underline shrink-0"
          >
            Retry
          </button>
          <button onClick={() => setError('')} className="text-red-400">&#x2715;</button>
        </div>
      )}

      {/* Profile pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {profiles.map((p) => (
          <div key={p.id} className="flex-shrink-0 flex items-center group">
            <button
              onClick={() => onSelect(p.id, p.name)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition whitespace-nowrap ${
                selectedId === p.id
                  ? 'bg-brandTint border-brandLine text-brandDeep'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {p.name}
              {p.is_default && <span className="ml-1 text-[10px] text-brandSoft">★</span>}
            </button>
            <div className="opacity-0 group-hover:opacity-100 flex items-center ml-1 transition-opacity">
              <button
                onClick={() => { setEditTarget(p); setShowModal(true); }}
                className="text-gray-400 hover:text-brandDeep text-xs p-1"
                title="Edit"
              >
                ✎
              </button>
              {profiles.length > 1 && (
                <button
                  onClick={() => handleDelete(p.id)}
                  className="text-gray-400 hover:text-red-500 text-xs p-1"
                  title="Delete"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        ))}

        <button
          onClick={() => { setEditTarget({}); setShowModal(true); }}
          className="flex-shrink-0 px-3 py-1.5 rounded-full border border-dashed border-gray-300 text-gray-400 text-sm hover:border-brandLine hover:text-brandDeep transition"
        >
          + Add
        </button>
      </div>

      {showModal && (
        <EditProfileModal
          profile={editTarget?.id ? editTarget : null}
          onSave={handleSave}
          onClose={() => { setShowModal(false); setEditTarget(null); }}
        />
      )}
    </div>
  );
}
