/** Generic vehicle command payloads and acknowledgements. */

/** `{ ok }` acknowledgement returned by many mutating routes. */
export interface OkResponse {
  ok: boolean;
}

export interface CommandPayload {
  command: string;
  params?: Record<string, unknown>;
}

export interface CommandResult {
  success: boolean;
  message?: string;
  result?: unknown;
}
