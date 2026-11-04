import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

const getSession = vi.fn();
const login = vi.fn();
let authListener: (() => void) | null = null;

vi.mock('../api/client', () => ({
  api: {
    getSession: (...a: unknown[]) => getSession(...a),
    login: (...a: unknown[]) => login(...a),
  },
  onAuthRequired: (fn: () => void) => {
    authListener = fn;
    return () => { authListener = null; };
  },
}));

import AuthGate from './AuthGate';

describe('AuthGate', () => {
  beforeEach(() => {
    getSession.mockReset();
    login.mockReset();
    authListener = null;
  });

  it('renders the app when no auth is required', async () => {
    getSession.mockResolvedValue({ auth_required: false, authenticated: true, role: 'control' });
    render(<AuthGate><div>dashboard</div></AuthGate>);
    expect(await screen.findByText('dashboard')).toBeDefined();
  });

  it('shows the sign-in form when not authenticated', async () => {
    getSession.mockResolvedValue({ auth_required: true, authenticated: false, role: null });
    render(<AuthGate><div>dashboard</div></AuthGate>);
    expect(await screen.findByLabelText('API key')).toBeDefined();
    expect(screen.queryByText('dashboard')).toBeNull();
  });

  it('reports an invalid key', async () => {
    getSession.mockResolvedValue({ auth_required: true, authenticated: false, role: null });
    login.mockRejectedValue({ response: { status: 401 } });
    render(<AuthGate><div>dashboard</div></AuthGate>);
    fireEvent.change(await screen.findByLabelText('API key'), { target: { value: 'bad' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Invalid API key.');
    expect(login).toHaveBeenCalledWith('bad');
  });

  it('falls back to the app when the server has no session endpoint', async () => {
    getSession.mockRejectedValue(new Error('404'));
    render(<AuthGate><div>dashboard</div></AuthGate>);
    expect(await screen.findByText('dashboard')).toBeDefined();
  });

  it('re-opens the sign-in screen on a later 401', async () => {
    getSession.mockResolvedValue({ auth_required: true, authenticated: true, role: 'control' });
    render(<AuthGate><div>dashboard</div></AuthGate>);
    await screen.findByText('dashboard');
    authListener?.();
    await waitFor(() => expect(screen.queryByLabelText('API key')).not.toBeNull());
  });
});
