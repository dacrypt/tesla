/** Climate state and commands. */
import { client } from './http';
import type { ClimateState, CommandResult } from './types';

export const climateApi = {
  getClimateState: () => client().get<ClimateState>('/api/climate/status').then(r => r.data),
  getClimateVehicle: () => client().get<ClimateState>('/api/vehicle/climate').then(r => r.data),
  climateOn: () => client().post<CommandResult>('/api/climate/on').then(r => r.data),
  climateOff: () => client().post<CommandResult>('/api/climate/off').then(r => r.data),
  setTemps: (driver_temp: number, passenger_temp: number) =>
    client().post<CommandResult>('/api/climate/temp', { driver_temp, passenger_temp }).then(r => r.data),
};
