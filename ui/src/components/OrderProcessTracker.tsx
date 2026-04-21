import React, { useState } from 'react';
import { OrderTask, RealStatus, DossierLogistics, RuntData, DossierFinancial } from '../api/client';

// ── Step definitions ───────────────────────────────────────────────────────

type StepCategory = 'order' | 'financing' | 'production' | 'logistics' | 'registration' | 'delivery';

interface StepDef {
  id: string;
  label: string;
  icon: string;
  category: StepCategory;
}

const ORDER_STEPS: StepDef[] = [
  { id: 'order_placed',       label: 'Order Placed',          icon: '📋', category: 'order' },
  { id: 'payment_method',     label: 'Payment Method',         icon: '💳', category: 'financing' },
  { id: 'bank_approval',      label: 'Bank Approval',          icon: '🏦', category: 'financing' },
  { id: 'bank_disbursement',  label: 'Bank Disbursement',      icon: '💰', category: 'financing' },
  { id: 'payment_to_tesla',   label: 'Payment to Tesla',       icon: '✅', category: 'financing' },
  { id: 'vin_assigned',       label: 'VIN Assigned',           icon: '🔑', category: 'production' },
  { id: 'vehicle_produced',   label: 'Vehicle Produced',       icon: '🏭', category: 'production' },
  { id: 'vehicle_shipped',    label: 'Shipped',                icon: '🚢', category: 'logistics' },
  { id: 'customs_cleared',    label: 'Customs Cleared',        icon: '🛃', category: 'logistics' },
  { id: 'runt_registered',    label: 'RUNT Registered',        icon: '🇨🇴', category: 'registration' },
  { id: 'insurance_soat',     label: 'SOAT Insurance',         icon: '🛡️', category: 'registration' },
  { id: 'plate_assigned',     label: 'Plate Assigned',         icon: '🏷️', category: 'registration' },
  { id: 'delivery_scheduled', label: 'Delivery Scheduled',     icon: '📅', category: 'delivery' },
  { id: 'documents_ready',    label: 'Documents Ready',        icon: '📄', category: 'delivery' },
  { id: 'delivered',          label: 'Delivered!',             icon: '🎉', category: 'delivery' },
];

const CATEGORY_LABELS: Record<StepCategory, string> = {
  order:        'Order',
  financing:    'Financing',
  production:   'Production',
  logistics:    'Logistics',
  registration: 'Registration',
  delivery:     'Delivery',
};

const CATEGORY_COLORS: Record<StepCategory, string> = {
  order:        '#0FBCF9',
  financing:    '#9B59B6',
  production:   '#F99716',
  logistics:    '#F99716',
  registration: '#0BE881',
  delivery:     '#05C46B',
};

// ── Step state resolution ──────────────────────────────────────────────────

interface StepState {
  completed: boolean;
  active: boolean;
  date?: string;
}

