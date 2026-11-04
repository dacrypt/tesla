/** Session and Tesla account authentication. */

export interface SessionStatus {
  auth_required: boolean;
  authenticated: boolean;
  role: 'control' | 'read' | null;
}

/** /api/auth/status */
export interface AuthStatus {
  authenticated: boolean;
  backend: string;
  has_fleet: boolean;
  has_order: boolean;
  has_tessie: boolean;
  has_portal_session?: boolean;
}

/** /api/auth/login — start of the OAuth2 PKCE flow. */
export interface AuthLoginStart {
  auth_url: string;
  state: string;
}

/** /api/auth/browser-login — `ok: false` with `mfa_required` asks for an MFA code. */
export interface BrowserLoginResult {
  ok: boolean;
  mfa_required?: boolean;
  error?: string;
  has_order?: boolean;
  has_fleet?: boolean;
  has_portal?: boolean;
}

/** /api/auth/portal-scrape */
export interface PortalScrapeResult {
  ok: boolean;
  mfa_required?: boolean;
  error?: string;
  [key: string]: unknown;
}
