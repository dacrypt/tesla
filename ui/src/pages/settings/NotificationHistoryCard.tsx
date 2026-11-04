import React, { useEffect, useState } from 'react';
import { api, NotificationEntry } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import { BellIcon } from './icons';

function timeAgoLabel(isoTimestamp: string): string {
  const diff = Date.now() - new Date(isoTimestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Recently sent notifications (JSONL log on the server). */
const NotificationHistoryCard: React.FC = () => {
  const [history, setHistory] = useState<NotificationEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await api.getNotificationHistory(20);
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => { loadHistory(); }, []);

  const clearHistory = async () => {
    // Clear from localStorage is not possible; just refresh to reflect server state
    // History is JSONL-only — we truncate by reloading (no delete endpoint yet)
    setHistory([]);
  };

  return (
    <div className="tesla-card">
      <div className="flex-between" style={{ marginBottom: 14 }}>
        <div className="flex-center gap-sm">
          <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
            <BellIcon />
          </div>
          <div>
            <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Notification History</div>
            <div style={{ color: '#86888f', fontSize: 12 }}>Recent sent notifications</div>
          </div>
        </div>
        {history.length > 0 && (
          <button
            onClick={clearHistory}
            className="tesla-btn secondary"
            style={{ fontSize: 11, padding: '4px 10px', color: '#FF6B6B' }}
          >
            Clear
          </button>
        )}
      </div>

      {historyLoading ? (
        <div className="flex-center" style={{ padding: '12px 0' }}><Spinner /></div>
      ) : history.length === 0 ? (
        <div style={{ color: '#86888f', fontSize: 13, textAlign: 'center', padding: '8px 0' }}>
          No notifications sent yet
        </div>
      ) : (
        <div className="flex-col gap-xs">
          {history.map((entry, i) => (
            <div key={i} className="flex-col" style={{
              background: 'rgba(255,255,255,0.03)',
              border: `1px solid ${entry.success ? 'rgba(16,185,129,0.2)' : 'rgba(255,107,107,0.2)'}`,
              borderRadius: 8, padding: '8px 10px', gap: 2,
            }}>
              <div className="flex-between">
                <span style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>{entry.title}</span>
                <div className="flex-center gap-xs">
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                    background: entry.success ? 'rgba(16,185,129,0.15)' : 'rgba(255,107,107,0.15)',
                    color: entry.success ? '#10b981' : '#FF6B6B',
                  }}>
                    {entry.success ? 'OK' : 'FAIL'}
                  </span>
                  <span style={{ color: '#86888f', fontSize: 11 }}>{timeAgoLabel(entry.timestamp)}</span>
                </div>
              </div>
              <div style={{ color: '#86888f', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {entry.message}
              </div>
              <div style={{ color: '#555', fontSize: 11 }}>via {entry.channel}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default NotificationHistoryCard;