function resolveSteps(
  orderStatus: Record<string, unknown> | null,
  tasks: OrderTask[],
  realStatus: RealStatus | null | undefined,
  logistics: DossierLogistics | null | undefined,
  runt: RuntData | null | undefined,
  financing: Record<string, unknown> | null,
): Record<string, StepState> {
  const result: Record<string, StepState> = {};

  // Helper: search tasks by type or name substring
  const findTask = (typeOrName: string): OrderTask | undefined =>
    tasks.find(t =>
      t.task_type?.toLowerCase().includes(typeOrName.toLowerCase()) ||
      t.task_name?.toLowerCase().includes(typeOrName.toLowerCase())
    );

  const taskDone = (typeOrName: string): boolean => {
    const t = findTask(typeOrName);
    return t ? (t.completed || t.task_status?.toLowerCase() === 'complete' || t.task_status?.toLowerCase() === 'completed') : false;
  };

  const taskActive = (typeOrName: string): boolean => {
    const t = findTask(typeOrName);
    return t ? (t.active || t.task_status?.toLowerCase() === 'in_progress' || t.task_status?.toLowerCase() === 'pending') : false;
  };

  // order_placed: always true if we have reservation data
  result['order_placed'] = {
    completed: true,
    active: false,
    date: (orderStatus?.order_date as string) || undefined,
  };

  // payment_method: task type or financing.paymentMethod
  const paymentMethodTask = findTask('payment');
  const hasPaymentMethod = !!(financing?.paymentMethod || financing?.payment_method || financing?.lender);
  result['payment_method'] = {
    completed: taskDone('payment') || hasPaymentMethod,
    active: !hasPaymentMethod && taskActive('payment'),
  };

  // bank_approval: from financing or task
  const bankApproval = taskDone('loan') || taskDone('bank') || taskDone('approval') ||
    !!(financing?.loanApproved || financing?.loan_approved || financing?.approved);
  result['bank_approval'] = {
    completed: bankApproval,
    active: !bankApproval && !!(paymentMethodTask?.completed),
  };

  // bank_disbursement
  const disbursed = taskDone('disburs') || !!(financing?.disbursed || financing?.disbursement);
  result['bank_disbursement'] = {
    completed: disbursed,
    active: !disbursed && bankApproval,
  };

  // payment_to_tesla
  const paidTesla = taskDone('final_payment') || taskDone('payment_to_tesla') ||
    taskDone('tesla_payment') || !!(financing?.paidToTesla || financing?.paid);
  result['payment_to_tesla'] = {
    completed: paidTesla,
    active: !paidTesla && disbursed,
  };

  // vin_assigned
  const vinAssigned = !!(realStatus?.vin_assigned || orderStatus?.vin);
  result['vin_assigned'] = {
    completed: vinAssigned,
    active: !vinAssigned && paidTesla,
  };

  // vehicle_produced
  const produced = !!(realStatus?.is_produced);
  result['vehicle_produced'] = {
    completed: produced,
    active: !produced && vinAssigned,
  };

  // vehicle_shipped
  const shipped = !!(realStatus?.is_shipped);
  result['vehicle_shipped'] = {
    completed: shipped,
    active: !shipped && produced,
  };

  // customs_cleared
  const customsCleared = !!(realStatus?.is_customs_cleared ||
    (logistics?.customs_status && logistics.customs_status.toLowerCase().includes('clear')));
  result['customs_cleared'] = {
    completed: customsCleared,
    active: !customsCleared && shipped,
  };

  // runt_registered
  const inRunt = !!(realStatus?.in_runt);
  result['runt_registered'] = {
    completed: inRunt,
    active: !inRunt && customsCleared,
  };

  // insurance_soat
  const hasSoat = !!(realStatus?.has_soat || runt?.soat_vigente);
  result['insurance_soat'] = {
    completed: hasSoat,
    active: !hasSoat && inRunt,
    date: runt?.soat_vencimiento ? `Vence: ${runt.soat_vencimiento}` : undefined,
  };

  // plate_assigned
  const hasPlaca = !!(realStatus?.has_placa || (runt?.placa && runt.placa.trim() !== ''));
  result['plate_assigned'] = {
    completed: hasPlaca,
    active: !hasPlaca && hasSoat,
    date: runt?.placa || undefined,
  };

  // delivery_scheduled
  const deliveryScheduled = !!(realStatus?.is_delivery_scheduled || realStatus?.delivery_date);
  result['delivery_scheduled'] = {
    completed: deliveryScheduled,
    active: !deliveryScheduled && hasPlaca,
    date: realStatus?.delivery_date || undefined,
  };

  // documents_ready
  const docsReady = taskDone('document') || taskDone('docs') || deliveryScheduled;
  result['documents_ready'] = {
    completed: docsReady,
    active: !docsReady && deliveryScheduled,
  };

  // delivered
  const delivered = !!(realStatus?.is_delivered);
  result['delivered'] = {
    completed: delivered,
    active: !delivered && deliveryScheduled,
    date: realStatus?.delivery_date || undefined,
  };

  // Terminal-state cascade: if delivered, every earlier step is implicitly done.
  // Post-delivery paperwork (RUNT, SOAT, plate) may still trail by days, so
  // only cascade completion into production/logistics/order/financing/delivery
  // categories — leave registration steps as-is so pending paperwork stays visible.
  if (delivered) {
    for (const step of ORDER_STEPS) {
      if (step.id === 'delivered') continue;
      if (step.category === 'registration') continue;
      const st = result[step.id];
      if (st && !st.completed) {
        result[step.id] = { ...st, completed: true, active: false };
      }
    }
  }

  return result;
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StepIcon({ completed, active }: { completed: boolean; active: boolean }) {
  if (completed) {
    return (
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        background: 'rgba(11,232,129,0.15)',
        border: '2px solid #0BE881',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="#0BE881">
          <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
        </svg>
      </div>
    );
  }
  if (active) {
    return (
      <div style={{
        width: 28, height: 28, borderRadius: '50%',
        border: '2px solid #F99716',
        background: 'rgba(249,151,22,0.12)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
        position: 'relative',
      }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: '#F99716',
          animation: 'otp-pulse 1.5s ease-in-out infinite',
        }} />
        <style>{`
          @keyframes otp-pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.7); }
          }
        `}</style>
      </div>
    );
  }
  return (
    <div style={{
      width: 28, height: 28, borderRadius: '50%',
      border: '2px solid rgba(255,255,255,0.1)',
      background: 'rgba(255,255,255,0.03)',
      flexShrink: 0,
    }} />
  );
}

