/** Mission Control read model, alerts and timeline events. */

export interface AlertEvent {
  alert_id: string;
  kind: string;
  source_id?: string | null;
  domain_id?: string | null;
  severity: string;
  title: string;
  message: string;
  created_at: string;
  acked_at?: string | null;
  resolved_at?: string | null;
}

export interface TimelineEvent {
  event_id?: string;
  kind: string;
  severity?: string;
  title: string;
  message: string;
  created_at?: string;
  timestamp?: string;
  source_id?: string;
  domain_id?: string;
}

export interface MissionControlExecutive {
  delivery_readiness: { status: string; summary: string };
  financial_state: { status: string; summary: string };
  legal_readiness: { status: string; summary: string };
  safety_posture: { status: string; summary: string };
  source_health: {
    status: string;
    ok_sources: number;
    total_sources: number;
    degraded_sources: string[];
  };
  active_alerts_count: number;
  last_successful_refresh: string | null;
}

/**
 * A domain projection's derived state (core/domains.py). The keys read by the
 * dashboard are typed; every domain adds its own extra keys.
 */
export interface MissionControlDomainState {
  vin?: string | null;
  plate?: string | null;
  order_status?: string | null;
  delivery_date?: string | null;
  estimated_delivery?: string | null;
  delivery_location?: string | null;
  ok_sources?: number;
  total_sources?: number;
  [key: string]: unknown;
}

/** Boolean flags derived per domain (e.g. `vin_assigned`, `plate_assigned`). */
export type MissionControlFlags = Record<string, boolean | null | undefined>;

/** Cached payload of a data source; shape depends on the source. */
export interface MissionControlSourceData {
  placa?: string;
  soat_vencimiento?: string;
  tecnomecanica_vencimiento?: string;
  vencimiento?: string;
  comparendos?: number;
  multas?: number;
  total_deuda?: number;
  paz_y_salvo?: boolean;
  [key: string]: unknown;
}

export interface MissionControlDomain {
  domain_id: string;
  computed_at: string;
  state: MissionControlDomainState;
  derived_flags: MissionControlFlags;
  summary: string;
  health: { status: string; ok_sources?: number; total_sources?: number; degraded_sources?: string[] };
}

export interface MissionControlSource {
  id: string;
  name: string;
  category?: string;
  refreshed_at?: string | null;
  stale?: boolean;
  error?: string | null;
  data?: MissionControlSourceData | null;
  changes?: Array<{ field: string; old?: string | null; new?: string | null }>;
}

export interface MissionControlData {
  generated_at: string;
  executive: MissionControlExecutive;
  domains: MissionControlDomain[];
  sources: MissionControlSource[];
  critical_diffs: Array<{
    source_id: string;
    source_name: string;
    changes_count: number;
    changes: Array<{ field: string; old?: string | null; new?: string | null }>;
    refreshed_at?: string | null;
  }>;
  timeline: TimelineEvent[];
  active_alerts: AlertEvent[];
}

/** /api/mission-control/dashboard-summary — the executive block, flattened. */
export interface DashboardSummary extends MissionControlExecutive {
  generated_at: string;
  critical_changes_count: number;
}
