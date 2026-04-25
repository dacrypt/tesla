-- TeslaMate `charges` table DDL snapshot (v1.30.x series).
--
-- Source: TeslaMate ecto migrations, which define the canonical shape of the
-- `charges` table. Captured as a snapshot for backend tests so that schema
-- drift is detected before it reaches production.
--
-- Reference: https://github.com/teslamate-org/teslamate (priv/repo/migrations/)
--
-- Only the columns used by `get_charge_curve` / `get_curve_stats` are required
-- for the backend to work; the full column list is kept here for context.
CREATE TABLE charges (
    id bigserial NOT NULL PRIMARY KEY,
    date timestamp(0) without time zone NOT NULL,
    battery_heater_on boolean,
    battery_heater boolean,
    battery_heater_no_power boolean,
    battery_level smallint,
    charge_energy_added numeric(8,2),
    charger_actual_current smallint,
    charger_phases smallint,
    charger_pilot_current smallint,
    charger_power smallint,
    charger_voltage smallint,
    conn_charge_cable text,
    fast_charger_present boolean,
    fast_charger_brand text,
    fast_charger_type text,
    ideal_battery_range_km numeric(6,2),
    not_enough_power_to_heat boolean,
    outside_temp numeric(4,1),
    charging_process_id integer NOT NULL REFERENCES charging_processes(id)
        ON DELETE CASCADE,
    battery_level_raw smallint,
    usable_battery_level smallint,
    rated_battery_range_km numeric(6,2)
);

CREATE INDEX charges_charging_process_id_index ON charges (charging_process_id);
CREATE INDEX charges_date_index ON charges (date);
