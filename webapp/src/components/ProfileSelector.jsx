/**
 * ProfileSelector – horizontal pill bar showing household profiles.
 *
 * Features:
 * - Tap a profile pill to select it (used for scoring personalisation)
 * - Long-press or tap edit icon to open EditProfileModal
 * - "+ Add" button respects plan limits
 */
import { useState, useEffect, useCallback } from 'react';
import { listProfiles, createProfile, updateProfile, deleteProfile, setDefaultProfile } from '../services/profileApi';
import { useAuth } from '../context/AuthContext';
import EditProfileModal from './EditProfileModal';

export default function ProfileSelector({ selectedId, onSelect }) {
  const { loading: authLoading } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editTarget, setEditTarget] = useState(null);    // null | {} (new) | profile obj
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const data = await listProfiles();
      setProfiles(data);
      // Auto-select default profile if nothing selected
      if (!selectedId && data.length > 0) {
        const def = data.find((p) => p.is_default) || data[0];
        onSelect(def.id, def.name);
      }
    } catch (err) {
      // If 401 just silently ignore (user not logged in when optional)
      if (err.response?.status !== 401) {
        setError('Could not load profiles');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedId, onSelect]);

  // Wait for auth session to restore before fetching profiles
  useEffect(() => {
    if (!authLoading) refresh();
  }, [authLoading, refresh]);

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
      await refresh();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Could not save profile';
      setError(msg);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this profile?')) return;
    await deleteProfile(id);
    await refresh();
    // If we deleted the selected profile, deselect
    if (selectedId === id) {
      const remaining = profiles.filter((p) => p.id !== id);
      if (remaining.length > 0) onSelect(remaining[0].id, remaining[0].name);
      else onSelect(null, '');
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
        <p className="text-xs text-gray-400">No profiles yet.</p>
        <button
          onClick={() => { setEditTarget({}); setShowModal(true); }}
          className="text-sm text-indigo-500 hover:text-indigo-600 font-medium"
        >
          + Create your first profile
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Error banner */}
      {error && (
        <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-1.5">
          {error}
          <button onClick={() => setError('')} className="ml-2 text-red-400">&#x2715;</button>
        </p>
      )}

      {/* Profile pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {profiles.map((p) => (
          <div key={p.id} className="flex-shrink-0 flex items-center group">
            <button
              onClick={() => onSelect(p.id, p.name)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition whitespace-nowrap ${
                selectedId === p.id
                  ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {p.name}
              {p.is_default && (
                <span className="ml-1 text-[10px] text-indigo-400">★</span>
              )}
            </button>
            {/* Edit/delete on hover */}
            <div className="opacity-0 group-hover:opacity-100 flex items-center ml-1 transition-opacity">
              <button
                onClick={() => { setEditTarget(p); setShowModal(true); }}
                className="text-gray-400 hover:text-indigo-500 text-xs p-1"
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

        {/* Add button */}
        <button
          onClick={() => { setEditTarget({}); setShowModal(true); }}
          className="flex-shrink-0 px-3 py-1.5 rounded-full border border-dashed border-gray-300 text-gray-400 text-sm hover:border-indigo-300 hover:text-indigo-500 transition"
        >
          + Add
        </button>
      </div>

      {/* Edit modal */}
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
