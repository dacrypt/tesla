/** Tesla order tracking. */
import { client } from './http';
import type { OrderDetails, OrderStatus } from './types';

export const orderApi = {
  getOrderStatus: () => client().get<OrderStatus>('/api/order/status').then(r => r.data),
  getOrderDetails: () => client().get<OrderDetails>('/api/order/details', { timeout: 10000 }).then(r => r.data),
  getOrderSummary: () => client().get<{ summary: string; reservation_number: string }>('/api/order/summary').then(r => r.data),
  getOrderShareText: (includeVin = false) => client().get<{ text: string; summary: string }>('/api/order/share', { params: { include_vin: includeVin } }).then(r => r.data),
};
