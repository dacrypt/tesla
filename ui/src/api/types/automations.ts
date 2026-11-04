/** Geofences and automation rules. */

export interface GeofenceZone {
  name: string;
  lat: number;
  lon: number;
  radius_km: number;
  distance_km?: number;
  inside?: boolean;
}

export interface AutomationTrigger {
  type: string;
  threshold?: number | null;
  field?: string | null;
  from_value?: string | null;
  to_value?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  radius_km?: number;
  time?: string | null;
}

export interface AutomationAction {
  type: string;
  message?: string;
  command?: string;
  webhook_url?: string;
  webhook_payload?: string;
}

export interface AutomationCondition {
  field: string;
  operator: string;
  value: string;
}

export interface AutomationRule {
  name: string;
  enabled: boolean;
  trigger: AutomationTrigger;
  action: AutomationAction;
  conditions?: AutomationCondition[];
  last_fired?: string | null;
  cooldown_minutes?: number;
  delay_seconds?: number;
  retry_count?: number;
  retry_delay_seconds?: number;
}

export interface AutomationsStatus {
  total: number;
  enabled: number;
  disabled: number;
}
