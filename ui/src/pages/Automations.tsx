import React, { useState, useEffect, useCallback } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonToast,
} from '@ionic/react';
import {
  api,
  AutomationRule,
  AutomationTrigger,
  AutomationAction,
  AutomationsStatus,
} from '../api/client';

// ---- Icons ----
const BotIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.38-1 1.73V7h3a3 3 0 013 3v1a2 2 0 012 2v2a2 2 0 01-2 2v1a3 3 0 01-3 3H8a3 3 0 01-3-3v-1a2 2 0 01-2-2v-2a2 2 0 012-2v-1a3 3 0 013-3h3V5.73A2 2 0 0112 2zm-4 9a1 1 0 100 2 1 1 0 000-2zm8 0a1 1 0 100 2 1 1 0 000-2zm-4 3.5c-1.5 0-2.5.67-2.5.67v.83s1 .5 2.5.5 2.5-.5 2.5-.5v-.83S13.5 14.5 12 14.5z"/>
  </svg>
);
const PlusIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z"/>
  </svg>
);
const TrashIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
  </svg>
);
const PlayIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z"/>
  </svg>
);
const CloseIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
  </svg>
);

function Spin() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function formatLastFired(ts?: string | null): string {
  if (!ts) return 'Never';
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

function triggerLabel(trigger: AutomationTrigger): string {
  switch (trigger.type) {
    case 'battery_below': return `Battery < ${trigger.threshold ?? '?'}%`;
    case 'battery_above': return `Battery > ${trigger.threshold ?? '?'}%`;
    case 'charging_complete': return 'Charging complete';
    case 'charging_started': return 'Charging started';
    case 'sentry_event': return 'Sentry event';
    case 'location_enter': return 'Location enter';
    case 'location_exit': return 'Location exit';
    case 'state_change': return `State: ${trigger.field ?? '?'} changes`;
    case 'time_of_day': return `At ${trigger.time ?? '?'}`;
    default: return trigger.type;
  }
}

function actionLabel(action: AutomationAction): string {
  switch (action.type) {
    case 'notify': return `Notify: ${(action.message || '').slice(0, 30) || '(no message)'}`;
    case 'command':
    case 'exec': return `Exec: ${(action.command || '').slice(0, 30) || '(no cmd)'}`;
    case 'webhook': return `Webhook: ${(action.webhook_url || '').slice(0, 30) || '(no url)'}`;
    default: return action.type;
  }
}

// ---- Default form state ----
const defaultTrigger = (): AutomationTrigger => ({ type: 'battery_below', threshold: 20 });
const defaultAction = (): AutomationAction => ({ type: 'notify', message: 'Battery low: {battery_level}%' });

const TRIGGER_TYPES = [
  'battery_below',
  'battery_above',
  'charging_complete',
  'charging_started',
  'sentry_event',
  'location_enter',
  'location_exit',
  'state_change',
  'time_of_day',
];

const ACTION_TYPES = ['notify', 'command', 'webhook'];

// ---- Add Rule Modal ----
interface AddRuleModalProps {
  onClose: () => void;
  onCreated: () => void;
  setToast: (t: { message: string; color: string }) => void;
}

const AddRuleModal: React.FC<AddRuleModalProps> = ({ onClose, onCreated, setToast }) => {
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState<AutomationTrigger>(defaultTrigger());
  const [action, setAction] = useState<AutomationAction>(defaultAction());
  const [submitting, setSubmitting] = useState(false);

  const handleTriggerTypeChange = (type: string) => {
    setTrigger({ type });
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setToast({ message: 'Rule name is required', color: 'warning' });
      return;
    }
    setSubmitting(true);
    try {
      await api.createAutomation({ name: name.trim(), trigger, action, enabled: true });
      setToast({ message: `Rule "${name.trim()}" created`, color: 'success' });
      onCreated();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create rule';
      setToast({ message: msg, color: 'danger' });
    } finally {
      setSubmitting(false);
    }
  };

  const inp: React.CSSProperties = {
    background: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: 8,
    color: '#e5e5e5',
    padding: '8px 10px',
    width: '100%',
    fontSize: 14,
    boxSizing: 'border-box',
  };

  const needsThreshold = trigger.type === 'battery_below' || trigger.type === 'battery_above';
  const needsLocation = trigger.type === 'location_enter' || trigger.type === 'location_exit';
  const needsField = trigger.type === 'state_change';
  const needsTime = trigger.type === 'time_of_day';

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{ background: '#111', border: '1px solid #333', borderRadius: 12, padding: 24, width: '90%', maxWidth: 460 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ color: '#e5e5e5', fontSize: 16, fontWeight: 600 }}>New Automation Rule</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer' }}><CloseIcon /></button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Name */}
          <div>
            <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Rule Name</label>
            <input style={inp} placeholder="e.g. Low Battery Alert" value={name} onChange={e => setName(e.target.value)} />
          </div>

          {/* Trigger type */}
          <div>
            <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Trigger Type</label>
            <select style={inp} value={trigger.type} onChange={e => handleTriggerTypeChange(e.target.value)}>
              {TRIGGER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Threshold */}
          {needsThreshold && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Threshold (%)</label>
              <input
                style={inp} type="number" min={1} max={100}
                value={trigger.threshold ?? ''}
                onChange={e => setTrigger({ ...trigger, threshold: Number(e.target.value) })}
              />
            </div>
          )}

          {/* Location */}
          {needsLocation && (
            <>
              <div>
                <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Latitude</label>
                <input style={inp} type="number" step="0.0001" placeholder="e.g. 4.7110"
                  value={trigger.latitude ?? ''}
                  onChange={e => setTrigger({ ...trigger, latitude: Number(e.target.value) })} />
              </div>
              <div>
                <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Longitude</label>
                <input style={inp} type="number" step="0.0001" placeholder="e.g. -74.0721"
                  value={trigger.longitude ?? ''}
                  onChange={e => setTrigger({ ...trigger, longitude: Number(e.target.value) })} />
              </div>
              <div>
                <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Radius (km)</label>
                <input style={inp} type="number" step="0.1" min={0.1}
                  value={trigger.radius_km ?? 0.5}
                  onChange={e => setTrigger({ ...trigger, radius_km: Number(e.target.value) })} />
              </div>
            </>
          )}

          {/* State change field */}
          {needsField && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Field (e.g. charge_state.charging_state)</label>
              <input style={inp} placeholder="charge_state.charging_state"
                value={trigger.field ?? ''}
                onChange={e => setTrigger({ ...trigger, field: e.target.value })} />
            </div>
          )}

          {/* Time */}
          {needsTime && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Time (HH:MM)</label>
              <input style={inp} type="time"
                value={trigger.time ?? ''}
                onChange={e => setTrigger({ ...trigger, time: e.target.value })} />
            </div>
          )}

          {/* Action type */}
          <div>
            <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Action Type</label>
            <select style={inp} value={action.type} onChange={e => setAction({ ...action, type: e.target.value })}>
              {ACTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Action message / command / url */}
          {action.type === 'notify' && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Message</label>
              <input style={inp} placeholder="Battery low: {battery_level}%"
                value={action.message ?? ''}
                onChange={e => setAction({ ...action, message: e.target.value })} />
            </div>
          )}
          {(action.type === 'command' || action.type === 'exec') && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Command</label>
              <input style={inp} placeholder="echo Battery: {battery_level}"
                value={action.command ?? ''}
                onChange={e => setAction({ ...action, command: e.target.value })} />
            </div>
          )}
          {action.type === 'webhook' && (
            <div>
              <label style={{ color: '#888', fontSize: 12, display: 'block', marginBottom: 4 }}>Webhook URL</label>
              <input style={inp} placeholder="https://hooks.example.com/..."
                value={action.webhook_url ?? ''}
                onChange={e => setAction({ ...action, webhook_url: e.target.value })} />
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
          <button
            onClick={onClose}
            style={{ flex: 1, padding: '10px 0', background: '#222', border: '1px solid #333', borderRadius: 8, color: '#888', cursor: 'pointer', fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{ flex: 2, padding: '10px 0', background: '#05C46B', border: 'none', borderRadius: 8, color: '#000', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}
          >
            {submitting ? 'Creating...' : 'Create Rule'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ---- Main Page ----
const Automations: React.FC = () => {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [status, setStatus] = useState<AutomationsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [toast, setToastState] = useState<{ message: string; color: string } | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const setToast = (t: { message: string; color: string }) => setToastState(t);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [r, s] = await Promise.allSettled([api.getAutomations(), api.getAutomationsStatus()]);
      if (r.status === 'fulfilled') setRules(r.value);
      if (s.status === 'fulfilled') setStatus(s.value);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleToggle = async (rule: AutomationRule) => {
    setToggling(rule.name);
    try {
      if (rule.enabled) {
        await api.disableAutomation(rule.name);
      } else {
        await api.enableAutomation(rule.name);
      }
      await fetchAll();
    } catch {
      setToast({ message: 'Failed to update rule', color: 'danger' });
    } finally {
      setToggling(null);
    }
  };

  const handleDelete = async (name: string) => {
    setDeleting(name);
    try {
      await api.deleteAutomation(name);
      setToast({ message: `Rule "${name}" deleted`, color: 'success' });
      await fetchAll();
    } catch {
      setToast({ message: 'Failed to delete rule', color: 'danger' });
    } finally {
      setDeleting(null);
    }
  };

  const handleQuickSetup = async () => {
    const defaults: Array<{ name: string; trigger: AutomationTrigger; action: AutomationAction }> = [
      {
        name: 'Low Battery Alert',
        trigger: { type: 'battery_below', threshold: 20 },
        action: { type: 'notify', message: 'Battery low: {battery_level}%' },
      },
      {
        name: 'Charging Complete',
        trigger: { type: 'charging_complete' },
        action: { type: 'notify', message: 'Charging complete — {battery_level}%' },
      },
      {
        name: 'Sentry Event',
        trigger: { type: 'sentry_event' },
        action: { type: 'notify', message: 'Sentry alert detected' },
      },
    ];
    let created = 0;
    for (const rule of defaults) {
      try {
        await api.createAutomation({ ...rule, enabled: true });
        created++;
      } catch {
        // skip duplicates
      }
    }
    setToast({ message: `${created} default rule${created !== 1 ? 's' : ''} created`, color: 'success' });
    await fetchAll();
  };

  const handleTest = async (name: string) => {
    setTesting(name);
    try {
      const result = await api.testAutomation(name);
      setToast({
        message: result.fired
          ? `Fired: ${result.message || 'Rule would fire'}`
          : 'Rule did not fire with synthetic data',
        color: result.fired ? 'success' : 'warning',
      });
    } catch {
      setToast({ message: 'Test failed', color: 'danger' });
    } finally {
      setTesting(null);
    }
  };

  const card: React.CSSProperties = {
    background: '#111',
    border: '1px solid #222',
    borderRadius: 12,
    padding: '14px 16px',
    marginBottom: 10,
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar style={{ '--background': '#0a0a0a', '--color': '#e5e5e5' } as React.CSSProperties}>
          <IonTitle style={{ fontSize: 18, fontWeight: 700 }}>Automations</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent style={{ '--background': '#0a0a0a' } as React.CSSProperties}>
        <div style={{ padding: '12px 16px', maxWidth: 700, margin: '0 auto' }}>

          {/* Status bar */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
            {[
              { label: 'Total', value: status?.total ?? '--', color: '#e5e5e5' },
              { label: 'Enabled', value: status?.enabled ?? '--', color: '#05C46B' },
              { label: 'Disabled', value: status?.disabled ?? '--', color: '#888' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ ...card, flex: 1, textAlign: 'center', marginBottom: 0 }}>
                <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
                <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>{label}</div>
              </div>
            ))}
          </div>

          {/* Add rule button */}
          <button
            onClick={() => setShowAdd(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: '#05C46B', border: 'none', borderRadius: 10,
              color: '#000', cursor: 'pointer', fontSize: 14, fontWeight: 600,
              padding: '10px 18px', marginBottom: 16,
            }}
          >
            <PlusIcon /> Add Rule
          </button>

          {/* Rules list */}
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spin /></div>
          ) : rules.length === 0 ? (
            <div style={{ ...card, textAlign: 'center', color: '#555', padding: 40 }}>
              <BotIcon />
              <div style={{ marginTop: 12, fontSize: 14 }}>No automation rules yet.</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Tap "Add Rule" to create one, or use Quick Setup.</div>
              <button
                onClick={handleQuickSetup}
                style={{
                  marginTop: 16, padding: '10px 20px',
                  background: 'rgba(5,196,107,0.12)', border: '1px solid rgba(5,196,107,0.3)',
                  borderRadius: 10, color: '#05C46B', cursor: 'pointer',
                  fontSize: 13, fontWeight: 600,
                }}
              >
                ⚡ Quick Setup (3 default rules)
              </button>
            </div>
          ) : (
            rules.map(rule => (
              <div key={rule.name} style={card}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                  {/* Left: name + labels */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ color: '#e5e5e5', fontSize: 15, fontWeight: 600 }}>{rule.name}</span>
                      <span style={{
                        fontSize: 10, padding: '2px 7px', borderRadius: 10, fontWeight: 600,
                        background: rule.enabled ? 'rgba(5,196,107,0.15)' : 'rgba(136,136,136,0.15)',
                        color: rule.enabled ? '#05C46B' : '#888',
                        border: `1px solid ${rule.enabled ? 'rgba(5,196,107,0.3)' : 'rgba(136,136,136,0.3)'}`,
                      }}>
                        {rule.enabled ? 'ENABLED' : 'DISABLED'}
                      </span>
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      <span style={{ fontSize: 11, color: '#0FBCF9', background: 'rgba(15,188,249,0.1)', padding: '2px 8px', borderRadius: 6 }}>
                        {triggerLabel(rule.trigger)}
                      </span>
                      <span style={{ fontSize: 11, color: '#F99716', background: 'rgba(249,151,22,0.1)', padding: '2px 8px', borderRadius: 6 }}>
                        {actionLabel(rule.action)}
                      </span>
                      {rule.conditions && rule.conditions.length > 0 && (
                        <span style={{ fontSize: 11, color: '#888', background: '#1a1a1a', padding: '2px 8px', borderRadius: 6 }}>
                          {rule.conditions.length} condition{rule.conditions.length !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                    <div style={{ marginTop: 6, fontSize: 11, color: '#555' }}>
                      Last fired: {formatLastFired(rule.last_fired)}
                      {rule.cooldown_minutes ? ` · Cooldown: ${rule.cooldown_minutes}m` : ''}
                    </div>
                  </div>

                  {/* Right: toggle + actions */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8, flexShrink: 0 }}>
                    {/* Toggle switch */}
                    <button
                      onClick={() => handleToggle(rule)}
                      disabled={toggling === rule.name}
                      style={{
                        width: 42, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
                        background: rule.enabled ? '#05C46B' : '#333',
                        position: 'relative', transition: 'background 0.2s',
                      }}
                    >
                      <span style={{
                        position: 'absolute', top: 3,
                        left: rule.enabled ? 22 : 3,
                        width: 16, height: 16, borderRadius: '50%',
                        background: '#fff', transition: 'left 0.2s',
                        display: 'block',
                      }} />
                    </button>
                    {/* Action buttons */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={() => handleTest(rule.name)}
                        disabled={testing === rule.name}
                        title="Dry-run test"
                        style={{
                          background: '#1a1a1a', border: '1px solid #333', borderRadius: 6,
                          color: '#0FBCF9', cursor: 'pointer', padding: '4px 8px',
                          display: 'flex', alignItems: 'center', gap: 4, fontSize: 11,
                        }}
                      >
                        {testing === rule.name ? <Spin /> : <PlayIcon />}
                        Test
                      </button>
                      <button
                        onClick={() => handleDelete(rule.name)}
                        disabled={deleting === rule.name}
                        title="Delete rule"
                        style={{
                          background: '#1a1a1a', border: '1px solid #333', borderRadius: 6,
                          color: '#FF6B6B', cursor: 'pointer', padding: '4px 8px',
                          display: 'flex', alignItems: 'center', gap: 4, fontSize: 11,
                        }}
                      >
                        {deleting === rule.name ? <Spin /> : <TrashIcon />}
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {showAdd && (
          <AddRuleModal
            onClose={() => setShowAdd(false)}
            onCreated={() => { setShowAdd(false); fetchAll(); }}
            setToast={setToast}
          />
        )}

        <IonToast
          isOpen={toast !== null}
          message={toast?.message ?? ''}
          color={toast?.color ?? 'success'}
          duration={3000}
          position="top"
          onDidDismiss={() => setToastState(null)}
        />
      </IonContent>
    </IonPage>
  );
};

export default Automations;
