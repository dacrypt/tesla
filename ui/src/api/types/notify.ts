/** Apprise notification channels and history. */

/** /api/notify/list */
export interface NotifyChannels {
  enabled: boolean;
  channels: string[];
  template: string;
}

/** One line of the notification history JSONL log (/api/notify/history). */
export interface NotificationEntry {
  timestamp: string;
  title: string;
  message: string;
  channel: string;
  success: boolean;
}
