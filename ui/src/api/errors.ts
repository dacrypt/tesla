/**
 * Helpers to read thrown values without `any`.
 *
 * Works structurally (not via `axios.isAxiosError`) so plain-object rejections,
 * e.g. test mocks like `{ response: { status: 401 } }`, are handled the same way.
 */

function field(value: unknown, key: string): unknown {
  return typeof value === 'object' && value !== null
    ? (value as Record<string, unknown>)[key]
    : undefined;
}

/** `e.message` when the thrown value carries a string message. */
export function errorMessageOf(e: unknown): string | undefined {
  const message = field(e, 'message');
  return typeof message === 'string' ? message : undefined;
}

/** FastAPI's `response.data.detail` from an axios error, when it is a string. */
export function errorDetailOf(e: unknown): string | undefined {
  const detail = field(field(field(e, 'response'), 'data'), 'detail');
  return typeof detail === 'string' ? detail : undefined;
}

/** HTTP status of an axios error response, if any. */
export function errorStatusOf(e: unknown): number | undefined {
  const status = field(field(e, 'response'), 'status');
  return typeof status === 'number' ? status : undefined;
}

/** Equivalent of the legacy `e.message || e`: the message, else the value stringified. */
export function describeError(e: unknown): string {
  return errorMessageOf(e) || String(e);
}
