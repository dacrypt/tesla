/** Climate state. */

export interface ClimateState {
  inside_temp?: number;
  outside_temp?: number;
  driver_temp_setting?: number;
  passenger_temp_setting?: number;
  is_climate_on?: boolean;
  seat_heater_left?: number;
  seat_heater_right?: number;
  seat_heater_rear_left?: number;
  seat_heater_rear_center?: number;
  seat_heater_rear_right?: number;
  steering_wheel_heater?: boolean;
  bioweapon_mode?: boolean;
  climate_keeper_mode?: string;
}
