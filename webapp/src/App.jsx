import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import ScanPage from './components/ScanPage';
import ResultsPage from './components/ResultsPage';
import AccountDrawer from './components/AccountDrawer';
import ProfilesManagePage from './components/ProfilesManagePage';
import { scanBarcode, scanLabel } from './services/api';
import evaluateOcrQuality from './utils/evaluateOcrQuality';

function AppInner() {
  const { session, user, loading: authLoading, signOut } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' | 'signup'

  const [view, setView] = useState('scan');       // 'scan' | 'loading' | 'results' | 'profiles'
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastBarcode, setLastBarcode] = useState('');
  const [scoredForName, setScoredForName] = useState('');
  const [showAccountDrawer, setShowAccountDrawer] = useState(false);

  // OCR quality gate: when label OCR is poor, stay on scan view with quality info
  const [ocrQualityInfo, setOcrQualityInfo] = useState(null); // { ok, reasons, rawText, result }

  // Show a simple spinner while Supabase checks the session
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#f5f7fb] flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-gray-200 border-t-indigo-500 animate-spin" />
      </div>
    );
  }

  // Not logged in -> show auth pages
  if (!session) {
    if (authView === 'signup') {
      return <Signup onSwitch={() => setAuthView('login')} />;
    }
    return <Login onSwitch={() => setAuthView('signup')} />;
  }

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

        // OCR quality gate for label scans (unless user chose "continue anyway")
        if (!skipQualityCheck) {
          const rawText = result.ingredients_raw_text || '';
          const quality = evaluateOcrQuality(rawText);
          if (!quality.ok) {
            setOcrQualityInfo({ ...quality, rawText, result });
            setView('scan');
            setIsLoading(false);
            return;
          }
        }
      }
      setAnalysisResult(result);
      setView('results');
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Something went wrong. Please try again.';
      setError(msg);
      setView('scan');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setView('scan');
    setAnalysisResult(null);
    setError(null);
    setLastBarcode('');
  };

  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      {/* Top bar with user info + menu */}
      <div className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b border-gray-100 px-4 py-2 flex items-center justify-between">
        {/* Left: go back to home if not on scan */}
        <div className="flex items-center gap-2 min-w-0">
          {view !== 'scan' && view !== 'loading' && (
            <button
              onClick={() => { if (view === 'profiles') setView('scan'); }}
              className="text-sm text-gray-500 hover:text-indigo-600 font-medium truncate max-w-[200px]"
            >
              LabelLens
            </button>
          )}
          {(view === 'scan' || view === 'loading') && (
            <span className="text-sm text-gray-500 truncate max-w-[200px]">
              {user?.email}
            </span>
          )}
        </div>

        {/* Right: menu button */}
        <button
          onClick={() => setShowAccountDrawer(true)}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition text-gray-500 hover:text-gray-700"
          title="Account menu"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
      </div>

      {/* Error toast */}
      {error && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 bg-white border border-red-200 text-red-600 px-6 py-3 rounded-xl text-sm shadow-lg animate-slide-up flex items-center gap-3">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">&#x2715;</button>
        </div>
      )}

      {view === 'scan' && (
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
      )}

      {view === 'loading' && (
        <div className="min-h-screen bg-[#f5f7fb] flex items-center justify-center">
          <div className="bg-white border border-gray-100 rounded-3xl shadow-card p-12 text-center animate-fade-in max-w-sm">
            <div className="w-16 h-16 mx-auto mb-6 rounded-full border-4 border-gray-200 border-t-indigo-500 animate-spin" />
            <h2 className="text-2xl font-bold mb-3 gradient-text">Analyzing...</h2>
            <p className="text-gray-500 text-sm">Identifying ingredients, checking conflicts, and generating your personalized summary.</p>
            <div className="mt-6 w-full bg-gray-100 rounded-full h-2 overflow-hidden">
              <div className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 rounded-full animate-pulse" style={{ width: '70%' }} />
            </div>
          </div>
        </div>
      )}

      {view === 'results' && analysisResult && (
        <ResultsPage data={analysisResult} onReset={handleReset} scoredForName={scoredForName} />
      )}

      {view === 'profiles' && (
        <ProfilesManagePage onBack={() => setView('scan')} />
      )}

      {/* Account drawer */}
      {showAccountDrawer && (
        <AccountDrawer
          email={user?.email}
          onClose={() => setShowAccountDrawer(false)}
          onManageProfiles={() => setView('profiles')}
          onSignOut={signOut}
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
