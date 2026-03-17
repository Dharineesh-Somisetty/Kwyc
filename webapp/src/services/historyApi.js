/**
 * History API – scan history CRUD + search.
 * Uses the shared axios instance which auto-attaches the JWT.
 */
import api from './api';

/** List scan history for the current user. */
export const listHistory = async (limit = 50, offset = 0) => {
  const res = await api.get('/api/history', { params: { limit, offset } });
  return res.data;
};

/** Search scan history by product name, brand, or barcode. */
export const searchHistory = async (query, limit = 20) => {
  const res = await api.get('/api/history/search', { params: { q: query, limit } });
  return res.data;
};

/** Get full analysis result for a history entry. */
export const getHistoryResult = async (historyId) => {
  const res = await api.get(`/api/history/${historyId}/result`);
  return res.data;
};
