/**
 * API Client Configuration
 * Educational Note: We create an axios instance with base configuration
 * to avoid repeating the base URL and headers in every request.
 * This is the single source of truth for API communication.
 */

import axios from 'axios';
import { getAccessToken } from '../auth/session';

// Base host URL (without /api/v1 path) - used for file URLs, static assets.
// When VITE_API_HOST is set to "" (Docker via nginx proxy), same-origin requests
// are used. When unset (local dev), falls back to localhost:5001.
const envHost = import.meta.env.VITE_API_HOST;
export const API_HOST = envHost !== undefined ? envHost : 'http://localhost:5001';

// Full API URL (with /api/v1 path) - used for API requests
const envApiUrl = import.meta.env.VITE_API_URL;
const API_BASE_URL = envApiUrl !== undefined ? envApiUrl : `${API_HOST}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

const attachAuthHeader = (config: any) => {
  const token = getAccessToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
};

// Add request interceptor for debugging (educational purposes)
api.interceptors.request.use(
  (config) => {
    const next = attachAuthHeader(config);
    console.log('API Request:', config.method?.toUpperCase(), config.url);
    return next;
  },
  (error) => {
    console.error('Request Error:', error);
    return Promise.reject(error);
  }
);

// Ensure global axios requests (non-api instance) include auth header too
axios.interceptors.request.use(attachAuthHeader);

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url);
    return response;
  },
  async (error) => {
    const status = error.response?.status;
    console.error('Response Error:', status, error.response?.data);
    return Promise.reject(error);
  }
);

/**
 * Build an authenticated URL for browser elements that can't send Authorization headers.
 *
 * Educational Note: Elements like <img>, <video>, <audio>, and <iframe> make their own
 * HTTP requests without axios interceptors. We append the JWT as a query parameter
 * so the backend auth middleware can validate it. The backend checks ?token= as a
 * fallback when no Authorization header is present.
 *
 * @param url - Absolute URL or path starting with /api/. If it's a full URL (starts with http),
 *              the token is appended directly. If it's a path, API_HOST is prepended first.
 */
export function getAuthUrl(url: string): string {
  const token = getAccessToken();
  const fullUrl = url.startsWith('http') ? url : `${API_HOST}${url}`;
  if (!token) return fullUrl;
  const separator = fullUrl.includes('?') ? '&' : '?';
  return `${fullUrl}${separator}token=${token}`;
}

export { API_BASE_URL };
