import { useState } from 'react';
import ScanPage from './components/ScanPage';
import ResultsPage from './components/ResultsPage';
import { scanBarcode, scanLabel } from './services/api';

function App() {
  const [view, setView] = useState('scan');       // 'scan' | 'loading' | 'results'
  const [analysisResult, setAnalysisResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastBarcode, setLastBarcode] = useState('');  // kept across barcode→label fallback

  const handleScanResult = async ({ type, barcode, imageFile, userProfile }) => {
    setError(null);
    setIsLoading(true);
    setView('loading');

    try {
      let result;
      if (type === 'barcode') {
        setLastBarcode(barcode);           // remember for potential label fallback
        result = await scanBarcode(barcode, userProfile);
      } else {
        // Pass lastBarcode (or explicit barcode from payload) so backend can cache
        const barcodeToSend = barcode || lastBarcode;
        result = await scanLabel(imageFile, userProfile, barcodeToSend);
        setLastBarcode('');                // consumed — clear it
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
      // NOTE: lastBarcode is intentionally kept so user can retry via label upload
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
      {/* Error toast */}
      {error && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-white border border-red-200 text-red-600 px-6 py-3 rounded-xl text-sm shadow-lg animate-slide-up flex items-center gap-3">
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
            {/* Spinner */}
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
        <ResultsPage data={analysisResult} onReset={handleReset} />
      )}
    </div>
  );
}

export default App;

