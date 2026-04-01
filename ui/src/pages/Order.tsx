import React, { useEffect, useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRefresher,
  IonRefresherContent,
} from '@ionic/react';
import { api, OrderStatus } from '../api/client';

// ---- Icons ----
const CheckIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
  </svg>
);

const PackageIcon = () => (
  <svg width={32} height={32} viewBox="0 0 24 24" fill="rgba(255,255,255,0.25)">
    <path d="M17 3H7c-1.1 0-1.99.9-1.99 2L5 21l7-3 7 3V5c0-1.1-.9-2-2-2zm0 15l-5-2.18L7 18V5h10v13z"/>
  </svg>
);

function Spin() {
  return (
    <svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.1)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

const gateLabels: Record<string, string> = {
  order_placed: 'Order Placed',
  payment_confirmed: 'Payment Confirmed',
  vin_assigned: 'VIN Assigned',
  in_production: 'In Production',
  produced: 'Produced',
  delivery_scheduled: 'Delivery Scheduled',
  delivered: 'Delivered',
};

function statusColor(status?: string): string {
  if (status === 'delivered') return '#0BE881';
  if (status === 'in_production') return '#F99716';
  if (status === 'produced') return '#0FBCF9';
  return '#86888f';
}

function daysUntil(dateStr: string): number {
  const d = new Date(dateStr);
  const now = new Date();
  return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

const KNOWN_DELIVERY = new Date('2026-04-10T10:00:00');

function OfflineOrderFallback() {
  const days = Math.max(0, Math.ceil((KNOWN_DELIVERY.getTime() - Date.now()) / (1000 * 60 * 60 * 24)));
  return (
    <div>
      {/* Offline banner */}
      <div style={{ background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.2)', borderRadius: 10, padding: '10px 14px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="#F99716"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>
        <span style={{ color: '#F99716', fontSize: 12 }}>Showing cached data — server offline</span>
      </div>

      {/* Order header */}
      <div className="tesla-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <div style={{ color: '#86888f', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>RN126460939</div>
            <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 22, letterSpacing: '-0.5px' }}>Tesla Model Y</div>
            <div style={{ color: '#86888f', fontSize: 13, marginTop: 3 }}>Long Range · Pearl White</div>
          </div>
          <span style={{ background: 'rgba(249,151,22,0.12)', color: '#F99716', border: '1px solid rgba(249,151,22,0.3)', borderRadius: 100, padding: '5px 12px', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}>
            Booked
          </span>
        </div>
        {/* Progress */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ color: '#86888f', fontSize: 12 }}>Delivery Progress</span>
          <span style={{ color: '#ffffff', fontSize: 12, fontWeight: 600 }}>4 / 7 gates</span>
        </div>
        <div className="progress-track" style={{ height: 8 }}>
          <div className="progress-fill" style={{ width: '57%', background: '#05C46B' }} />
        </div>
      </div>

      {/* VIN */}
      <div className="tesla-card">
        <div className="label-xs" style={{ marginBottom: 8 }}>Vehicle Identification Number</div>
        <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 18, fontFamily: 'SF Mono, Menlo, monospace', letterSpacing: '0.12em' }}>
          LRWYGCEK3TC512197
        </div>
        <div style={{ color: '#86888f', fontSize: 11, marginTop: 6 }}>Giga Shanghai · Model Y · 2023</div>
      </div>

      {/* Delivery */}
      <div className="tesla-card" style={{ borderColor: 'rgba(5,196,107,0.25)' }}>
        <div className="label-xs" style={{ marginBottom: 10, color: '#05C46B' }}>DELIVERY APPOINTMENT</div>
        <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 22, marginBottom: 4, letterSpacing: '-0.5px' }}>
          Thursday, April 10, 2026
        </div>
        <div style={{ color: '#86888f', fontSize: 14, marginBottom: 12 }}>10:00 AM</div>
        {days > 0 && (
          <div style={{ background: 'rgba(5,196,107,0.1)', border: '1px solid rgba(5,196,107,0.2)', borderRadius: 10, padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: '#86888f', fontSize: 13 }}>Days until delivery</span>
            <span style={{ color: '#05C46B', fontWeight: 700, fontSize: 22 }}>{days}</span>
          </div>
        )}
      </div>

      {/* Gates */}
      <div className="tesla-card">
        <p className="section-title" style={{ paddingTop: 0 }}>Delivery Gates</p>
        {[
          { label: 'Order Placed', done: true },
          { label: 'Payment Confirmed', done: true },
          { label: 'VIN Assigned', done: true },
          { label: 'In Production', done: true },
          { label: 'Produced', done: false, current: true },
          { label: 'Delivery Scheduled', done: false },
          { label: 'Delivered', done: false },
        ].map((gate, i, arr) => (
          <div key={gate.label} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: i < arr.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
            <div style={{ width: 30, height: 30, borderRadius: '50%', background: gate.done ? '#0BE881' : gate.current ? 'rgba(5,196,107,0.2)' : 'rgba(255,255,255,0.06)', border: `2px solid ${gate.done ? '#0BE881' : gate.current ? '#05C46B' : 'rgba(255,255,255,0.1)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: gate.done ? '#000' : gate.current ? '#05C46B' : '#86888f', fontSize: 11, fontWeight: 700 }}>
              {gate.done ? <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg> : i + 1}
            </div>
            <div style={{ flex: 1 }}>
              <span style={{ color: gate.done ? '#fff' : gate.current ? '#fff' : '#86888f', fontSize: 14, fontWeight: gate.done || gate.current ? 600 : 400 }}>{gate.label}</span>
              {gate.current && <div style={{ color: '#05C46B', fontSize: 11, marginTop: 2, fontWeight: 600 }}>YOU ARE HERE</div>}
            </div>
            {gate.done && <span style={{ color: '#0BE881', fontSize: 11, fontWeight: 600 }}>Done</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

const Order: React.FC = () => {
  const [order, setOrder] = useState<OrderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrder = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getOrderStatus();
      setOrder(data);
    } catch (e: unknown) {
      const err = e as { response?: { status: number } };
      if (err.response?.status === 404) {
        setError('no_order');
      } else {
        setError('fetch_failed');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchOrder(); }, []);

  const doRefresh = async (event: CustomEvent) => {
    await fetchOrder();
    (event.target as HTMLIonRefresherElement).complete();
  };

  const gates = order?.gates || {};
  const gateEntries = Object.entries(gates);
  const completedGates = gateEntries.filter(([, v]) => v).length;
  const totalGates = gateEntries.length;
  const progressPct = totalGates > 0 ? (completedGates / totalGates) * 100 : 0;
  const color = statusColor(order?.status);

  // Find the first incomplete gate (current position)
  const currentGateIdx = gateEntries.findIndex(([, v]) => !v);

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Order Status</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        <div className="page-pad">
          {loading ? (
            <div className="loading-center">
              <Spin />
            </div>
          ) : error ? (
            error === 'fetch_failed' ? (
              // Show last-known order data when API is offline
              <OfflineOrderFallback />
            ) : (
              // no_order
              <div className="empty-state">
                <div className="empty-icon"><PackageIcon /></div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 18 }}>No Active Order</div>
                <div style={{ color: '#86888f', fontSize: 14, lineHeight: 1.5 }}>Order data will appear here once you have a Tesla on order.</div>
              </div>
            )
          ) : (
            <>
              {/* ---- Order header card ---- */}
              <div className="tesla-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                  <div>
                    <div style={{ color: '#86888f', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
                      RN{order?.order_id || '—'}
                    </div>
                    <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 22, letterSpacing: '-0.5px' }}>
                      {order?.model || 'Tesla Model Y'}
                    </div>
                    {(order?.trim || order?.color) && (
                      <div style={{ color: '#86888f', fontSize: 13, marginTop: 3 }}>
                        {[order.trim, order.color].filter(Boolean).join(' · ')}
                      </div>
                    )}
                  </div>
                  <span
                    style={{
                      background: `${color}15`,
                      color: color,
                      border: `1px solid ${color}40`,
                      borderRadius: 100,
                      padding: '5px 12px',
                      fontSize: 12,
                      fontWeight: 600,
                      textTransform: 'capitalize',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {order?.status?.replace(/_/g, ' ') || 'Unknown'}
                  </span>
                </div>

                {totalGates > 0 && (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ color: '#86888f', fontSize: 12 }}>Delivery Progress</span>
                      <span style={{ color: '#ffffff', fontSize: 12, fontWeight: 600 }}>{completedGates} / {totalGates} gates</span>
                    </div>
                    <div className="progress-track" style={{ height: 8 }}>
                      <div
                        className="progress-fill"
                        style={{
                          width: `${progressPct}%`,
                          background: progressPct === 100 ? '#0BE881' : '#05C46B',
                        }}
                      />
                    </div>
                  </>
                )}
              </div>

              {/* ---- VIN ---- */}
              {order?.vin && (
                <div className="tesla-card">
                  <div className="label-xs" style={{ marginBottom: 8 }}>Vehicle Identification Number</div>
                  <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 18, fontFamily: 'SF Mono, Menlo, monospace', letterSpacing: '0.12em' }}>
                    {order.vin}
                  </div>
                </div>
              )}

              {/* ---- Delivery appointment ---- */}
              {order?.delivery_appointment && (() => {
                const apptDate = new Date(order.delivery_appointment!);
                const days = daysUntil(order.delivery_appointment!);
                return (
                  <div className="tesla-card" style={{ borderColor: 'rgba(5,196,107,0.25)' }}>
                    <div className="label-xs" style={{ marginBottom: 10, color: '#05C46B' }}>DELIVERY APPOINTMENT</div>
                    <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 22, marginBottom: 4, letterSpacing: '-0.5px' }}>
                      {apptDate.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                    </div>
                    <div style={{ color: '#86888f', fontSize: 14, marginBottom: 12 }}>
                      {apptDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    {days > 0 && (
                      <div style={{ background: 'rgba(5,196,107,0.1)', border: '1px solid rgba(5,196,107,0.2)', borderRadius: 10, padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#86888f', fontSize: 13 }}>Days until delivery</span>
                        <span style={{ color: '#05C46B', fontWeight: 700, fontSize: 22 }}>{days}</span>
                      </div>
                    )}
                    {days <= 0 && (
                      <div style={{ background: 'rgba(11,232,129,0.1)', border: '1px solid rgba(11,232,129,0.25)', borderRadius: 10, padding: '10px 14px', textAlign: 'center', color: '#0BE881', fontWeight: 600 }}>
                        Delivery Day!
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* ---- ETA (no appointment) ---- */}
              {!order?.delivery_appointment && order?.estimated_delivery && (
                <div className="tesla-card">
                  <div className="label-xs" style={{ marginBottom: 8 }}>ESTIMATED DELIVERY</div>
                  <div style={{ color: '#F99716', fontWeight: 700, fontSize: 22 }}>{order.estimated_delivery}</div>
                </div>
              )}

              {/* ---- Delivery Gates ---- */}
              {gateEntries.length > 0 && (
                <div className="tesla-card">
                  <p className="section-title" style={{ paddingTop: 0 }}>Delivery Gates</p>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {gateEntries.map(([key, value], index) => {
                      const isCurrentGate = index === currentGateIdx;
                      return (
                        <div
                          key={key}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '12px 0',
                            borderBottom: index < gateEntries.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                          }}
                        >
                          {/* Gate number / check circle */}
                          <div
                            style={{
                              width: 30,
                              height: 30,
                              borderRadius: '50%',
                              background: value ? '#0BE881' : isCurrentGate ? 'rgba(5,196,107,0.2)' : 'rgba(255,255,255,0.06)',
                              border: `2px solid ${value ? '#0BE881' : isCurrentGate ? '#05C46B' : 'rgba(255,255,255,0.1)'}`,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexShrink: 0,
                              color: value ? '#000' : isCurrentGate ? '#05C46B' : '#86888f',
                              fontSize: 11,
                              fontWeight: 700,
                            }}
                          >
                            {value ? <CheckIcon /> : index + 1}
                          </div>

                          <div style={{ flex: 1 }}>
                            <span style={{ color: value ? '#ffffff' : isCurrentGate ? '#ffffff' : '#86888f', fontSize: 14, fontWeight: value || isCurrentGate ? 600 : 400 }}>
                              {gateLabels[key] || key.replace(/_/g, ' ')}
                            </span>
                            {isCurrentGate && !value && (
                              <div style={{ color: '#05C46B', fontSize: 11, marginTop: 2, fontWeight: 600 }}>
                                YOU ARE HERE
                              </div>
                            )}
                          </div>

                          {value && (
                            <span style={{ color: '#0BE881', fontSize: 11, fontWeight: 600 }}>Done</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Order;