interface FinancingSectionProps {
  financing: Record<string, unknown> | null;
  tasks: OrderTask[];
}

function FinancingSection({ financing, tasks }: FinancingSectionProps) {
  const [expanded, setExpanded] = useState(false);

  const hasData = financing && Object.keys(financing).length > 0;
  const financingTasks = tasks.filter(t =>
    t.task_type?.toLowerCase().includes('financ') ||
    t.task_type?.toLowerCase().includes('loan') ||
    t.task_name?.toLowerCase().includes('financ') ||
    t.task_name?.toLowerCase().includes('loan') ||
    t.task_name?.toLowerCase().includes('bank')
  );

  if (!hasData && financingTasks.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 0', color: '#9B59B6',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Financing Details
        </span>
        <span style={{ fontSize: 12, color: '#86888f', transition: 'transform 0.2s', display: 'inline-block', transform: expanded ? 'rotate(180deg)' : 'none' }}>▼</span>
      </button>

      {expanded && (
        <div style={{
          background: 'rgba(155,89,182,0.06)',
          border: '1px solid rgba(155,89,182,0.15)',
          borderRadius: 8, padding: '10px 12px', marginTop: 4,
        }}>
          {financingTasks.length > 0 && (
            <div style={{ marginBottom: hasData ? 8 : 0 }}>
              {financingTasks.map((t, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 100,
                    background: t.completed ? 'rgba(11,232,129,0.1)' : 'rgba(255,255,255,0.05)',
                    color: t.completed ? '#0BE881' : '#86888f',
                  }}>{t.completed ? '✓' : '○'}</span>
                  <span style={{ fontSize: 12, color: t.completed ? '#f5f5f7' : '#86888f' }}>{t.task_name || t.task_type}</span>
                  {t.task_status && (
                    <span style={{ fontSize: 10, color: '#86888f', marginLeft: 'auto' }}>{t.task_status}</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {hasData && financing && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(financing).slice(0, 8).map(([k, v]) => v != null && v !== '' && (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ fontSize: 11, color: '#86888f', textTransform: 'capitalize' }}>
                    {k.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 11, color: '#f5f5f7', fontWeight: 500, textAlign: 'right', maxWidth: '60%', wordBreak: 'break-word' }}>
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export interface OrderProcessTrackerProps {
  orderStatus?: Record<string, unknown> | null;
  tasks?: OrderTask[];
  financing?: Record<string, unknown> | null;
  realStatus?: RealStatus | null;
  logistics?: DossierLogistics | null;
  runt?: RuntData | null;
  financial?: DossierFinancial | null;
  loading?: boolean;
}

export default function OrderProcessTracker({
  orderStatus = null,
  tasks = [],
  financing = null,
  realStatus = null,
  logistics = null,
  runt = null,
  loading = false,
}: OrderProcessTrackerProps) {
  const stepStates = resolveSteps(orderStatus, tasks, realStatus, logistics, runt, financing);

  const completedCount = ORDER_STEPS.filter(s => stepStates[s.id]?.completed).length;
  const totalCount = ORDER_STEPS.length;
  const progressPct = Math.round((completedCount / totalCount) * 100);

  // Group by category for section headers
  let lastCategory: StepCategory | null = null;

  if (loading) {
    return (
      <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
        <div style={{ color: '#86888f', fontSize: 13, textAlign: 'center' }}>Loading order process...</div>
      </div>
    );
  }

  return (
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#f5f5f7' }}>Order Process</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ fontSize: 11, color: '#86888f' }}>{completedCount}/{totalCount}</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#05C46B' }}>{progressPct}%</div>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.07)',
        marginBottom: 16, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: 2,
          width: `${progressPct}%`,
          background: 'linear-gradient(90deg, #0FBCF9, #05C46B)',
          transition: 'width 0.5s ease',
        }} />
      </div>

      {/* Steps */}
      <div style={{ position: 'relative' }}>
        {ORDER_STEPS.map((step, idx) => {
          const state = stepStates[step.id] || { completed: false, active: false };
          const showCategoryHeader = step.category !== lastCategory;
          lastCategory = step.category;
          const isLast = idx === ORDER_STEPS.length - 1;

          return (
            <React.Fragment key={step.id}>
              {showCategoryHeader && (
                <div style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: CATEGORY_COLORS[step.category],
                  marginTop: idx === 0 ? 0 : 10,
                  marginBottom: 6,
                  paddingLeft: 36,
                }}>
                  {CATEGORY_LABELS[step.category]}
                </div>
              )}

              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                paddingBottom: isLast ? 0 : 2,
                position: 'relative',
              }}>
                {/* Connector line */}
                {!isLast && (
                  <div style={{
                    position: 'absolute',
                    left: 13, top: 28, bottom: -2,
                    width: 2,
                    background: state.completed ? 'rgba(11,232,129,0.2)' : 'rgba(255,255,255,0.05)',
                    zIndex: 0,
                  }} />
                )}

                {/* Step icon */}
                <div style={{ position: 'relative', zIndex: 1 }}>
                  <StepIcon completed={state.completed} active={state.active} />
                </div>

                {/* Step content */}
                <div style={{ flex: 1, minWidth: 0, paddingTop: 3, paddingBottom: 3 }}>
                  <div style={{
                    fontSize: 13, fontWeight: state.completed ? 500 : 400,
                    color: state.completed ? '#f5f5f7' : state.active ? '#F99716' : 'rgba(255,255,255,0.35)',
                    lineHeight: 1.3,
                  }}>
                    {step.icon} {step.label}
                  </div>
                  {state.date && (
                    <div style={{ fontSize: 10, color: '#86888f', marginTop: 1 }}>{state.date}</div>
                  )}
                </div>

                {/* Status label */}
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  {state.completed ? (
                    <span style={{ fontSize: 10, color: '#0BE881', fontWeight: 600 }}>Done</span>
                  ) : state.active ? (
                    <span style={{ fontSize: 10, color: '#F99716', fontWeight: 600 }}>Active</span>
                  ) : (
                    <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)' }}>Pending</span>
                  )}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Financing expandable section */}
      <FinancingSection financing={financing} tasks={tasks} />
    </div>
  );
}
