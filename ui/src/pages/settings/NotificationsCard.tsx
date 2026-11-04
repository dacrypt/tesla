import React, { useState } from 'react';
import { IonRange } from '@ionic/react';
import { api, describeError } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import { BellIcon, SendIcon, TrashIcon } from './icons';
import type { Notify } from './types';

interface Props {
  channels: string[];
  onChannelsChange: (channels: string[]) => void;
  notify: Notify;
}

/** Apprise channels (add / test / remove) and locally persisted event toggles. */
const NotificationsCard: React.FC<Props> = ({ channels: notifyChannels, onChannelsChange, notify }) => {
  const [newChannel, setNewChannel] = useState('');
  const [notifyLoading, setNotifyLoading] = useState(false);
  const [testingChannel, setTestingChannel] = useState<number | null>(null);
  // Event toggles (persisted locally — map to automation engine rules)
  const [evtChargeComplete, setEvtChargeComplete] = useState(() => localStorage.getItem('evt_charge_complete') === 'true');
  const [evtLowBattery, setEvtLowBattery] = useState(() => localStorage.getItem('evt_low_battery') === 'true');
  const [evtLowBatteryThreshold, setEvtLowBatteryThreshold] = useState(() => Number(localStorage.getItem('evt_low_battery_threshold') || '20'));
  const [evtSentry, setEvtSentry] = useState(() => localStorage.getItem('evt_sentry') === 'true');

  const addNotifyChannel = async () => {
    if (!newChannel.trim()) return;
    setNotifyLoading(true);
    try {
      await api.addNotifyChannel(newChannel.trim());
      setNewChannel('');
      const data = await api.getNotifyChannels();
      onChannelsChange(data.channels || []);
      notify('Channel added', 'success');
    } catch (e: unknown) {
      notify('Failed to add channel: ' + describeError(e), 'danger');
    } finally {
      setNotifyLoading(false);
    }
  };

  const removeNotifyChannel = async (index: number) => {
    try {
      await api.removeNotifyChannel(index);
      const data = await api.getNotifyChannels();
      onChannelsChange(data.channels || []);
      notify('Channel removed', 'success');
    } catch (e: unknown) {
      notify('Failed to remove channel: ' + describeError(e), 'danger');
    }
  };

  const testNotifyChannel = async (index: number) => {
    setTestingChannel(index);
    try {
      await api.sendNotifyTest();
      notify('Test notification sent', 'success');
    } catch (e: unknown) {
      notify('Test failed: ' + describeError(e), 'danger');
    } finally {
      setTestingChannel(null);
    }
  };

  const setEvtToggle = (key: string, value: boolean, setter: (v: boolean) => void) => {
    setter(value);
    localStorage.setItem(key, String(value));
  };

  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
          <BellIcon />
        </div>
        <div>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Notifications</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>Apprise notification channels</div>
        </div>
      </div>

      {/* Channel list */}
      {notifyChannels.length > 0 ? (
        <div style={{ marginBottom: 14 }}>
          {notifyChannels.map((ch, i) => (
            <div key={i} className="flex-center gap-sm" style={{
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 8, padding: '8px 10px', marginBottom: 6,
            }}>
              <span style={{ flex: 1, color: '#ffffff', fontSize: 12, fontFamily: 'SF Mono, Menlo, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ch}
              </span>
              <button
                onClick={() => testNotifyChannel(i)}
                disabled={testingChannel === i}
                className="tesla-btn blue"
                style={{ fontSize: 11, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                {testingChannel === i ? <Spinner /> : <SendIcon />}
                Test
              </button>
              <button
                onClick={() => removeNotifyChannel(i)}
                className="tesla-btn secondary"
                style={{ fontSize: 11, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4, color: '#FF6B6B' }}
              >
                <TrashIcon />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ color: '#86888f', fontSize: 13, marginBottom: 14, textAlign: 'center', padding: '8px 0' }}>
          No channels configured
        </div>
      )}

      {/* Add channel form */}
      <div style={{ marginBottom: 8 }}>
        <input
          type="text"
          value={newChannel}
          onChange={(e) => setNewChannel(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addNotifyChannel()}
          placeholder="tgram://BOT_TOKEN/CHAT_ID"
          className="tesla-input mono"
          style={{ marginBottom: 6, fontSize: 12 }}
        />
        <div style={{ color: '#86888f', fontSize: 11, marginBottom: 8, lineHeight: 1.6 }}>
          Formats: <code style={{ color: '#10b981' }}>tgram://BOT/CHAT</code> · <code style={{ color: '#10b981' }}>discord://id/token</code> · <code style={{ color: '#10b981' }}>slack://a/b/c</code> · <code style={{ color: '#10b981' }}>mailto://user:pass@gmail.com</code>
        </div>
        <button
          onClick={addNotifyChannel}
          disabled={notifyLoading || !newChannel.trim()}
          className="tesla-btn"
          style={{ width: '100%', fontSize: 13 }}
        >
          {notifyLoading ? <Spinner /> : '+ Add Channel'}
        </button>
      </div>

      {/* Event toggles */}
      <div style={{ marginTop: 18, borderTop: '1px solid rgba(255,255,255,0.07)', paddingTop: 14 }}>
        <div style={{ color: '#86888f', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>Event Triggers</div>

        {/* Charge complete toggle */}
        <div className="stat-row" style={{ marginBottom: 12 }}>
          <div>
            <div style={{ color: '#ffffff', fontSize: 13 }}>Charge complete</div>
            <div style={{ color: '#86888f', fontSize: 11 }}>Notify when charging finishes</div>
          </div>
          <button
            onClick={() => setEvtToggle('evt_charge_complete', !evtChargeComplete, setEvtChargeComplete)}
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
              background: evtChargeComplete ? '#10b981' : 'rgba(255,255,255,0.12)',
              transition: 'background 0.2s', position: 'relative', flexShrink: 0,
            }}
          >
            <div style={{
              position: 'absolute', top: 2, left: evtChargeComplete ? 22 : 2,
              width: 20, height: 20, borderRadius: '50%', background: '#fff',
              transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
            }} />
          </button>
        </div>

        {/* Low battery toggle */}
        <div style={{ marginBottom: 6 }}>
          <div className="stat-row" style={{ marginBottom: evtLowBattery ? 8 : 0 }}>
            <div>
              <div style={{ color: '#ffffff', fontSize: 13 }}>Low battery</div>
              <div style={{ color: '#86888f', fontSize: 11 }}>Notify below threshold</div>
            </div>
            <button
              onClick={() => setEvtToggle('evt_low_battery', !evtLowBattery, setEvtLowBattery)}
              style={{
                width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
                background: evtLowBattery ? '#10b981' : 'rgba(255,255,255,0.12)',
                transition: 'background 0.2s', position: 'relative', flexShrink: 0,
              }}
            >
              <div style={{
                position: 'absolute', top: 2, left: evtLowBattery ? 22 : 2,
                width: 20, height: 20, borderRadius: '50%', background: '#fff',
                transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
              }} />
            </button>
          </div>
          {evtLowBattery && (
            <div style={{ paddingLeft: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ color: '#86888f', fontSize: 11 }}>Threshold</span>
                <span style={{ color: '#10b981', fontWeight: 600, fontSize: 13 }}>{evtLowBatteryThreshold}%</span>
              </div>
              <IonRange
                min={5} max={50} step={5} value={evtLowBatteryThreshold}
                onIonChange={(e) => {
                  const v = e.detail.value as number;
                  setEvtLowBatteryThreshold(v);
                  localStorage.setItem('evt_low_battery_threshold', String(v));
                }}
              />
            </div>
          )}
        </div>

        {/* Sentry event toggle */}
        <div className="stat-row">
          <div>
            <div style={{ color: '#ffffff', fontSize: 13 }}>Sentry event</div>
            <div style={{ color: '#86888f', fontSize: 11 }}>Notify on sentry alerts</div>
          </div>
          <button
            onClick={() => setEvtToggle('evt_sentry', !evtSentry, setEvtSentry)}
            style={{
              width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
              background: evtSentry ? '#10b981' : 'rgba(255,255,255,0.12)',
              transition: 'background 0.2s', position: 'relative', flexShrink: 0,
            }}
          >
            <div style={{
              position: 'absolute', top: 2, left: evtSentry ? 22 : 2,
              width: 20, height: 20, borderRadius: '50%', background: '#fff',
              transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
            }} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default NotificationsCard;
