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

      {/* ── Main content ─────────────────────────── */}
      <div className={showBottomNav ? 'pb-20' : ''}>
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
            />
          </ErrorBoundary>
        )}

        {view === 'loading' && <LoadingAnalysis />}

        {view === 'results' && analysisResult && (
          <ErrorBoundary fallbackMessage="Could not display results. Please scan again.">
            <ResultsPage data={analysisResult} onReset={handleReset} scoredForName={scoredForName} />
          </ErrorBoundary>
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
