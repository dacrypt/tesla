import React, { useState } from 'react';
import { api, errorDetailOf, VehicleInvitation } from '../../api/client';
import type { Notify } from './types';

interface Props {
  invitations: VehicleInvitation[];
  onInvitationsChange: React.Dispatch<React.SetStateAction<VehicleInvitation[]>>;
  notify: Notify;
}

/** Driver invitations: send and revoke. */
const VehicleSharingCard: React.FC<Props> = ({ invitations, onInvitationsChange: setInvitations, notify }) => {
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [sharingLoading, setSharingLoading] = useState(false);

  const sendInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviteLoading(true);
    try {
      await api.inviteDriver(inviteEmail.trim());
      setInviteEmail('');
      const fresh = await api.getInvitations();
      setInvitations(Array.isArray(fresh) ? fresh : []);
      notify(`Invitation sent to ${inviteEmail}`, 'success');
    } catch (e: unknown) {
      notify(errorDetailOf(e) || 'Failed to send invitation', 'danger');
    } finally {
      setInviteLoading(false);
    }
  };

  const revokeInvite = async (id: string) => {
    setSharingLoading(true);
    try {
      await api.revokeInvitation(id);
      setInvitations(prev => prev.filter(i => i.id !== id));
      notify('Invitation revoked', 'success');
    } catch (e: unknown) {
      notify(errorDetailOf(e) || 'Failed to revoke invitation', 'danger');
    } finally {
      setSharingLoading(false);
    }
  };

  return (
    <div className="tesla-card">
      <p className="section-title">Vehicle Sharing</p>
      <p style={{ color: '#999', fontSize: 13, margin: '0 0 12px' }}>
        Invite drivers to access your vehicle.
      </p>

      {/* Invite form */}
      <div className="flex-center gap-sm" style={{ marginBottom: 12 }}>
        <input
          type="email"
          value={inviteEmail}
          onChange={e => setInviteEmail(e.target.value)}
          placeholder="Driver email"
          className="tesla-input"
          style={{ flex: 1, fontSize: 13 }}
          disabled={inviteLoading}
          onKeyDown={e => e.key === 'Enter' && sendInvite()}
        />
        <button
          onClick={sendInvite}
          disabled={inviteLoading || !inviteEmail.trim()}
          className="tesla-btn"
          style={{ fontSize: 13, padding: '8px 14px', whiteSpace: 'nowrap' }}
        >
          {inviteLoading ? '...' : 'Invite'}
        </button>
      </div>

      {/* Invitations list */}
      {invitations.length === 0 ? (
        <div style={{ color: '#666', fontSize: 13, textAlign: 'center', padding: '8px 0' }}>
          No active invitations
        </div>
      ) : (
        <div className="flex-col gap-xs">
          {invitations.map(inv => (
            <div key={inv.id} className="flex-between" style={{
              padding: '8px 10px', borderRadius: 8,
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div className="flex-col" style={{ gap: 2 }}>
                <span style={{ fontSize: 13, color: '#f5f5f7' }}>
                  {inv.name || inv.email || inv.id}
                </span>
                {inv.email && inv.name && (
                  <span style={{ fontSize: 11, color: '#86888f' }}>{inv.email}</span>
                )}
                {inv.status && (
                  <span style={{ fontSize: 10, color: inv.status === 'accepted' ? '#0BE881' : '#86888f' }}>
                    {inv.status}
                  </span>
                )}
              </div>
              <button
                onClick={() => revokeInvite(inv.id)}
                disabled={sharingLoading}
                className="tesla-btn secondary"
                style={{ fontSize: 12, padding: '4px 10px', color: '#FF6B6B' }}
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default VehicleSharingCard;
