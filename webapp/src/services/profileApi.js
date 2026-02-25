/**
 * Profile API – CRUD for household profiles.
 * Uses the shared axios instance which auto-attaches the JWT.
 */
import api from './api';

/** List all profiles for the current user. */
export const listProfiles = async () => {
  const res = await api.get('/api/profiles');
  return res.data;
};

/** Create a new profile. */
export const createProfile = async (data) => {
  const res = await api.post('/api/profiles', data);
  return res.data;
};

/** Update an existing profile. */
export const updateProfile = async (profileId, data) => {
  const res = await api.patch(`/api/profiles/${profileId}`, data);
  return res.data;
};

/** Delete a profile. */
export const deleteProfile = async (profileId) => {
  await api.delete(`/api/profiles/${profileId}`);
};

/** Set a profile as the default. */
export const setDefaultProfile = async (profileId) => {
  const res = await api.post(`/api/profiles/${profileId}/default`);
  return res.data;
};
