/**
 * OnboardingFlow – guided setup for new users.
 * Walks users through creating their first health profile.
 */
import { useState } from 'react';
import BrandLogo from './BrandLogo';

const ALLERGY_OPTIONS = ['Peanuts', 'Tree Nuts', 'Milk', 'Eggs', 'Soy', 'Wheat', 'Fish', 'Shellfish', 'Sesame'];
const DIET_OPTIONS = [
  { value: '', label: 'No preference' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'halal', label: 'Halal' },
];

export default function OnboardingFlow({ onComplete }) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [allergies, setAllergies] = useState([]);
  const [dietStyle, setDietStyle] = useState('');
  const [avoidTerms, setAvoidTerms] = useState('');

  const toggleAllergy = (a) => {
    setAllergies((prev) =>
      prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a]
    );
  };

  const handleFinish = () => {
    onComplete({
      name: name.trim() || 'Me',
      allergies,
      diet_style: dietStyle || null,
      avoid_terms: avoidTerms
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      is_default: true,
    });
  };

  const steps = [
    // Step 0: Welcome
    <div key="welcome" className="text-center animate-fade-in">
      <BrandLogo showTagline />
      <h2 className="text-2xl font-display font-extrabold gradient-text mt-6 mb-3">
        Welcome to KWYC!
      </h2>
      <p className="text-gray-500 text-sm max-w-sm mx-auto mb-8">
        Let's set up your health profile so we can personalize ingredient analysis just for you.
      </p>
      <button onClick={() => setStep(1)} className="btn-primary text-sm px-8 py-3">
        Get Started
      </button>
      <button
        onClick={() => onComplete(null)}
        className="block mx-auto mt-4 text-xs text-gray-400 hover:text-gray-600"
      >
        Skip for now
      </button>
    </div>,

    // Step 1: Name
    <div key="name" className="animate-fade-in">
      <div className="text-center mb-6">
        <span className="text-xs text-gray-400 uppercase tracking-wider">Step 1 of 3</span>
        <h2 className="text-xl font-bold text-gray-800 mt-1">What should we call you?</h2>
        <p className="text-gray-400 text-sm mt-1">This helps identify your profile if you add family members later.</p>
      </div>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. Me, John, Mom..."
        className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 focus:outline-none focus:border-brand transition-colors text-center text-lg"
        autoFocus
      />
      <div className="flex gap-3 mt-6">
        <button onClick={() => setStep(0)} className="btn-secondary text-sm flex-1">Back</button>
        <button onClick={() => setStep(2)} className="btn-primary text-sm flex-1">Next</button>
      </div>
    </div>,

    // Step 2: Allergies & Diet
    <div key="allergies" className="animate-fade-in">
      <div className="text-center mb-6">
        <span className="text-xs text-gray-400 uppercase tracking-wider">Step 2 of 3</span>
        <h2 className="text-xl font-bold text-gray-800 mt-1">Any dietary needs?</h2>
        <p className="text-gray-400 text-sm mt-1">Select your allergies and diet preference.</p>
      </div>

      <div className="mb-5">
        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Allergies</label>
        <div className="flex flex-wrap gap-2">
          {ALLERGY_OPTIONS.map((a) => (
            <button
              key={a}
              onClick={() => toggleAllergy(a.toLowerCase())}
              className={`px-3 py-1.5 rounded-full text-sm font-medium border transition min-h-[36px] ${
                allergies.includes(a.toLowerCase())
                  ? 'bg-red-50 text-red-600 border-red-200'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-5">
        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Diet</label>
        <div className="flex flex-wrap gap-2">
          {DIET_OPTIONS.map((d) => (
            <button
              key={d.value}
              onClick={() => setDietStyle(d.value)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition min-h-[36px] ${
                dietStyle === d.value
                  ? 'bg-brandTint text-brandDeep border-brandLine'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-3 mt-6">
        <button onClick={() => setStep(1)} className="btn-secondary text-sm flex-1">Back</button>
        <button onClick={() => setStep(3)} className="btn-primary text-sm flex-1">Next</button>
      </div>
    </div>,

    // Step 3: Avoid terms + finish
    <div key="avoid" className="animate-fade-in">
      <div className="text-center mb-6">
        <span className="text-xs text-gray-400 uppercase tracking-wider">Step 3 of 3</span>
        <h2 className="text-xl font-bold text-gray-800 mt-1">Anything else to avoid?</h2>
        <p className="text-gray-400 text-sm mt-1">Add specific ingredients you'd like to flag (comma-separated).</p>
      </div>

      <textarea
        value={avoidTerms}
        onChange={(e) => setAvoidTerms(e.target.value)}
        placeholder="e.g. palm oil, MSG, artificial colors..."
        rows={3}
        className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 focus:outline-none focus:border-brand transition-colors text-sm resize-none"
      />

      {/* Summary preview */}
      <div className="mt-5 bg-brandTint border border-brandLine rounded-2xl p-4">
        <h4 className="text-xs font-semibold text-brandDeep uppercase tracking-wider mb-2">Your Profile</h4>
        <p className="text-sm text-gray-700 font-medium">{name || 'Me'}</p>
        {allergies.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {allergies.map((a) => (
              <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-red-50 text-red-500 border border-red-200 capitalize">{a}</span>
            ))}
          </div>
        )}
        {dietStyle && <p className="text-xs text-gray-500 mt-1 capitalize">{dietStyle}</p>}
      </div>

      <div className="flex gap-3 mt-6">
        <button onClick={() => setStep(2)} className="btn-secondary text-sm flex-1">Back</button>
        <button onClick={handleFinish} className="btn-primary text-sm flex-1">
          Create Profile & Start Scanning
        </button>
      </div>
    </div>,
  ];

  return (
    <div className="min-h-screen bg-bg1 flex items-center justify-center p-4">
      <div className="bg-white border border-gray-100 rounded-3xl shadow-card p-8 w-full max-w-md">
        {/* Progress dots */}
        {step > 0 && (
          <div className="flex justify-center gap-1.5 mb-6">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`w-2 h-2 rounded-full transition-all ${
                  s <= step ? 'bg-brand w-6' : 'bg-gray-200'
                }`}
              />
            ))}
          </div>
        )}
        {steps[step]}
      </div>
    </div>
  );
}
