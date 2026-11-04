/** Server status, configuration and providers. */

export interface ServerStatus {
  version: string;
  backend: string;
  vin: string;
}

export interface TeslaConfig {
  backend?: string;
  default_vin?: string;
  tessie_token?: string;
  teslaMate_url?: string;
}

export interface ProviderStatus {
  name: string;
  available: boolean;
  layer?: string;
  priority?: number;
  capabilities?: string[];
  description?: string;
  message?: string;
}
