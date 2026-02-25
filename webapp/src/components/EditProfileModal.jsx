/**
 * EditProfileModal – create or edit a household profile.
 * Renders as a slide-up modal overlay.
 */
import { useState, useEffect } from 'react';

const DIET_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'halal', label: 'Halal' },
];

export default function EditProfileModal({ profile, onSave, onClose }) {
  const isNew = !profile?.id;

  const [name, setName] = useState(profile?.name || '');
  const [dietStyle, setDietStyle] = useState(profile?.diet_style || '');
  const [allergiesText, setAllergiesText] = useState(
    (profile?.allergies || []).join(', ')
  );
  const [avoidText, setAvoidText] = useState(
    (profile?.avoid_terms || []).join(', ')
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const data = {
      name: name.trim() || 'Me',
      diet_style: dietStyle || null,
      allergies: allergiesText
        .split(',')
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      avoid_terms: avoidText
        .split(',')
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
    };
    await onSave(data, profile?.id);
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <form
        onSubmit={handleSubmit}
        className="relative z-10 bg-white rounded-t-3xl sm:rounded-3xl shadow-xl w-full max-w-md p-6 space-y-4 animate-slide-up"
      >
        <h2 className="text-lg font-bold text-gray-800">
          {isNew ? 'Add Profile' : 'Edit Profile'}
        </h2>

        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Mom, Dad, Kid"
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-sm transition"
          />
        </div>

        {/* Diet */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            Diet
          </label>
          <div className="flex flex-wrap gap-2">
            {DIET_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setDietStyle(opt.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition ${
                  dietStyle === opt.value
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                    : 'border-gray-200 text-gray-500 hover:border-gray-300'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Allergies */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            Allergies (comma-separated)
          </label>
          <input
            type="text"
            value={allergiesText}
            onChange={(e) => setAllergiesText(e.target.value)}
            placeholder="e.g. peanuts, milk, shellfish"
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-sm transition"
          />
        </div>

        {/* Avoid terms */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">
            Avoid (comma-separated)
          </label>
          <input
            type="text"
            value={avoidText}
            onChange={(e) => setAvoidText(e.target.value)}
            placeholder="e.g. palm oil, MSG, aspartame"
            className="w-full px-3 py-2 rounded-xl border border-gray-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-sm transition"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 text-white text-sm font-semibold hover:shadow-lg transition disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
}
