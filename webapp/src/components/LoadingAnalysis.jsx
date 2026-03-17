/**
 * LoadingAnalysis – animated loading screen with progressive stages
 * instead of a misleading static progress bar.
 */
import { useState, useEffect } from 'react';

const STAGES = [
  { label: 'Reading label...', icon: '📸', duration: 2500 },
  { label: 'Identifying ingredients...', icon: '🔬', duration: 3000 },
  { label: 'Checking conflicts...', icon: '🛡️', duration: 2500 },
  { label: 'Generating summary...', icon: '✍️', duration: 4000 },
];

export default function LoadingAnalysis() {
  const [currentStage, setCurrentStage] = useState(0);

  useEffect(() => {
    const timers = [];
    let elapsed = 0;
    STAGES.forEach((stage, i) => {
      if (i === 0) return; // Start at 0
      elapsed += stage.duration;
      timers.push(setTimeout(() => setCurrentStage(i), elapsed));
    });
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="min-h-screen bg-bg1 flex items-center justify-center px-4">
      <div className="bg-white border border-gray-100 rounded-3xl shadow-card p-10 text-center animate-fade-in max-w-sm w-full">
        {/* Animated spinner */}
        <div className="relative w-20 h-20 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-4 border-gray-100" />
          <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-brand animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center text-2xl">
            {STAGES[currentStage].icon}
          </div>
        </div>

        <h2 className="text-2xl font-bold mb-2 gradient-text">Analyzing...</h2>

        {/* Stage indicators */}
        <div className="space-y-2 mt-6 text-left">
          {STAGES.map((stage, i) => (
            <div
              key={i}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-xl transition-all duration-500 ${
                i < currentStage
                  ? 'bg-emerald-50 text-emerald-700'
                  : i === currentStage
                  ? 'bg-brandTint text-brandDeep'
                  : 'text-gray-300'
              }`}
            >
              {i < currentStage ? (
                <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : i === currentStage ? (
                <div className="w-4 h-4 rounded-full border-2 border-brandDeep border-t-transparent animate-spin shrink-0" />
              ) : (
                <div className="w-4 h-4 rounded-full border-2 border-gray-200 shrink-0" />
              )}
              <span className="text-sm font-medium">{stage.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
