/**
 * Shared SSE connection to the VehicleStateHub.
 *
 * Single EventSource for the entire app. Hooks subscribe to specific
 * event types via addEventListener. Reconnects with exponential backoff.
 */
import { api } from '../api/client';

let _es: EventSource | null = null;
let _retryCount = 0;
let _retryTimeout: ReturnType<typeof setTimeout> | null = null;
let _stopped = false;

type Listener = (evt: MessageEvent) => void;
const _listeners: Map<string, Set<Listener>> = new Map();

function _connect() {
  if (_stopped || _es) return;

  _es = new EventSource(api.getStreamUrl());

  _es.onopen = () => {
    _retryCount = 0;
  };

  // Route events to registered listeners
  for (const eventType of ['vehicle', 'source', 'error']) {
    _es.addEventListener(eventType, ((evt: MessageEvent) => {
      const listeners = _listeners.get(eventType);
      if (listeners) {
        listeners.forEach(fn => fn(evt));
      }
    }) as EventListener);
  }

  _es.onerror = () => {
    _es?.close();
    _es = null;
    if (!_stopped) {
      const delay = Math.min(1000 * Math.pow(2, _retryCount), 30000);
      _retryTimeout = setTimeout(() => {
        _retryCount++;
        _connect();
      }, delay);
    }
  };
}

/** Subscribe to an SSE event type. Returns an unsubscribe function. */
export function subscribe(eventType: string, listener: Listener): () => void {
  if (!_listeners.has(eventType)) {
    _listeners.set(eventType, new Set());
  }
  _listeners.get(eventType)!.add(listener);

  // Start connection on first subscriber
  if (!_es && !_stopped) {
    _connect();
  }

  return () => {
    const set = _listeners.get(eventType);
    if (set) {
      set.delete(listener);
      // If no listeners left for any event, close the connection
      let total = 0;
      _listeners.forEach(s => total += s.size);
      if (total === 0) {
        _stop();
      }
    }
  };
}

/** Stop the shared SSE connection and prevent reconnects. */
export function stop() {
  _stopped = true;
  _stop();
}

function _stop() {
  if (_retryTimeout) clearTimeout(_retryTimeout);
  if (_es) {
    _es.close();
    _es = null;
  }
}

/** Check if the SSE connection is currently open. */
export function isConnected(): boolean {
  return _es?.readyState === EventSource.OPEN;
}
