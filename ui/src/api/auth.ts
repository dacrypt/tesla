/** Tesla account authentication and the dashboard session (API key → HttpOnly cookie). */
import { client } from './http';
import type {
  AuthLoginStart,
  AuthStatus,
  BrowserLoginResult,
  PortalScrapeResult,
  SessionStatus,
} from './types';

export const authApi = {
  // Tesla account
  getAuthLogin: () =>
    client().get<AuthLoginStart>('/api/auth/login').then(r => r.data),
  postAuthCallback: (code: string, state: string) =>
    client().post<{ ok: boolean; expires_in?: number }>('/api/auth/callback', { code, state }).then(r => r.data),
  postAuthTessie: (token: string) =>
    client().post<{ ok: boolean }>('/api/auth/tessie', { token }).then(r => r.data),
  // The server opens Tesla's own login page in a browser window on its machine;
  // credentials are typed there, never sent through this API.
  browserLogin: (mfa_code?: string) =>
    client().post<BrowserLoginResult>('/api/auth/browser-login', { mfa_code }, { timeout: 300000 }).then(r => r.data),
  portalScrape: (mfa_code?: string) =>
    client().post<PortalScrapeResult>('/api/auth/portal-scrape', { mfa_code }, { timeout: 420000 }).then(r => r.data),
  getAuthStatus: () =>
    client().get<AuthStatus>('/api/auth/status').then(r => r.data),

  // Session (API key → HttpOnly cookie)
  getSession: () => client().get<SessionStatus>('/api/session').then(r => r.data),
  login: (key: string) => client().post<SessionStatus>('/api/session', { key }).then(r => r.data),
  logout: () => client().delete<{ ok: boolean }>('/api/session').then(r => r.data),
};
