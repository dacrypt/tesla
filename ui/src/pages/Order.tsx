import React from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
} from '@ionic/react';
import { useHistory } from 'react-router-dom';
import OrderProcessTracker from '../components/OrderProcessTracker';
import CopyButton from '../components/CopyButton';
import SkeletonCard from '../components/SkeletonCard';
import EmptyState from '../components/EmptyState';
import { useAppInit } from '../hooks/useAppInit';
import { api, OrderTask } from '../api/client';

// ── Icons ─────────────────────────────────────────────────────────────────────

const CalendarIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M20 3h-1V1h-2v2H7V1H5v2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 18H4V8h16v13z"/>
  </svg>
);

const LocationIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
  </svg>
);

const FinanceIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/>
  </svg>
);

const CheckIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
  </svg>
);

const PendingIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
  </svg>
);

// ── Subcomponents ─────────────────────────────────────────────────────────────

function OrderHeader({
  reservationNumber,
  phase,
  phaseLabel,
  phaseColor,
  model,
  variant,
}: {
  reservationNumber?: string;
  phase: string;
  phaseLabel: string;
  phaseColor: string;
  model?: string;
  variant?: string;
}) {
  return (
    <div className="tesla-card p-lg mb-md">
      <div className="flex-between mb-sm">
        <div>
          {reservationNumber && (
            <div className="text-secondary text-sm mb-xs">
              RN {reservationNumber}
            </div>
          )}
          <div className="fw-bold text-xl" style={{ color: '#fff' }}>
            {model || 'Tesla'}{variant ? ` ${variant}` : ''}
          </div>
        </div>
        <span style={{
          fontSize: 12,
          fontWeight: 700,
          color: phaseColor,
          background: `${phaseColor}18`,
          padding: '5px 14px',
          borderRadius: 100,
          border: `1px solid ${phaseColor}30`,
        }}>
          {phaseLabel}
        </span>
      </div>
    </div>
  );
}

const MapIcon = () => (
  <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor">
    <path d="M20.5 3l-.16.03L15 5.1 9 3 3.36 4.9c-.21.07-.36.25-.36.48V20.5c0 .28.22.5.5.5l.16-.03L9 18.9l6 2.1 5.64-1.9c.21-.07.36-.25.36-.48V3.5c0-.28-.22-.5-.5-.5zM15 19l-6-2.11V5l6 2.11V19z"/>
  </svg>
);

const CreditIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z"/>
  </svg>
);

const PlateIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/>
  </svg>
);

