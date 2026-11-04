/**
 * Shared HTTP layer: API base URL, the single axios instance (with 429 retry
 * and 401 detection), and the rate-limit / auth-required event channels.
 *
 * Domain modules (`./vehicle`, `./charge`, ...) build on `client()`.
 */
import axios, { AxiosInstance, AxiosError } from 'axios';

export function getBaseUrl(): string {
  const envUrl = (import.meta.env.VITE_TESLA_API_URL || '').trim();
  if (envUrl) return envUrl;
  if (import.meta.env.DEV) return '';
  return localStorage.getItem('tesla_api_url') || '';
}

export function setBaseUrl(url: string): void {
  localStorage.setItem('tesla_api_url', url);
}

// ── Rate-limit toast event ────────────────────────────────────────────────────
// Components can subscribe to this to show a user-visible notification.

type RateLimitListener = (retryAfterSeconds: number) => void;
const rateLimitListeners = new Set<RateLimitListener>();

export function onRateLimit(fn: RateLimitListener): () => void {
  rateLimitListeners.add(fn);
  return () => rateLimitListeners.delete(fn);
}

function emitRateLimit(retryAfterSeconds: number): void {
  rateLimitListeners.forEach(fn => fn(retryAfterSeconds));
}

// ── Auth-required event ───────────────────────────────────────────────────────
// Fired when the server answers 401 so the app can show the sign-in screen.

type AuthListener = () => void;
const authListeners = new Set<AuthListener>();

export function onAuthRequired(fn: AuthListener): () => void {
  authListeners.add(fn);
  return () => authListeners.delete(fn);
}

function emitAuthRequired(): void {
  authListeners.forEach(fn => fn());
}

// ── Axios client with 429 retry ───────────────────────────────────────────────

const MAX_RETRIES = 2;

function createClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: getBaseUrl(),
    timeout: 15000,
    // Send the HttpOnly session cookie (also when the API lives on another origin).
    withCredentials: true,
    headers: { 'Content-Type': 'application/json' },
  });

  // Attach retry metadata and response interceptor once
  instance.interceptors.response.use(
    response => response,
    async (error: AxiosError) => {
      const config = error.config as typeof error.config & { _retryCount?: number };
      if (!config) return Promise.reject(error);

      const status = error.response?.status;
      if (status === 401 && !String(config.url || '').startsWith('/api/session')) {
        emitAuthRequired();
      }
      if (status !== 429) return Promise.reject(error);

      config._retryCount = (config._retryCount ?? 0) + 1;
      if (config._retryCount > MAX_RETRIES) return Promise.reject(error);

      const retryAfter = parseInt(
        (error.response?.headers as Record<string, string>)?.['retry-after'] || '5',
        10,
      );

      // Notify UI on first retry
      if (config._retryCount === 1) {
        emitRateLimit(retryAfter);
      }

      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      return instance(config);
    },
  );

  return instance;
}

// One shared instance (re-created only when the API base URL changes) instead
// of a new axios instance + interceptor on every call.
let _client: AxiosInstance | null = null;
let _clientBase: string | null = null;

export function client(): AxiosInstance {
  const base = getBaseUrl();
  if (!_client || _clientBase !== base) {
    _client = createClient();
    _clientBase = base;
  }
  return _client;
}
