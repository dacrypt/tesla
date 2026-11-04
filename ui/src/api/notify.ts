/** Apprise notification channels and history. */
import { client } from './http';
import type { CommandResult, NotificationEntry, NotifyChannels } from './types';

export const notifyApi = {
  getNotifyChannels: () => client().get<NotifyChannels>('/api/notify/list').then(r => r.data),
  sendNotifyTest: () => client().post<CommandResult>('/api/notify/test').then(r => r.data),
  addNotifyChannel: (url: string) => client().post<CommandResult>('/api/notify/add', { url }).then(r => r.data),
  removeNotifyChannel: (index: number) => client().post<CommandResult>('/api/notify/remove', { index }).then(r => r.data),
  getNotificationHistory: (limit = 20) => client().get<NotificationEntry[]>(`/api/notify/history?limit=${limit}`).then(r => r.data),
};
