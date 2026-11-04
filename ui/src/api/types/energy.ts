/** Energy pricing (Colombian tariffs). */

export interface EnergyTariff {
  estrato: number;
  valor_kwh: number;
  empresa: string;
  municipio: string;
}

export interface EnergyTariffsResult {
  ciudad: string;
  estrato: number;
  tariffs: EnergyTariff[];
  total: number;
}

export interface EnergyCityTariff {
  estrato: number;
  valor_kwh: number;
}

export interface EnergyCityCompare {
  name: string;
  empresa: string;
  estratos: EnergyCityTariff[];
}

export interface EnergyCompareResult {
  cities: EnergyCityCompare[];
}

export interface EnergyVehicleLocationTariff {
  city: string;
  estrato: number;
  valor_kwh: number;
  empresa: string;
  municipio: string;
  location_source: string;
  lat: number | null;
  lon: number | null;
}
