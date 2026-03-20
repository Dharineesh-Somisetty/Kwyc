import { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import ScanPage from './components/ScanPage';
import ResultsPage from './components/ResultsPage';
import ProfilesManagePage from './components/ProfilesManagePage';
import HistoryPage from './components/HistoryPage';
import SettingsPage from './components/SettingsPage';
import OnboardingFlow from './components/OnboardingFlow';
import LoadingAnalysis from './components/LoadingAnalysis';
import BottomNav from './components/BottomNav';
import ErrorBoundary from './components/ErrorBoundary';
import HowToUsePage from './components/HowToUsePage';
import BrandLogo from './components/BrandLogo';
import { scanBarcode, scanLabel } from './services/api';
import { createProfile, listProfiles } from './services/profileApi';
import evaluateOcrQuality from './utils/evaluateOcrQuality';

function AppInner() {
  const { session, user, loading: authLoading, signOut } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' | 'signup'

  // ── View & tab state ─────────────────────────────
  const [activeTab, setActiveTab] = useState('scan');  // 'scan' | 'history' | 'profiles' | 'settings'
  const [view, setView] = useState('scan');            // 'scan' | 'loading' | 'results' | 'onboarding'
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastBarcode, setLastBarcode] = useState('');
  const [scoredForName, setScoredForName] = useState('');
  const [showOnboarding, setShowOnboarding] = useState(false);

  // OCR quality gate
  const [ocrQualityInfo, setOcrQualityInfo] = useState(null);

  // ── Check if user needs onboarding ────────────────
  useEffect(() => {
    if (!session || !user) return;
    const onboardingDone = localStorage.getItem(`kwyc_onboarded_${user.id}`);
    if (onboardingDone) return;

    // Check if user has any profiles
    listProfiles()
      .then((profiles) => {
        if (profiles.length === 0) {
          setShowOnboarding(true);
          setView('onboarding');
        } else {
          localStorage.setItem(`kwyc_onboarded_${user.id}`, '1');
        }
      })
      .catch(() => {
        // Silently skip onboarding check on error
      });
  }, [session, user]);

  // Show spinner while Supabase checks session
  if (authLoading) {
    return (
      <div className="min-h-screen bg-bg1 flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-gray-200 border-t-brand animate-spin" />
      </div>
    );
  }

  // Not logged in -> auth pages
  if (!session) {
    if (authView === 'signup') {
      return <Signup onSwitch={() => setAuthView('login')} />;
    }
    return <Login onSwitch={() => setAuthView('signup')} />;
  }

  // ── Onboarding flow ───────────────────────────────
  if (showOnboarding && view === 'onboarding') {
    return (
      <OnboardingFlow
        onNavigateHowTo={() => setView('howto')}
        onComplete={async (profileData) => {
          if (profileData) {
            try {
              await createProfile(profileData);
            } catch {
              // Profile creation failed, still continue
            }
          }
          localStorage.setItem(`kwyc_onboarded_${user.id}`, '1');
          setShowOnboarding(false);
          setView('scan');
        }}
      />
    );
  }

  // ── How-to page during onboarding ──────────────────
  if (showOnboarding && view === 'howto') {
    return <HowToUsePage onBack={() => setView('onboarding')} />;
  }

  // ── Scan handler ──────────────────────────────────
  const handleScanResult = async ({ type, barcode, imageFile, userProfile, profileId, profileName, skipQualityCheck }) => {
    setError(null);
    setOcrQualityInfo(null);
    setIsLoading(true);
    setView('loading');
    setScoredForName(profileName || '');

    try {
      let result;
      if (type === 'barcode') {
        setLastBarcode(barcode);
        result = await scanBarcode(barcode, userProfile, profileId);
      } else {
        const barcodeToSend = barcode || lastBarcode;
        result = await scanLabel(imageFile, userProfile, barcodeToSend, profileId);
        setLastBarcode('');

        // OCR quality gate for label scans
        if (!skipQualityCheck) {
          const rawText = result.ingredients_raw_text || '';
          const quality = evaluateOcrQuality(rawText);
          if (!quality.ok) {
            setOcrQualityInfo({ ...quality, rawText, result });
            setView('scan');
            setActiveTab('scan');
            setIsLoading(false);
            return;
          }
        }
      }
      setAnalysisResult(result);
      setView('results');
    } catch (err) {
      const status = err.response?.status;
      let msg;
      if (status === 429) {
        msg = 'You\'ve reached the scan limit. Please wait a moment and try again.';
      } else {
        msg = err.response?.data?.detail || err.message || 'Something went wrong. Please try again.';
      }
      setError(msg);
      setView('scan');
      setActiveTab('scan');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setView('scan');
    setActiveTab('scan');
    setAnalysisResult(null);
    setError(null);
    setLastBarcode('');
  };

  // ── Tab handler ────────────────────────────────────
  const handleTabChange = (tab) => {
    if (view === 'loading') return;
    setActiveTab(tab);
    if (tab === 'scan') {
      setView('scan');
    } else {
      setView(tab);
    }
    setError(null);
  };

  // ── View from history ──────────────────────────────
  const handleViewHistoryResult = (result) => {
    setAnalysisResult(result);
    setScoredForName('');
    setView('results');
  };

  // Determine if bottom nav should show
  const showBottomNav = view !== 'loading' && view !== 'results';

  return (
    <div className="min-h-screen bg-bg1">
      {/* ── Top bar ──────────────────────────────── */}
      <div className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-gray-100 px-4 py-2 flex items-center justify-between">
        <button
          onClick={() => handleTabChange('scan')}
          className="flex items-center gap-2 min-w-0 text-left min-h-[44px]"
          aria-label="Go to home / scan page"
        >
          <BrandLogo variant="icon" className="h-9 w-9 shrink-0" />
          <div className="min-w-0">
            <span className="block text-sm font-display font-bold text-[#145C2B] truncate">
              KWYC
            </span>
            <span className="hidden sm:block text-[11px] text-gray-400 truncate">
              Know What You Consume
            </span>
          </div>
        </button>

        <div className="flex items-center gap-3 min-w-0">
          <span className="hidden sm:block text-sm text-gray-500 truncate max-w-[220px]">
            {user?.email}
          </span>
        </div>
      </div>

      {/* ── Error toast (with rate limit awareness) ──── */}
      {error && (
        <div
          className={`fixed top-14 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl text-sm shadow-lg animate-slide-up flex items-center gap-3 max-w-[90vw] ${
            error.includes('limit')
              ? 'bg-amber-50 border border-amber-200 text-amber-700'
              : 'bg-white border border-red-200 text-red-600'
          }`}
          role="alert"
        >
          {error.includes('limit') && (
            <svg className="w-5 h-5 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-current opacity-60 hover:opacity-100 min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label="Dismiss error">&#x2715;</button>
        </div>
      )}

      {/* ── Desktop flanks + Main content ────────── */}
      <div className="flex min-h-[calc(100vh-52px)]">

        {/* ── Left decorative flank (desktop only) ── */}
        <aside className="hidden lg:block w-60 xl:w-72 shrink-0 select-none pointer-events-none" aria-hidden="true">
          <div className="sticky top-20 pt-10 pr-5 xl:pr-8 space-y-5">
            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-brandTint flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">Personalized</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Tailored to your health profile, allergies, and dietary needs.</p>
            </div>

            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">AI Analysis</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Powered by AI to parse and evaluate every ingredient.</p>
            </div>

            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-amber-50 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">Conflict Alerts</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Flags allergens, dietary conflicts, and ingredients to watch.</p>
            </div>

            {/* Decorative accent line */}
            <div className="flex items-center gap-2 pt-2 pl-1">
              <div className="w-8 h-0.5 rounded-full bg-brandLine" />
              <div className="w-3 h-0.5 rounded-full bg-brandLine/50" />
            </div>
          </div>
        </aside>

        {/* ── Center content ────────────────────────── */}
        <div className={`flex-1 min-w-0 ${showBottomNav ? 'pb-20' : ''}`}>
          {view === 'scan' && (
            <ErrorBoundary fallbackMessage="The scanner encountered an error. Please try again.">
              <ScanPage
                onScanResult={handleScanResult}
                isLoading={isLoading}
                lastFailedBarcode={lastBarcode}
                ocrQualityInfo={ocrQualityInfo}
                onAcceptPendingResult={() => {
                  if (ocrQualityInfo?.result) {
                    setAnalysisResult(ocrQualityInfo.result);
                    setOcrQualityInfo(null);
                    setView('results');
                  }
                }}
                onClearOcrQuality={() => setOcrQualityInfo(null)}
                onNavigateHowTo={() => setView('howto')}
              />
            </ErrorBoundary>
          )}

          {view === 'loading' && <LoadingAnalysis />}

          {view === 'results' && analysisResult && (
            <ErrorBoundary fallbackMessage="Could not display results. Please scan again.">
              <ResultsPage data={analysisResult} onReset={handleReset} scoredForName={scoredForName} />
            </ErrorBoundary>
          )}

          {view === 'howto' && (
            <HowToUsePage onBack={() => { setView('scan'); setActiveTab('scan'); }} />
          )}

          {view === 'history' && (
            <ErrorBoundary fallbackMessage="Could not load history.">
              <HistoryPage onViewResult={handleViewHistoryResult} />
            </ErrorBoundary>
          )}

          {view === 'profiles' && (
            <ErrorBoundary fallbackMessage="Could not load profiles.">
              <ProfilesManagePage onBack={() => handleTabChange('scan')} />
            </ErrorBoundary>
          )}

          {view === 'settings' && (
            <ErrorBoundary fallbackMessage="Could not load settings.">
              <SettingsPage />
            </ErrorBoundary>
          )}
        </div>

        {/* ── Right decorative flank (desktop only) ── */}
        <aside className="hidden lg:block w-60 xl:w-72 shrink-0 select-none pointer-events-none" aria-hidden="true">
          <div className="sticky top-20 pt-10 pl-5 xl:pl-8 space-y-5">
            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-sky-50 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-sky-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 013.75 9.375v-4.5zM3.75 14.625c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5a1.125 1.125 0 01-1.125-1.125v-4.5zM13.5 4.875c0-.621.504-1.125 1.125-1.125h4.5c.621 0 1.125.504 1.125 1.125v4.5c0 .621-.504 1.125-1.125 1.125h-4.5A1.125 1.125 0 0113.5 9.375v-4.5z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 6.75h.75v.75h-.75v-.75zM6.75 16.5h.75v.75h-.75v-.75zM16.5 6.75h.75v.75h-.75v-.75zM13.5 13.5h.75v.75h-.75v-.75zM13.5 19.5h.75v.75h-.75v-.75zM19.5 13.5h.75v.75h-.75v-.75zM19.5 19.5h.75v.75h-.75v-.75zM16.5 16.5h.75v.75h-.75v-.75z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">Barcode Scan</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Instant results from any product barcode.</p>
            </div>

            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-brandTint flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">Label Photo</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Snap or upload a nutrition label for AI analysis.</p>
            </div>

            <div className="flank-card">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
                  <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-gray-700">Family Profiles</p>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">Separate scores for each family member.</p>
            </div>

            {/* Quick tips */}
            <div className="flank-tip-card">
              <p className="text-xs font-bold text-brandDeep mb-1.5">Did you know?</p>
              <p className="text-xs text-gray-600 leading-relaxed">Red 40 and Yellow 5 are banned in several EU countries but commonly found in US products.</p>
            </div>

            <div className="flank-tip-card">
              <p className="text-xs font-bold text-brandDeep mb-1.5">Tip</p>
              <p className="text-xs text-gray-600 leading-relaxed">Create separate profiles for family members to get personalized scores for each person.</p>
            </div>

            {/* Decorative accent line */}
            <div className="flex items-center gap-2 pt-2">
              <div className="w-8 h-0.5 rounded-full bg-brandLine" />
              <div className="w-3 h-0.5 rounded-full bg-brandLine/50" />
            </div>
          </div>
        </aside>

      </div>

      {/* ── Bottom navigation ────────────────────── */}
      {showBottomNav && (
        <BottomNav
          activeTab={activeTab}
          onTabChange={handleTabChange}
          disabled={isLoading}
        />
      )}
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

export default App;
