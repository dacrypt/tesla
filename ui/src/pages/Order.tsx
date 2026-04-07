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
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div>
          {reservationNumber && (
            <div style={{ color: '#86888f', fontSize: 11, marginBottom: 4 }}>
              RN {reservationNumber}
            </div>
          )}
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 18 }}>
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

function DeliveryCard({
  deliveryDate,
  deliveryLocation,
  deliveryAddress,
  deliveryWindow,
}: {
  deliveryDate?: string;
  deliveryLocation?: string;
  deliveryAddress?: string;
  deliveryWindow?: string;
}) {
  if (!deliveryDate && !deliveryWindow && !deliveryLocation) return null;

  return (
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color: '#05C46B' }}><CalendarIcon /></span>
        <span style={{ color: '#f5f5f7', fontWeight: 600, fontSize: 14 }}>Delivery Appointment</span>
      </div>
      {deliveryDate && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 20 }}>{deliveryDate}</div>
        </div>
      )}
      {deliveryWindow && !deliveryDate && (
        <div style={{ color: '#F99716', fontSize: 14, fontWeight: 600, marginBottom: 8 }}>
          Window: {deliveryWindow}
        </div>
      )}
      {deliveryLocation && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 6 }}>
          <span style={{ color: '#86888f', marginTop: 1 }}><LocationIcon /></span>
          <div>
            <div style={{ color: '#f5f5f7', fontSize: 13 }}>{deliveryLocation}</div>
            {deliveryAddress && (
              <div style={{ color: '#86888f', fontSize: 11, marginTop: 2 }}>{deliveryAddress}</div>
            )}
          </div>
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
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ color: '#9B59B6' }}><FinanceIcon /></span>
        <span style={{ color: '#f5f5f7', fontWeight: 600, fontSize: 14 }}>Financing</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px' }}>
        {entries.map(([k, v]) => (
          <div key={k}>
            <div style={{ color: '#86888f', fontSize: 10, marginBottom: 2 }}>{formatKey(k)}</div>
            <div style={{ color: '#f5f5f7', fontSize: 13, fontWeight: 500 }}>{formatVal(v)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TasksCard({ tasks }: { tasks: OrderTask[] }) {
  if (!tasks || tasks.length === 0) return null;

  return (
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      <div style={{ color: '#f5f5f7', fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
        Order Tasks
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {tasks.map((task, i) => {
          const done = task.completed || task.task_status?.toLowerCase() === 'complete' || task.task_status?.toLowerCase() === 'completed';
          const active = task.active && !done;
          return (
            <div key={i} style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 8,
              background: active
                ? 'rgba(5,196,107,0.06)'
                : done
                  ? 'rgba(11,232,129,0.04)'
                  : 'rgba(255,255,255,0.02)',
              border: `1px solid ${active ? 'rgba(5,196,107,0.2)' : done ? 'rgba(11,232,129,0.1)' : 'rgba(255,255,255,0.04)'}`,
            }}>
              <span style={{ color: done ? '#0BE881' : active ? '#05C46B' : '#86888f', flexShrink: 0 }}>
                {done ? <CheckIcon /> : <PendingIcon />}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color: done ? '#86888f' : active ? '#f5f5f7' : '#86888f',
                  fontSize: 13,
                  fontWeight: active ? 600 : 400,
                  textDecoration: done ? 'line-through' : 'none',
                }}>
                  {task.task_name}
                </div>
                {task.task_status && (
                  <div style={{ color: '#86888f', fontSize: 10, marginTop: 2 }}>
                    {task.task_status}
                  </div>
                )}
              </div>
              {active && (
                <span style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: '#05C46B',
                  background: 'rgba(5,196,107,0.12)',
                  padding: '2px 7px',
                  borderRadius: 100,
                  border: '1px solid rgba(5,196,107,0.2)',
                }}>
                  Active
                </span>
              )}
            </div>
          );
        })}
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
  const [orderLoading, setOrderLoading] = React.useState(false);

  const fetchOrder = React.useCallback(() => {
    setOrderLoading(true);
    api.getOrderDetails()
      .then(details => {
        setOrderTasks(details.tasks || []);
        setOrderFinancing(details.financing || null);
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

          {/* ── Delivery Appointment ── */}
          <DeliveryCard
            deliveryDate={status?.delivery_date}
            deliveryLocation={status?.delivery_location}
            deliveryWindow={deliveryWindow}
          />

          {/* ── Financing ── */}
          <FinancingCard financing={orderFinancing} />

          {/* ── Order Tasks ── */}
          <TasksCard tasks={orderTasks} />

          {/* ── Back to Dashboard ── */}
          <button
            onClick={() => history.push('/dashboard')}
            className="tesla-btn"
            style={{ width: '100%', fontSize: 14, padding: '14px 20px', borderRadius: 12, marginBottom: 8 }}
          >
            ← Back to Dashboard
          </button>

          {order?.lastActivityDate && (
            <div style={{ textAlign: 'center', fontSize: 10, color: 'rgba(255,255,255,0.2)', paddingBottom: 8 }}>
              Updated: {new Date(order.lastActivityDate).toLocaleString()}
            </div>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Order;
