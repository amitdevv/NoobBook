/**
 * API Client Configuration
 * Educational Note: We create an axios instance with base configuration
 * to avoid repeating the base URL and headers in every request.
 * This is the single source of truth for API communication.
 */

import axios from 'axios';
import type { AxiosError } from 'axios';

// ==================== Default Axios Auth Interceptor ====================
// Some API files (settings, sources, chats, studio) use raw axios instead
// of the `api` instance below. This ensures ALL axios requests get the token.
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('noobbook_access_token');
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

// ==================== Request Interceptor ====================
// Attaches Bearer token to every request + debugging log
api.interceptors.request.use(
  (config) => {
    // Attach JWT token if available
    const token = localStorage.getItem('noobbook_access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    console.log('API Request:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('Request Error:', error);
    return Promise.reject(error);
  }
);

// ==================== Response Interceptor ====================
// Handles 401 errors by attempting token refresh before redirecting to login.
// Educational Note: When an access token expires mid-session, the first 401
// triggers a refresh attempt using the stored refresh token. If the refresh
// succeeds, the original request is retried transparently. A flag + queue
// prevent multiple simultaneous refresh attempts — subsequent 401s wait for
// the first refresh to complete, then retry with the new token.
let isRefreshing = false;
let pendingRequests: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processPendingRequests(token: string | null, error?: unknown) {
  pendingRequests.forEach(({ resolve, reject }) => {
    if (token) {
      resolve(token);
    } else {
      reject(error);
    }
  });
  pendingRequests = [];
}

api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url);
    return response;
  },
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config;
    const url = originalRequest?.url || '';

    // Only attempt refresh for 401s on non-auth endpoints
    if (status === 401 && !url.includes('/auth/') && originalRequest) {
      // If a refresh is already in progress, queue this request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: (token: string) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            },
            reject: (err: unknown) => reject(err),
          });
        });
      }

      isRefreshing = true;
      const refreshToken = localStorage.getItem('noobbook_refresh_token');

      if (refreshToken) {
        try {
          // Use raw axios to avoid triggering this interceptor again
          const refreshResponse = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            { refresh_token: refreshToken }
          );

          const { access_token, refresh_token: newRefreshToken } = refreshResponse.data;

          localStorage.setItem('noobbook_access_token', access_token);
          if (newRefreshToken) {
            localStorage.setItem('noobbook_refresh_token', newRefreshToken);
          }

          // Retry the original request with the new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          processPendingRequests(access_token);
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed — clear tokens and redirect to login
          processPendingRequests(null, refreshError);
          localStorage.removeItem('noobbook_access_token');
          localStorage.removeItem('noobbook_refresh_token');
          window.location.href = '/login';
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        // No refresh token available — redirect to login
        isRefreshing = false;
        localStorage.removeItem('noobbook_access_token');
        window.location.href = '/login';
      }
    }

    console.error('Response Error:', status, (error.response?.data as any));
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
  const token = localStorage.getItem('noobbook_access_token');
  const fullUrl = url.startsWith('http') ? url : `${API_HOST}${url}`;
  if (!token) return fullUrl;
  const separator = fullUrl.includes('?') ? '&' : '?';
  return `${fullUrl}${separator}token=${token}`;
}

export { API_BASE_URL };
