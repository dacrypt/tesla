/** Energy pricing (Colombian tariffs). */
import { client } from './http';
import type { EnergyCompareResult, EnergyTariffsResult, EnergyVehicleLocationTariff } from './types';

export const energyApi = {
  getEnergyTariffs: (ciudad: string, estrato: number) =>
    client().get<EnergyTariffsResult>(`/api/energy/tariffs?ciudad=${encodeURIComponent(ciudad)}&estrato=${estrato}`).then(r => r.data),
  getEnergyTariffsCompare: () =>
    client().get<EnergyCompareResult>('/api/energy/tariffs/compare').then(r => r.data),
  getEnergyTariffsAtVehicle: () =>
    client().get<EnergyVehicleLocationTariff>('/api/energy/tariffs/vehicle-location').then(r => r.data),
};