function DeliveryCard({
  deliveryDate,
  deliveryLocation,
  deliveryAddress,
  deliveryWindow,
  deliveryType,
  creditBalance,
  licensePlate,
  mapUrl,
  statusMessage,
  delivered = false,
}: {
  deliveryDate?: string;
  deliveryLocation?: string;
  deliveryAddress?: string;
  deliveryWindow?: string;
  deliveryType?: string;
  creditBalance?: number | string;
  licensePlate?: string;
  mapUrl?: string;
  statusMessage?: string;
  delivered?: boolean;
}) {
  if (!deliveryDate && !deliveryWindow && !deliveryLocation) return null;

  return (
    <div className="tesla-card p-lg mb-md">
      {/* Header */}
      <div className="flex-between mb-md">
        <div className="flex-center gap-sm">
          <span style={{ color: '#05C46B' }}><CalendarIcon /></span>
          <span className="fw-semi text-lg" style={{ color: '#f5f5f7' }}>Delivery</span>
        </div>
        {deliveryDate && (
          <span style={{
            fontSize: 10, fontWeight: 700, color: '#05C46B',
            background: '#05C46B18', padding: '3px 10px',
            borderRadius: 100, border: '1px solid #05C46B30',
          }}>{delivered ? 'DELIVERED' : 'SCHEDULED'}</span>
        )}
      </div>

      {/* Date + type row */}
      <div style={{ display: 'grid', gridTemplateColumns: deliveryType ? '1fr 1fr' : '1fr', gap: 12, marginBottom: 10 }}>
        <div>
          <div className="text-secondary fw-semi uppercase mb-xs" style={{ fontSize: 10, letterSpacing: '0.05em' }}>{delivered ? 'Delivered On' : 'Appointment'}</div>
          {deliveryDate ? (
            <div className="fw-bold text-accent" style={{ fontSize: 16 }}>{deliveryDate}</div>
          ) : deliveryWindow ? (
            <div className="fw-semi text-base" style={{ color: '#F99716' }}>{deliveryWindow}</div>
          ) : (
            <div className="text-secondary text-base">Pending</div>
          )}
        </div>
        {deliveryType && (
          <div>
            <div className="text-secondary fw-semi uppercase mb-xs" style={{ fontSize: 10, letterSpacing: '0.05em' }}>Type</div>
            <div className="text-base" style={{ color: '#f5f5f7' }}>{deliveryType}</div>
          </div>
        )}
      </div>

      {/* Location */}
      {deliveryLocation && (
        <div className="mb-md" style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-secondary" style={{ marginTop: 1 }}><LocationIcon /></span>
          <div className="flex-1">
            <div className="text-base" style={{ color: '#f5f5f7' }}>{deliveryLocation}</div>
            {deliveryAddress && (
              <div className="text-secondary text-sm" style={{ marginTop: 2 }}>{deliveryAddress}</div>
            )}
          </div>
          {mapUrl && (
            <a href={mapUrl} target="_blank" rel="noopener noreferrer" style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              color: '#0FBCF9', fontSize: 11, fontWeight: 600, textDecoration: 'none',
              flexShrink: 0,
            }}>
              <MapIcon /> Map
            </a>
          )}
        </div>
      )}

      {/* Credit balance + License plate row */}
      {(creditBalance != null || licensePlate != null) && (
        <div className="grid-2 gap-md" style={{ padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          {creditBalance != null && (
            <div className="flex-center gap-sm" style={{ gap: 6 }}>
              <span className="text-secondary"><CreditIcon /></span>
              <div>
                <div className="text-secondary fw-semi uppercase" style={{ fontSize: 10 }}>Credit Balance</div>
                <div className="fw-semi text-base" style={{ color: '#f5f5f7' }}>
                  {typeof creditBalance === 'number' ? `$ ${Math.abs(creditBalance).toLocaleString()}` : creditBalance}
                </div>
              </div>
            </div>
          )}
          {licensePlate != null && (
            <div className="flex-center gap-sm" style={{ gap: 6 }}>
              <span className="text-secondary"><PlateIcon /></span>
              <div>
                <div className="text-secondary fw-semi uppercase" style={{ fontSize: 10 }}>License Plate</div>
                <div className="fw-semi text-base" style={{ color: licensePlate === 'Pending' ? '#F99716' : '#f5f5f7' }}>{licensePlate}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Status message */}
      {statusMessage && (
        <div style={{ marginTop: 6, padding: '6px 10px', background: 'rgba(15,188,249,0.06)', borderRadius: 6, border: '1px solid rgba(15,188,249,0.12)' }}>
          <div className="text-sm" style={{ color: '#0FBCF9' }}>{statusMessage}</div>
        </div>
      )}
    </div>
  );
}

function FinancingCard({ financing }: { financing: Record<string, unknown> | null }) {
  if (!financing || Object.keys(financing).length === 0) return null;

  const entries = Object.entries(financing).filter(([, v]) => v != null && v !== '');

  if (entries.length === 0) return null;

  const formatKey = (k: string) =>
    k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  const formatVal = (v: unknown): string => {
    if (typeof v === 'number') return v.toLocaleString();
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    return String(v);
  };

  return (
    <div className="tesla-card p-lg mb-md">
      <div className="flex-center gap-sm mb-md">
        <span style={{ color: '#9B59B6' }}><FinanceIcon /></span>
        <span className="fw-semi text-lg" style={{ color: '#f5f5f7' }}>Financing</span>
      </div>
      <div className="grid-2" style={{ gap: '6px 12px' }}>
        {entries.map(([k, v]) => (
          <div key={k}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>{formatKey(k)}</div>
            <div className="fw-medium text-base" style={{ color: '#f5f5f7' }}>{formatVal(v)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TasksCard({ tasks }: { tasks: OrderTask[] }) {
  if (!tasks || tasks.length === 0) return (
    <EmptyState title="No delivery tasks" message="Task details will appear once available from the Tesla API." />
  );

  const completedCount = tasks.filter(t =>
    t.completed || t.task_status?.toLowerCase() === 'complete' || t.task_status?.toLowerCase() === 'completed'
  ).length;

  // Build subtitle from task details
  const getSubtitle = (task: OrderTask): string | null => {
    const d = task.details || {};
    const parts: string[] = [];
    if (d.cardMessageTitle) parts.push(String(d.cardMessageTitle));
    if (d.registrationStatus) parts.push(String(d.registrationStatus));
    if (d.financialProductType) {
      parts.push(String(d.financialProductType).replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
    }
    if (d.cardSubtitle) parts.push(String(d.cardSubtitle));
    if (d.deliveryAddressTitle) parts.push(String(d.deliveryAddressTitle));
    if (d.completedPackets && Array.isArray(d.completedPackets)) {
      parts.push(d.completedPackets.join(', '));
    }
    if (d.eSignStatus) parts.push(`eSign: ${d.eSignStatus}`);
    return parts.length > 0 ? parts.join(' \u2022 ') : null;
  };

  // Status badge text and color
  const getBadge = (task: OrderTask): { text: string; color: string } | null => {
    const d = task.details || {};
    const s = String(d.status || task.task_status || '').toUpperCase();
    if (s === 'COMPLETE' || s === 'COMPLETED') return { text: 'Complete', color: '#05C46B' };
    if (s === 'DEFAULT') return { text: 'Default', color: '#86888f' };
    if (s === 'SELF_ARRANGED' || s === 'SELF-ARRANGED') return { text: 'Self-Arranged', color: '#F99716' };
    if (s === 'IGNORE') return null;
    if (s && !task.completed) return { text: s.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()), color: '#86888f' };
    return null;
  };

  return (
    <div className="tesla-card p-lg mb-md">
      {/* Header with progress counter */}
      <div className="flex-between mb-md">
        <div className="fw-semi text-lg" style={{ color: '#f5f5f7' }}>Delivery Progress</div>
        <span style={{
          fontSize: 11, fontWeight: 700, color: '#05C46B',
          background: '#05C46B18', padding: '2px 10px',
          borderRadius: 100, border: '1px solid #05C46B30',
        }}>
          {completedCount}/{tasks.length}
        </span>
      </div>
      <div className="flex-col" style={{ gap: 6 }}>
        {tasks.map((task, i) => {
          const done = task.completed || task.task_status?.toLowerCase() === 'complete' || task.task_status?.toLowerCase() === 'completed';
          const active = task.active && !done;
          const subtitle = getSubtitle(task);
          const badge = getBadge(task);

          return (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              padding: '10px 10px',
              borderRadius: 8,
              background: active
                ? 'rgba(5,196,107,0.06)'
                : done
                  ? 'rgba(11,232,129,0.03)'
                  : 'rgba(255,255,255,0.02)',
              border: `1px solid ${active ? 'rgba(5,196,107,0.2)' : done ? 'rgba(11,232,129,0.08)' : 'rgba(255,255,255,0.04)'}`,
            }}>
              <span style={{ color: done ? '#0BE881' : active ? '#05C46B' : '#86888f', flexShrink: 0, marginTop: 1 }}>
                {done ? <CheckIcon /> : <PendingIcon />}
              </span>
              <div className="flex-1" style={{ minWidth: 0 }}>
                <div className={`text-base${(active || done) ? ' fw-semi' : ''}`} style={{
                  color: done ? (subtitle ? '#c8c9cc' : '#86888f') : active ? '#f5f5f7' : '#86888f',
                }}>
                  {task.task_name || task.task_type}
                </div>
                {subtitle && (
                  <div className="text-secondary" style={{ fontSize: 10, marginTop: 3, lineHeight: '1.4' }}>
                    {subtitle}
                  </div>
                )}
              </div>
              {badge && (
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: badge.color,
                  background: `${badge.color}14`,
                  padding: '2px 7px',
                  borderRadius: 100,
                  border: `1px solid ${badge.color}28`,
                  flexShrink: 0,
                  marginTop: 1,
                }}>
                  {badge.text}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const HistoryIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M13 3a9 9 0 00-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0013 21a9 9 0 000-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/>
  </svg>
);

function SnapshotHistoryCard({ snapshots, reservationNumber }: {
  snapshots: Record<string, unknown>[];
  reservationNumber?: string;
}) {
  if (!snapshots || snapshots.length === 0) return (
    <EmptyState title="No snapshots yet" message="Order snapshots will accumulate as status changes are detected." />
  );

  // Sort newest first
  const sorted = [...snapshots].reverse();

  const formatTs = (ts?: unknown): string => {
    if (!ts || typeof ts !== 'string') return '—';
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: '2-digit', day: '2-digit', year: 'numeric',
        hour: 'numeric', minute: '2-digit', hour12: true,
      });
    } catch { return String(ts); }
  };

  return (
    <div className="tesla-card p-lg mb-md">
      <div className="flex-between mb-md">
        <div className="flex-center gap-sm">
          <span style={{ color: '#0FBCF9' }}><HistoryIcon /></span>
          <span className="fw-semi text-lg" style={{ color: '#f5f5f7' }}>Order Snapshot History</span>
        </div>
        {reservationNumber && (
          <span className="text-secondary" style={{ fontSize: 10 }}>{reservationNumber}</span>
        )}
      </div>
      <div className="flex-col" style={{ gap: 4 }}>
        {sorted.map((snap, i) => {
          const data = (snap.data || snap) as Record<string, unknown>;
          const changes = (snap.changes || []) as { field: string; old?: string; new?: string }[];
          const status = String(data.order_status || data.orderStatus || '—');
          const substatus = String(data.order_substatus || data.orderSubstatus || '');
          const hasChanges = changes.length > 0;

          return (
            <div key={i} style={{
              padding: '8px 10px', borderRadius: 6,
              background: hasChanges ? 'rgba(249,151,22,0.04)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${hasChanges ? 'rgba(249,151,22,0.12)' : 'rgba(255,255,255,0.04)'}`,
            }}>
              <div className="flex-between">
                <div className="text-secondary text-sm">{formatTs(snap.timestamp)}</div>
                <div className="flex-center" style={{ gap: 6 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, color: '#f5f5f7',
                    background: 'rgba(255,255,255,0.06)', padding: '1px 6px',
                    borderRadius: 4,
                  }}>{status}</span>
                  {substatus && (
                    <span className="text-secondary" style={{ fontSize: 10 }}>{substatus}</span>
                  )}
                </div>
              </div>
              {hasChanges && (
                <div className="mt-xs">
                  {changes.map((c, j) => (
                    <div key={j} style={{ fontSize: 10, color: '#F99716' }}>
                      {c.field}: {c.old || '—'} → {c.new || '—'}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-md" style={{ textAlign: 'center', fontSize: 10, color: 'rgba(255,255,255,0.2)' }}>
        {sorted.length} snapshot{sorted.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const Order: React.FC = () => {
  const { sources, computed } = useAppInit();
  const history = useHistory();

  const [orderTasks, setOrderTasks] = React.useState<OrderTask[]>([]);
  const [orderFinancing, setOrderFinancing] = React.useState<Record<string, unknown> | null>(null);
  const [orderStatus, setOrderStatus] = React.useState<Record<string, unknown> | null>(null);
  const [orderDelivery, setOrderDelivery] = React.useState<Record<string, unknown> | null>(null);
  const [orderLoading, setOrderLoading] = React.useState(false);
  const [orderSummary, setOrderSummary] = React.useState<string>('');
  const [shareText, setShareText] = React.useState<string>('');
  const [snapshots, setSnapshots] = React.useState<Record<string, unknown>[]>([]);

  const fetchOrder = React.useCallback(() => {
    setOrderLoading(true);
    // Fetch summary + share text + snapshots in parallel
    api.getOrderSummary().then(r => setOrderSummary(r?.summary || '')).catch(() => {});
    api.getOrderShareText().then(r => setShareText(r?.text || '')).catch(() => {});
    api.getSourceHistory('tesla_orders', 10).then(h => setSnapshots(h || [])).catch(() => {});
    api.getOrderDetails()
      .then(details => {
        setOrderTasks(details.tasks || []);
        setOrderFinancing(details.financing || null);
        setOrderDelivery(details.delivery || null);
        setOrderStatus(details.status as unknown as Record<string, unknown> || null);
      })
      .catch(() => {
        api.getOrderStatus().then(s => {
          setOrderStatus(s as unknown as Record<string, unknown>);
        }).catch(() => {});
      })
      .finally(() => setOrderLoading(false));
  }, []);

  React.useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const doRefresh = async (event: CustomEvent) => {
    fetchOrder();
    await new Promise<void>(r => setTimeout(r, 1000));
    (event.target as HTMLIonRefresherElement).complete();
  };

  const status = computed.real_status;
  const order = sources['tesla.order'];
  const specs = computed.specs;
  const phase = status?.phase || 'ordered';

  const phaseLabels: Record<string, string> = {
    ordered: 'Ordered', produced: 'Produced', shipped: 'In Transit',
    in_country: 'In Country', registered: 'Registered',
    delivery_scheduled: 'Delivery Scheduled', delivered: 'Delivered',
  };
  const phaseColors: Record<string, string> = {
    ordered: '#0FBCF9', produced: '#F99716', shipped: '#F99716',
    in_country: '#0BE881', registered: '#0BE881',
    delivery_scheduled: '#05C46B', delivered: '#05C46B',
  };

  const phaseLabel = phaseLabels[phase] || phase;
  const phaseColor = phaseColors[phase] || '#0FBCF9';

  // Delivery window string
  const deliveryWindow = order?.current?.delivery_window_start
    ? `${order.current.delivery_window_start}${order.current.delivery_window_end ? ` — ${order.current.delivery_window_end}` : ''}`
    : undefined;

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700, letterSpacing: '-0.3px' }}>Order</IonTitle>
          {orderLoading && (
            <div slot="end" style={{ paddingRight: 16 }}>
              <IonSpinner name="dots" style={{ '--color': '#86888f', width: 20, height: 20 } as React.CSSProperties} />
            </div>
          )}
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        <div className="page-pad" style={{ paddingTop: 8 }}>
          {/* ── Order Header ── */}
          <OrderHeader
            reservationNumber={order?.reservation_number}
            phase={phase}
            phaseLabel={phaseLabel}
            phaseColor={phaseColor}
            model={specs?.model}
            variant={specs?.variant}
          />

          {/* ── Skeleton while loading ── */}
          {orderLoading && !orderSummary && (
            <>
              <SkeletonCard rows={2} showHeader={false} />
              <SkeletonCard rows={4} showHeader />
            </>
          )}

          {/* ── Summary Card ── */}
          {orderSummary && (
            <div className="tesla-card mb-md" style={{ padding: 14 }}>
              <div className="flex-between" style={{ alignItems: 'flex-start', gap: 10 }}>
                <div className="flex-1" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <span style={{ color: '#0FBCF9', marginTop: 1, flexShrink: 0 }}>
                    <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
                      <path d="M11 17h2v-6h-2v6zm0-8h2V7h-2v2zm1 13C6.48 22 2 17.52 2 12S6.48 2 12 2s10 4.48 10 10-4.48 10-10 10z"/>
                    </svg>
                  </span>
                  <span className="text-base" style={{ color: '#c8c9cc', lineHeight: '1.4' }}>{orderSummary}</span>
                </div>
                {shareText && <CopyButton text={shareText} label="Share" />}
              </div>
            </div>
          )}

          {/* ── OrderProcessTracker (15-step timeline) ── */}
          <OrderProcessTracker
            orderStatus={orderStatus}
            tasks={orderTasks}
            financing={orderFinancing}
            realStatus={status}
            logistics={null}
            runt={sources['co.runt']}
            financial={null}
            loading={orderLoading}
          />

          {/* ── Delivery ── */}
          <DeliveryCard
            deliveryDate={status?.delivery_date || (orderDelivery?.appointmentDateUtc as string)}
            deliveryLocation={status?.delivery_location || (orderDelivery?.location as string)}
            deliveryAddress={orderDelivery?.address as string}
            deliveryWindow={deliveryWindow}
            deliveryType={
              orderDelivery?.deliveryType === 'PICKUP_SERVICE_CENTER' ? 'Pickup at Service Center'
                : orderDelivery?.deliveryType === 'DELIVERY' ? 'Home Delivery'
                : (orderDelivery?.deliveryType as string)
            }
            creditBalance={orderDelivery?.amountDue != null ? orderDelivery.amountDue as number : undefined}
            licensePlate={sources['co.runt']?.placa || sources['co.runt']?.current?.placa || 'Pending'}
            delivered={!!status?.is_delivered}
            mapUrl={orderDelivery?.mapUrl as string}
            statusMessage={
              orderDelivery?.vehicleIsReady && !orderDelivery?.withinAppointmentWindow
                ? 'Vehicle ready. Waiting for appointment window.'
                : orderDelivery?.readyToAccept
                  ? 'Your order is ready for scheduling once Tesla opens appointment booking.'
                  : undefined
            }
          />

          {/* ── Financing ── */}
          <FinancingCard financing={orderFinancing} />

          {/* ── Order Tasks ── */}
          <TasksCard tasks={orderTasks} />

          {/* ── Snapshot History ── */}
          <SnapshotHistoryCard
            snapshots={snapshots}
            reservationNumber={order?.reservation_number}
          />

          {/* ── Back to Dashboard ── */}
          <button
            onClick={() => history.push('/dashboard')}
            className="tesla-btn"
            style={{ width: '100%', fontSize: 14, padding: '14px 20px', borderRadius: 12, marginBottom: 8 }}
          >
            ← Back to Dashboard
          </button>

          {order?.lastActivityDate && (
            <div className="text-dim" style={{ textAlign: 'center', fontSize: 10, paddingBottom: 8 }}>
              Updated: {new Date(order.lastActivityDate).toLocaleString()}
            </div>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Order;
