/**
 * HistoryPage – shows the user's past scans with search.
 */
import { useState, useEffect, useCallback } from 'react';
import { listHistory, searchHistory, getHistoryResult } from '../services/historyApi';

const gradeColors = {
  A: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  B: 'bg-emerald-50 text-emerald-600 border-emerald-200',
  C: 'bg-amber-50 text-amber-700 border-amber-200',
  D: 'bg-orange-50 text-orange-700 border-orange-200',
  F: 'bg-red-50 text-red-700 border-red-200',
};

export default function HistoryPage({ onViewResult }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [loadingResultId, setLoadingResultId] = useState(null);
  const [error, setError] = useState('');

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listHistory();
      setHistory(data);
      setError('');
    } catch {
      setError('Could not load scan history.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      fetchHistory();
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setSearching(true);
        const results = await searchHistory(searchQuery);
        setHistory(results);
      } catch {
        setError('Search failed.');
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, fetchHistory]);

  const handleViewResult = async (item) => {
    try {
      setLoadingResultId(item.id);
      const result = await getHistoryResult(item.id);
      onViewResult(result);
    } catch {
      setError('Could not load scan result.');
    } finally {
      setLoadingResultId(null);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now - d;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-bg1 text-gray-800 pb-24">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <h1 className="text-2xl font-display font-extrabold text-gray-900 mb-1">Scan History</h1>
        <p className="text-sm text-gray-400 mb-6">Revisit your past product scans</p>

        {/* Search bar */}
        <div className="relative mb-6">
          <svg className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by product name, brand, or barcode..."
            aria-label="Search scan history"
            className="w-full pl-11 pr-4 py-3 bg-white border border-gray-200 rounded-2xl text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-brand transition-colors shadow-sm"
          />
          {searching && (
            <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
              <div className="w-4 h-4 rounded-full border-2 border-gray-300 border-t-brand animate-spin" />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2 flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => { setError(''); fetchHistory(); }} className="text-brandDeep font-medium hover:underline ml-2">Retry</button>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="glass-strong p-4 animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gray-100 rounded-xl" />
                  <div className="flex-1">
                    <div className="h-4 w-32 bg-gray-100 rounded mb-1.5" />
                    <div className="h-3 w-20 bg-gray-100 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && history.length === 0 && !searchQuery && (
          <div className="text-center py-16 animate-fade-in">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brandTint flex items-center justify-center">
              <svg className="w-8 h-8 text-brandDeep" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-gray-700 mb-1">No scans yet</h3>
            <p className="text-sm text-gray-400 max-w-xs mx-auto">
              Scan your first product to start building your history. All your scans will appear here.
            </p>
          </div>
        )}

        {/* No search results */}
        {!loading && history.length === 0 && searchQuery && (
          <div className="text-center py-12 animate-fade-in">
            <p className="text-gray-500 text-sm">No results for "{searchQuery}"</p>
          </div>
        )}

        {/* History list */}
        {!loading && history.length > 0 && (
          <div className="space-y-2 animate-fade-in">
            {history.map((item) => (
              <button
                key={item.id}
                onClick={() => handleViewResult(item)}
                disabled={loadingResultId === item.id}
                className="w-full glass-strong p-4 text-left hover:shadow-card-hover transition-all flex items-center gap-3 group"
              >
                {/* Score badge */}
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center font-bold text-sm border shrink-0 ${
                  item.grade ? (gradeColors[item.grade] || 'bg-gray-100 text-gray-500 border-gray-200') : 'bg-gray-100 text-gray-400 border-gray-200'
                }`}>
                  {item.grade || '?'}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-gray-800 truncate">
                      {item.product_name || 'Unknown Product'}
                    </span>
                    {item.scan_type === 'label' && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-brandTint text-brandDeep border border-brandLine shrink-0">
                        Label
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                    {item.brand && <span className="truncate">{item.brand}</span>}
                    {item.brand && item.barcode && <span>·</span>}
                    {item.barcode && <span className="font-mono">{item.barcode}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-[11px] text-gray-400">{formatDate(item.created_at)}</span>
                  {loadingResultId === item.id ? (
                    <div className="w-4 h-4 rounded-full border-2 border-gray-300 border-t-brand animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 text-gray-300 group-hover:text-brandDeep transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
