/** Shapes shared between the Settings page and its sections. */

/** Show a toast; `color` is an Ionic color name ('success', 'danger', ...). */
export type Notify = (message: string, color: string) => void;

/** One row of `/api/doctor` (feature availability on this install). */
export interface FeatureHealth {
  name: string;
  tier: string;
  // tier "X" = experimental (unofficial/fragile upstream): failing | unused | not-installed
  status:
    | 'ok'
    | 'missing-scope'
    | 'external-blocker'
    | 'not-configured'
    | 'failing'
    | 'unused'
    | 'not-installed';
  remediation?: string;
}
