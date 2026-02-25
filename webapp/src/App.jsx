import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import ScanPage from './components/ScanPage';
import ResultsPage from './components/ResultsPage';
import { scanBarcode, scanLabel } from './services/api';

function AppInner() {
  const { session, user, loading: authLoading, signOut } = useAuth();
  const [authView, setAuthView] = useState('login'); // 'login' | 'signup'

  const [view, setView] = useState('scan');       // 'scan' | 'loading' | 'results'
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastBarcode, setLastBarcode] = useState('');
  const [scoredForName, setScoredForName] = useState('');

  // Show a simple spinner while Supabase checks the session
  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#f5f7fb] flex items-center justify-center">
        <div className="w-10 h-10 rounded-full border-4 border-gray-200 border-t-indigo-500 animate-spin" />
      </div>
    );
  }

  // Not logged in → show auth pages
  if (!session) {
    if (authView === 'signup') {
      return <Signup onSwitch={() => setAuthView('login')} />;
    }
    return <Login onSwitch={() => setAuthView('signup')} />;
  }

  const handleScanResult = async ({ type, barcode, imageFile, userProfile, profileId, profileName }) => {
    setError(null);
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
      {/* Top bar with user info + sign out */}
      <div className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b border-gray-100 px-4 py-2 flex items-center justify-between">
        <span className="text-sm text-gray-500 truncate max-w-[200px]">
          {user?.email}
        </span>
        <button
          onClick={signOut}
          className="text-xs text-gray-400 hover:text-red-500 font-medium transition"
        >
          Sign Out
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
        <ScanPage onScanResult={handleScanResult} isLoading={isLoading} lastFailedBarcode={lastBarcode} />
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

