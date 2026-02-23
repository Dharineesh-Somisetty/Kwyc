/**
 * LabelLens API client.
 * Base URL is configured via VITE_API_BASE_URL (never hardcode secrets here).
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

/**
 * Scan a barcode → full analysis result.
 */
export const scanBarcode = async (barcode, userProfile = {}) => {
    const res = await api.post('/api/scan/barcode', {
        barcode,
        user_profile: userProfile,
    });
    return res.data;
};

/**
 * Upload a label image → full analysis result.
 * @param {string} [barcode] - Optional barcode to associate with this label
 *   so the backend can cache the extraction for future barcode-only scans.
 */
export const scanLabel = async (imageFile, userProfile = {}, barcode = '') => {
    const form = new FormData();
    form.append('image', imageFile);
    form.append('user_profile', JSON.stringify(userProfile));
    if (barcode) form.append('barcode', barcode);
    const res = await api.post('/api/scan/label', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
};

/**
 * Product-locked chat.
 */
export const chat = async (sessionId, message, chatHistory = []) => {
    const res = await api.post('/api/chat', {
        session_id: sessionId,
        message,
        chat_history: chatHistory,
    });
    return res.data;
};

export default api;

