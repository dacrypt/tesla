/** Tesla order status and details. */

export interface OrderStatus {
  order_id?: string;
  status?: string;
  vin?: string;
  estimated_delivery?: string;
  delivery_appointment?: string;
  model?: string;
  trim?: string;
  color?: string;
  gates?: Record<string, boolean>;
}

export interface OrderTask {
  task_type: string;
  task_status: string;
  task_name: string;
  completed: boolean;
  active: boolean;
  details?: Record<string, unknown>;
}

export interface OrderDetails {
  status: OrderStatus;
  tasks: OrderTask[];
  financing: Record<string, unknown>;
  registration: Record<string, unknown>;
  delivery: Record<string, unknown>;
  vehicle_info: Record<string, unknown>;
}
