"""Dossier backend — aggregates ALL data sources into a single vehicle dossier.

Sources:
- Tesla Owner API (order, account, feature config)
- NHTSA vPIC API (VIN decode for US-registered VINs)
- Tesla VIN Recall Search
- Ship tracking (shipinfo.net scraping)
- Local VIN decode (built-in decoder for all VINs including non-US)
- Historical archive (JSON snapshots on disk)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

from tesla_cli.core.config import load_config

logger = logging.getLogger(__name__)
from tesla_cli.core.models.dossier import (
    Logistics,
    OptionCode,
    OptionCodes,
    OrderSnapshot,
    OrderTimeline,
    RealStatus,
    Recall,
    ShipPosition,
    ShipTracking,
    TeslaAccount,
    VehicleDossier,
    VehicleSpecs,
    VinDecode,
)

# Archive location
ARCHIVE_DIR = Path.home() / ".tesla-cli" / "dossier"
DOSSIER_FILE = ARCHIVE_DIR / "dossier.json"
SNAPSHOTS_DIR = ARCHIVE_DIR / "snapshots"


# ── VIN Decoder (built-in, works for all VINs) ─────────────────────────────

# Position 1-3: World Manufacturer Identifier
WMI_MAP = {
    "5YJ": "Tesla Inc. (Fremont, CA)",
    "7SA": "Tesla Inc. (Fremont, CA)",
    "LRW": "Tesla Inc. (Shanghai, China)",
    "XP7": "Tesla Inc. (Berlin, Germany)",
    "SFZ": "Tesla Inc. (Tilburg, Netherlands)",
    "7G2": "Tesla Inc. (Austin, TX)",
}

# Position 4: Model
MODEL_MAP = {
    "S": "Model S",
    "3": "Model 3",
    "X": "Model X",
    "Y": "Model Y",
    "C": "Cybertruck",
    "R": "Roadster",
    "T": "Semi",
}

# Position 5: Body type
BODY_MAP = {
    "A": "Hatchback (5-door)",
    "B": "Hatchback (5-door)",
    "C": "MPV (5-door)",
    "D": "MPV (5-door)",
    "E": "Sedan (4-door)",
    "F": "Sedan (4-door)",
    "G": "SUV/Crossover (5-door)",
    "H": "SUV/Crossover (5-door)",
    "N": "Pickup",
}

# Position 6: Restraint system
RESTRAINT_MAP = {
    "A": "Manual Type 2 belts, front+knee airbags, side+curtain",
    "B": "Manual Type 2 belts, front+knee airbags, side+curtain",
    "C": "Manual Type 2 belts, front airbags, side inflatable",
    "D": "Manual Type 2 belts, front airbags, side inflatable",
    "F": "Manual Type 2 belts, front+knee airbags, side+curtain+pelvic",
}

# Position 7: Energy/battery type
ENERGY_MAP = {
    "E": "Electric (NMC/NCA battery)",
    "F": "Electric (LFP battery)",
    "H": "Electric (High Voltage NMC)",
}

# Position 8: Motor/battery config (evolves with new models)
MOTOR_MAP = {
    "1": "Single Motor (Standard Range)",
    "3": "Single Motor (Standard Range+)",
    "4": "Dual Motor (Long Range)",
    "A": "Dual Motor (Performance/Plaid)",
    "B": "Dual Motor (Long Range AWD)",
    "C": "Dual Motor (Performance)",
    "E": "Dual Motor (Standard AWD)",
    "F": "Performance / Dual Motor",
    "K": "Dual Motor Long Range (Juniper 2025+)",
    "P": "Performance (Plaid)",
    "S": "Standard Range Plus (CATL LFP)",
}

# Position 10: Model year
YEAR_MAP = {
    "A": "2010", "B": "2011", "C": "2012", "D": "2013", "E": "2014",
    "F": "2015", "G": "2016", "H": "2017", "J": "2018", "K": "2019",
    "L": "2020", "M": "2021", "N": "2022", "P": "2023", "R": "2024",
    "S": "2025", "T": "2026", "V": "2027", "W": "2028", "X": "2029",
    "Y": "2030",
}

# Position 11: Plant
PLANT_MAP = {
    "A": "Austin, TX (Gigafactory Texas)",
    "B": "Berlin, Germany (Gigafactory Berlin)",
    "C": "Shanghai, China (Gigafactory 3)",
    "F": "Fremont, CA",
    "K": "Sparks, NV (Gigafactory 1)",
    "R": "Reno, NV",
    "T": "Tilburg, Netherlands",
}

# ── Option Code Decoder ─────────────────────────────────────────────────────

OPTION_CODE_MAP: dict[str, tuple[str, str, str]] = {
    # ── Model ───────────────────────────────────────────────────────────────
    "MDLS":  ("model", "Model S", "Model S"),
    "MDL3":  ("model", "Model 3", "Model 3"),
    "MDLX":  ("model", "Model X", "Model X"),
    "MDLY":  ("model", "Model Y", "Model Y"),
    "MDLCT": ("model", "Cybertruck", "Cybertruck"),
    "MDLRD": ("model", "Roadster", "Roadster"),
    "MDLSM": ("model", "Semi", "Semi"),

    # ── Motor / Drivetrain ───────────────────────────────────────────────────
    "MTY62": ("motor", "Dual Motor Long Range (Y-62)", "Dual Motor Long Range (Y-62)"),
    "MT300": ("motor", "Standard Range RWD", "Tracción trasera alcance estándar"),
    "MT301": ("motor", "Standard Range Plus", "Standard Range Plus"),
    "MT314": ("motor", "Long Range AWD", "Long Range AWD"),
    "MT320": ("motor", "Performance AWD", "Performance AWD"),
    "MTPB":  ("motor", "Plaid (tri-motor)", "Plaid (tres motores)"),
    "MTSB":  ("motor", "Standard Range", "Alcance Estándar"),
    "MTLB":  ("motor", "Long Range", "Alcance Largo"),
    "MTY01": ("motor", "Standard Range (Model Y)", "Alcance Estándar (Model Y)"),
    "MTY02": ("motor", "Long Range AWD (Model Y)", "Long Range AWD (Model Y)"),
    "MTY03": ("motor", "Performance (Model Y)", "Performance (Model Y)"),
    "MTY04": ("motor", "Long Range RWD (Model Y)", "Long Range Trasera (Model Y)"),

    # ── Paint ────────────────────────────────────────────────────────────────
    "PN00":  ("paint", "Obsidian Black", "Negro Obsidiana"),
    "PN01":  ("paint", "Stealth Grey", "Gris Stealth"),
    "PN02":  ("paint", "Midnight Cherry", "Cereza Medianoche"),
    "PB00":  ("paint", "Solid Black", "Negro Sólido"),
    "PB01":  ("paint", "Silver Metallic", "Plata Metálico"),
    "PBCW":  ("paint", "Catalina White", "Blanco Catalina"),
    "PBSB":  ("paint", "Solid Black", "Negro Sólido"),
    "PMAB":  ("paint", "Icy White Multi-Coat", "Blanco Helado Multi-Capa"),
    "PMMB":  ("paint", "Midnight Silver Metallic", "Plata Medianoche Metálico"),
    "PMNG":  ("paint", "Midnight Cherry Red", "Rojo Cereza Medianoche"),
    "PPMR":  ("paint", "Red Multi-Coat", "Rojo Multi-Capa"),
    "PPSB":  ("paint", "Obsidian Black Metallic", "Negro Obsidiana Metálico"),
    "PPSR":  ("paint", "Signature Red", "Rojo Signature"),
    "PPSW":  ("paint", "Pearl White Multi-Coat", "Blanco Perla Multi-Capa"),
    "PPTI":  ("paint", "Titanium Metallic", "Titanio Metálico"),
    "PX00":  ("paint", "Pearl White", "Blanco Perla"),
    "PX01":  ("paint", "Ultra Red", "Rojo Ultra"),
    "PX02":  ("paint", "Quicksilver", "Quicksilver"),
    "PMSS":  ("paint", "Sand Silver", "Plata Arena"),
    "PPSM":  ("paint", "Midnight Silver Metallic", "Plata Medianoche"),
    "PMBL":  ("paint", "Blue Metallic", "Azul Metálico"),
    "PPSDB": ("paint", "Deep Blue Metallic", "Azul Profundo Metálico"),
    "PPNG":  ("paint", "Midnight Cherry Multi-Coat", "Cereza Medianoche Multi-Capa"),
    "PMTG":  ("paint", "Midnight Blue Metallic", "Azul Medianoche Metálico"),
    "PMSTG": ("paint", "Stealth Grey", "Gris Stealth"),
    "PMWH":  ("paint", "Pearl White Multi-Coat", "Blanco Perla Multi-Capa"),
    "PF00":  ("paint", "Black (standard)", "Negro (estándar)"),
    "LTSB":  ("paint", "Signature Black", "Negro Signature"),

    # ── Interior ─────────────────────────────────────────────────────────────
    "IPB0":  ("interior", "Premium Black", "Interior Premium Negro"),
    "IPB1":  ("interior", "Premium Black", "Interior Premium Negro"),
    "IPB12": ("interior", "Premium Black Gen 12 (Juniper)", "Interior Premium Negro Gen 12 (Juniper)"),
    "IPW0":  ("interior", "Premium White", "Interior Premium Blanco"),
    "IPW1":  ("interior", "Premium White", "Interior Premium Blanco"),
    "IPW12": ("interior", "Premium White Gen 12 (Juniper)", "Interior Premium Blanco Gen 12 (Juniper)"),
    "IBB0":  ("interior", "Standard Black", "Interior Estándar Negro"),
    "IBW0":  ("interior", "Standard White", "Interior Estándar Blanco"),
    "ITPB":  ("interior", "Black and White", "Interior Negro y Blanco"),
    "ITPW":  ("interior", "Premium White", "Interior Premium Blanco"),
    "INPB0": ("interior", "Next Gen Black", "Interior Nueva Gen Negro"),
    "INPW0": ("interior", "Next Gen White", "Interior Nueva Gen Blanco"),
    "RFPX":  ("interior", "Glass Roof", "Techo de Vidrio"),
    "RF3G":  ("interior", "Fixed Glass Roof", "Techo Fijo de Vidrio"),
    "RFBK":  ("interior", "Black Roof", "Techo Negro"),
    "RFP2":  ("interior", "Panoramic Roof", "Techo Panorámico"),
    "RFPO":  ("interior", "Panoramic Roof", "Techo Panorámico"),
    "RFSG":  ("interior", "Panoramic Sunroof", "Techo Solar Panorámico"),

    # ── Wheels ───────────────────────────────────────────────────────────────
    "WY18B": ("wheels", "18\" Aero", "Rines 18\" Aero"),
    "WY19P": ("wheels", "19\" Gemini", "Rines 19\" Gemini"),
    "WY19J": ("wheels", "19\" Gemini (Juniper)", "Rines 19\" Gemini (Juniper)"),
    "WY20A": ("wheels", "20\" Induction", "Rines 20\" Induction"),
    "WY20P": ("wheels", "20\" Performance", "Rines 20\" Performance"),
    "W38B":  ("wheels", "18\" Aero", "Rines 18\" Aero"),
    "W39B":  ("wheels", "19\" Sport", "Rines 19\" Sport"),
    "W40B":  ("wheels", "19\" Gemini", "Rines 19\" Gemini"),
    "W41B":  ("wheels", "20\" Überturbine", "Rines 20\" Überturbine"),
    "WT20P": ("wheels", "20\" Tempest", "Rines 20\" Tempest"),
    "WT22B": ("wheels", "22\" Turbine", "Rines 22\" Turbine"),
    "WX20P": ("wheels", "20\" Plaid", "Rines 20\" Plaid"),
    "WS90":  ("wheels", "19\" Slipstream", "Rines 19\" Slipstream"),
    "WT19B": ("wheels", "19\" Sonic Carbon Twin Turbine", "Rines 19\" Sonic Carbon"),
    "WX19B": ("wheels", "19\" Cyberstream", "Rines 19\" Cyberstream"),

    # ── Seats / Configuration ────────────────────────────────────────────────
    "STY5S": ("seats", "5-Seat", "5 Asientos"),
    "STY7S": ("seats", "7-Seat (3rd row)", "7 Asientos (3a fila)"),
    "ST0Y":  ("seats", "5-Seat", "5 Asientos"),
    "ST01":  ("seats", "5-Seat Standard", "5 Asientos Estándar"),
    "ST02":  ("seats", "7-Seat", "7 Asientos"),
    "ST03":  ("seats", "6-Seat (captain's chairs)", "6 Asientos (sillas capitán)"),
    "STC6":  ("seats", "6-Seat", "6 Asientos"),
    "STS6":  ("seats", "6-Seat Premium", "6 Asientos Premium"),
    "STS7":  ("seats", "7-Seat Premium", "7 Asientos Premium"),
    "STCF":  ("seats", "5-Seat Carbon Fiber Trim", "5 Asientos Fibra de Carbono"),

    # ── Autopilot / FSD ──────────────────────────────────────────────────────
    "APFA":  ("autopilot", "Autopilot (TACC + Autosteer)", "Autopilot (TACC + Autosteer)"),
    "APFB":  ("autopilot", "Autopilot (TACC + Autosteer)", "Autopilot (TACC + Autosteer)"),
    "APF0":  ("autopilot", "No Autopilot", "Sin Autopilot"),
    "APF1":  ("autopilot", "Enhanced Autopilot", "Autopilot Mejorado"),
    "APF2":  ("autopilot", "Full Self-Driving (FSD)", "Conducción Autónoma Completa (FSD)"),
    "APF3":  ("autopilot", "FSD Supervised", "FSD Supervisado"),
    "APH1":  ("autopilot", "Autopilot HW1.0", "Autopilot HW1.0"),
    "APH2":  ("autopilot", "Autopilot HW2.0", "Autopilot HW2.0"),
    "APH3":  ("autopilot", "Autopilot HW3.0", "Autopilot HW3.0"),
    "APH4":  ("autopilot", "Autopilot HW4.0 (AI4)", "Autopilot HW4.0 (AI4)"),
    "APPA":  ("autopilot", "Autopilot", "Autopilot"),
    "APPF":  ("autopilot", "FSD Capability", "FSD Capacidad"),
    "CTML":  ("autopilot", "Full Self-Driving (Supervised)", "FSD Supervisado"),
    "FSD2":  ("autopilot", "Full Self-Driving v2", "FSD v2"),

    # ── Charging ─────────────────────────────────────────────────────────────
    "SC00":  ("charging", "Free Supercharging Unlimited", "Supercharging Ilimitado Gratis"),
    "SC01":  ("charging", "Free Supercharging (limited)", "Supercharging Gratis (limitado)"),
    "SC04":  ("charging", "Pay Per Use Supercharging", "Supercharging de Pago"),
    "SC05":  ("charging", "Free Supercharging (transferable)", "Supercharging Gratis (transferible)"),
    "CON1":  ("charging", "Mobile Connector included", "Cable Móvil incluido"),
    "PL31":  ("charging", "J1772 Adapter", "Adaptador J1772"),
    "CHT0":  ("charging", "NACS/Tesla Charging", "Carga NACS/Tesla"),
    "CH04":  ("charging", "CCS (AC/DC) Charging", "Carga CCS (AC/DC)"),
    "CH05":  ("charging", "Type 2 Charging (EU)", "Carga Tipo 2 (EU)"),
    "CH06":  ("charging", "GB/T Charging (China)", "Carga GB/T (China)"),

    # ── Connectivity ─────────────────────────────────────────────────────────
    "CPF0":  ("connectivity", "Standard Connectivity", "Conectividad Estándar"),
    "CPF1":  ("connectivity", "Premium Connectivity (trial)", "Conectividad Premium (prueba)"),
    "CP00":  ("connectivity", "Standard Connectivity", "Conectividad Estándar"),
    "CP01":  ("connectivity", "Premium Connectivity", "Conectividad Premium"),
    "CPW1":  ("connectivity", "Wi-Fi Hotspot", "Punto de Acceso Wi-Fi"),
    "BT37":  ("connectivity", "Bluetooth 5.0", "Bluetooth 5.0"),

    # ── Features / Safety ────────────────────────────────────────────────────
    "ADM4":  ("feature", "Air Suspension (Adaptive)", "Suspensión Neumática Adaptativa"),
    "AU3P":  ("feature", "Ultra High Fidelity Sound System", "Sistema de Sonido Ultra Alta Fidelidad"),
    "BC3B":  ("feature", "12V Battery (lead-acid)", "Batería 12V (plomo-ácido)"),
    "BC3R":  ("feature", "12V LFP Battery", "Batería 12V LFP"),
    "BP00":  ("feature", "No Rear Bumper", "Sin Paragolpes Trasero"),
    "BP01":  ("feature", "Standard Bumper", "Paragolpes Estándar"),
    "CDM1":  ("feature", "One Pedal Driving (hold mode)", "Manejo un pedal (modo hold)"),
    "CID7":  ("feature", "17\" Touchscreen", "Pantalla táctil 17\""),
    "CID8":  ("feature", "15.4\" Touchscreen", "Pantalla táctil 15.4\""),
    "CID9":  ("feature", "8\" Rear Touchscreen", "Pantalla táctil trasera 8\""),
    "CODE":  ("feature", "Standard (base model)", "Estándar (modelo base)"),
    "DA01":  ("feature", "Dog Mode", "Modo Perro"),
    "DA02":  ("feature", "Dog Mode + Camp Mode", "Modo Perro + Modo Camping"),
    "DCF0":  ("feature", "No Dog Mode", "Sin Modo Perro"),
    "DF01":  ("feature", "Front Door (standard)", "Puerta Delantera Estándar"),
    "DV4W":  ("feature", "Homelink (standard)", "Homelink Estándar"),
    "DV2W":  ("feature", "Homelink (base)", "Homelink Base"),
    "FC3P":  ("feature", "Frunk (front trunk)", "Maletero Frontal"),
    "FG00":  ("feature", "No Falcon Doors", "Sin Puertas Falcon"),
    "FG02":  ("feature", "Falcon Wing Doors", "Puertas Falcon"),
    "FL01":  ("feature", "Front Fog Lights", "Luces Antiniebla Delanteras"),
    "FR01":  ("feature", "Sport Front Seats (heated)", "Asientos Deportivos Delanteros (calefacción)"),
    "FR02":  ("feature", "Premium Front Seats (heated + ventilated)", "Asientos Premium Delanteros (calef. + ventilación)"),
    "GB00":  ("feature", "No Third Row Seats", "Sin 3a Fila"),
    "GB01":  ("feature", "Third Row Seats (Model Y)", "3a Fila (Model Y)"),
    "HL31":  ("feature", "Standard Headlights", "Faros Estándar"),
    "HL32":  ("feature", "LED Headlights (matrix)", "Faros LED Matriciales"),
    "HM31":  ("feature", "HomeLink Gen 3", "HomeLink Gen 3"),
    "IL31":  ("feature", "Standard Interior Lighting", "Iluminación Interior Estándar"),
    "IL32":  ("feature", "Interior Ambient Lighting (18 LEDs)", "Iluminación Ambiental (18 LEDs)"),
    "LT00":  ("feature", "No Leather", "Sin Cuero"),
    "LT01":  ("feature", "Leather Steering Wheel", "Volante de Cuero"),
    "LT05":  ("feature", "Textile Steering Wheel", "Volante Textil"),
    "MR31":  ("feature", "Standard Mirrors", "Espejos Estándar"),
    "MR32":  ("feature", "Auto-Dimming + Heated Mirrors", "Espejos Atenuación Automática + Calefacción"),
    "PI00":  ("feature", "No Power Liftgate", "Sin Portón Eléctrico"),
    "PI01":  ("feature", "Power Liftgate", "Portón Eléctrico"),
    "PK00":  ("feature", "No Rear Spoiler", "Sin Alerón Trasero"),
    "PK01":  ("feature", "Rear Spoiler", "Alerón Trasero"),
    "PL31F": ("feature", "J1772 Charging Adapter", "Adaptador de Carga J1772"),
    "PS00":  ("feature", "No Parcel Shelf", "Sin Bandeja Trasera"),
    "PS01":  ("feature", "Parcel Shelf (fold-down)", "Bandeja Trasera (plegable)"),
    "RS3H":  ("feature", "Rear Seats (heated)", "Asientos Traseros (calefacción)"),
    "SA3P":  ("feature", "Air Suspension", "Suspensión Neumática"),
    "SB00":  ("feature", "No Power Sideboards", "Sin Estribos Eléctricos"),
    "SB01":  ("feature", "Power Sideboards (Model X)", "Estribos Eléctricos (Model X)"),
    "STCP":  ("feature", "Carbon Fiber Spoiler", "Alerón Fibra de Carbono"),
    "SU3C":  ("feature", "Coil Spring Suspension", "Suspensión con Resorte"),
    "TM00":  ("feature", "No Tow Package", "Sin Paquete Remolque"),
    "TM0A":  ("feature", "Tow Package", "Paquete de Remolque"),
    "TP03":  ("feature", "TPMS (tire pressure monitoring)", "Monitor Presión Neumáticos"),
    "TR00":  ("feature", "No Tow Hitch", "Sin Enganche"),
    "TR01":  ("feature", "Tow Hitch Receiver", "Enganche Receptor"),
    "TR02":  ("feature", "Deployable Tow Hitch", "Enganche Desplegable"),
    "UT3P":  ("feature", "Ultra High Fidelity Sound (Plaid)", "Sonido Ultra Alta Fidelidad (Plaid)"),
    "WR00":  ("feature", "Standard Wiper (no heated)", "Limpiaparabrisas Estándar"),
    "WR02":  ("feature", "Heated Windshield Wiper Area", "Limpiaparabrisas con Calefacción"),
    "X001":  ("feature", "Body Color Roof", "Techo Color Carrocería"),
    "X003":  ("feature", "Sunroof", "Techo Solar"),
    "X007":  ("feature", "Fog Lamps", "Luces Antiniebla"),
    "X010":  ("feature", "Autopilot Convenience", "Conveniencia Autopilot"),
    "X011":  ("feature", "Autopilot Safety", "Seguridad Autopilot"),
    "X014":  ("feature", "4G LTE + Wi-Fi", "4G LTE + Wi-Fi"),
    "X019":  ("feature", "Carbon Fiber Spoiler Package", "Paquete Alerón Fibra Carbono"),
    "X024":  ("feature", "Parking Sensors", "Sensores de Estacionamiento"),
    "X025":  ("feature", "Park Assist (auto)", "Asistente de Estacionamiento"),
    "X027":  ("feature", "Lighted Door Handles", "Manijas Iluminadas"),
    "X028":  ("feature", "Driver + Passenger Heated Seats", "Asientos Calef. Conductor y Pasajero"),
    "X030":  ("feature", "Dog Mode", "Modo Perro"),
    "X037":  ("feature", "Subzero Weather Package", "Paquete Clima Extremo"),
    "X040":  ("feature", "Rear Facing Seats", "Asientos Orientados Hacia Atrás"),
    "X044":  ("feature", "All-Weather Interior", "Interior Todo Clima"),
    "ZCAL":  ("feature", "California Emissions", "Emisiones California"),
    "ZFWD":  ("feature", "Front-Wheel Drive", "Tracción Delantera"),
    "ZRWD":  ("feature", "Rear-Wheel Drive", "Tracción Trasera"),
    "ZAWD":  ("feature", "All-Wheel Drive", "Tracción Total"),
}


def decode_vin(vin: str) -> VinDecode:
    """Decode a Tesla VIN into structured data."""
    if len(vin) < 17:
        return VinDecode(vin=vin)

    wmi = vin[0:3]
    pos7 = vin[6]
    pos8 = vin[7]
    pos10 = vin[9]
    pos11 = vin[10]

    # Determine battery chemistry from position 7 and plant
    if pos7 == "E":
        battery = "NMC/NCA (high energy density)"
    elif pos7 == "F":
        battery = "LFP (lithium iron phosphate)"
    elif pos7 == "H":
        battery = "NMC High Voltage"
    else:
        battery = "Unknown"

    # Plant country from WMI
    plant_country = "Unknown"
    if wmi.startswith("5") or wmi.startswith("7"):
        plant_country = "United States"
    elif wmi.startswith("L"):
        plant_country = "China"
    elif wmi.startswith("X"):
        plant_country = "Germany"
    elif wmi.startswith("S"):
        plant_country = "Netherlands/UK"

    return VinDecode(
        vin=vin,
        manufacturer=WMI_MAP.get(wmi, f"Unknown ({wmi})"),
        model=MODEL_MAP.get(vin[3], f"Unknown ({vin[3]})"),
        body_type=BODY_MAP.get(vin[4], f"Unknown ({vin[4]})"),
        restraint_system=RESTRAINT_MAP.get(vin[5], f"Unknown ({vin[5]})"),
        energy_type=ENERGY_MAP.get(pos7, f"Unknown ({pos7})"),
        motor_battery=MOTOR_MAP.get(pos8, f"Unknown ({pos8})"),
        check_digit=vin[8],
        model_year=YEAR_MAP.get(pos10, f"Unknown ({pos10})"),
        plant=PLANT_MAP.get(pos11, f"Unknown ({pos11})"),
        serial_number=vin[11:17],
        plant_country=plant_country,
        battery_chemistry=battery,
    )


def decode_option_codes(raw: str) -> OptionCodes:
    """Decode comma-separated option codes."""
    codes = []
    for code in raw.split(","):
        code = code.strip()
        if not code:
            continue
        if code in OPTION_CODE_MAP:
            cat, desc_en, desc_es = OPTION_CODE_MAP[code]
            codes.append(OptionCode(
                code=code, category=cat,
                description=desc_en, description_es=desc_es,
            ))
        else:
            codes.append(OptionCode(code=code, category="unknown", description=f"Unknown ({code})"))
    return OptionCodes(raw_string=raw, codes=codes)


# ── NHTSA API (delegated to openquery) ────────────────────────────────────


def fetch_nhtsa_decode(vin: str) -> dict[str, str]:
    """Fetch VIN decode from NHTSA via openquery (us.nhtsa_vin)."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("us.nhtsa_vin")
        result = src.query(QueryInput(document_type=DocumentType.VIN, document_number=vin))
        return result.all_fields
    except ImportError:
        logger.warning("openquery not installed, falling back to direct NHTSA call")
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json")
                if resp.status_code == 200:
                    data = resp.json()
                    return {item["Variable"]: item["Value"] for item in data.get("Results", [])
                            if item.get("Value") and item["Value"].strip()}
        except Exception:
            logger.warning("NHTSA VIN decode failed", exc_info=True)
    except Exception:
        logger.warning("NHTSA VIN decode via openquery failed", exc_info=True)
    return {}


def fetch_nhtsa_recalls(make: str, model: str, year: str) -> list[dict]:
    """Fetch recalls from NHTSA via openquery (us.nhtsa_recalls)."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("us.nhtsa_recalls")
        result = src.query(QueryInput(
            document_type=DocumentType.CUSTOM,
            document_number=f"{make}-{model}-{year}",
            extra={"make": make, "model": model, "year": year},
        ))
        # Convert back to raw dict format for compatibility
        return [
            {
                "NHTSACampaignNumber": r.campaign_number,
                "ReportReceivedDate": r.date_reported,
                "Component": r.component,
                "Summary": r.summary,
                "Consequence": r.consequence,
                "Remedy": r.remedy,
                "Manufacturer": r.manufacturer,
                "Notes": r.notes,
            }
            for r in result.recalls
        ]
    except ImportError:
        logger.warning("openquery not installed, falling back to direct NHTSA call")
        try:
            url = f"https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}"
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.json().get("results", [])
        except Exception:
            logger.warning("NHTSA recalls fetch failed", exc_info=True)
    except Exception:
        logger.warning("NHTSA recalls via openquery failed", exc_info=True)
    return []


# ── Tesla Recall Check ──────────────────────────────────────────────────────


def fetch_tesla_recalls(vin: str) -> list[Recall]:
    """Check Tesla's own recall search (web scraping fallback)."""
    recalls: list[Recall] = []
    # Tesla's recall API requires browser context; we check NHTSA instead
    nhtsa = fetch_nhtsa_recalls("TESLA", "Model Y", "2026")
    for r in nhtsa:
        recalls.append(Recall(
            recall_id=r.get("NHTSACampaignNumber", ""),
            date=r.get("ReportReceivedDate", ""),
            description=r.get("Summary", ""),
            component=r.get("Component", ""),
            remedy=r.get("Remedy", ""),
            status="open",
            nhtsa_id=r.get("NHTSACampaignNumber", ""),
            source="nhtsa",
        ))
    return recalls


# ── Ship Tracking ───────────────────────────────────────────────────────────


def fetch_tesla_ships() -> list[ShipTracking]:
    """Fetch Tesla car carrier positions via openquery (intl.ship_tracking)."""
    try:
        from openquery.sources import get_source
        from openquery.sources.base import DocumentType, QueryInput

        src = get_source("intl.ship_tracking")
        # Search for known Tesla carriers
        for carrier_name in ["Grand Venus", "Silver Glory", "SFL Composer"]:
            result = src.query(QueryInput(
                document_type=DocumentType.CUSTOM,
                document_number=carrier_name,
                extra={"vessel_name": carrier_name},
            ))
            if result.vessels:
                ships = []
                for v in result.vessels:
                    ships.append(ShipTracking(
                        vessel_name=v.name,
                        imo=v.imo,
                        mmsi=v.mmsi,
                        current_position=ShipPosition(
                            latitude=v.position.latitude,
                            longitude=v.position.longitude,
                            speed_knots=v.position.speed_knots,
                            course=v.position.course,
                        ),
                        tracking_url=v.tracking_url,
                    ))
                return ships
    except ImportError:
        logger.warning("openquery not installed, using fallback ship data")
    except Exception:
        logger.warning("Ship tracking via openquery failed", exc_info=True)

    return _known_tesla_carriers()


def _known_tesla_carriers() -> list[ShipTracking]:
    """Known Tesla car carrier vessels (fallback data)."""
    return [
        ShipTracking(
            vessel_name="Grand Venus",
            imo="9303211", mmsi="351034000",
            tracking_url="https://www.marinetraffic.com/en/ais/details/ships/imo:9303211",
        ),
        ShipTracking(
            vessel_name="Silver Glory",
            imo="9070474", mmsi="355989000",
            tracking_url="https://www.marinetraffic.com/en/ais/details/ships/imo:9070474",
        ),
        ShipTracking(
            vessel_name="SFL Composer",
            imo="9293583", mmsi="636021785",
            tracking_url="https://www.marinetraffic.com/en/ais/details/ships/imo:9293583",
        ),
    ]


# ── Tesla Account Data ──────────────────────────────────────────────────────


def fetch_tesla_account(token: str) -> TeslaAccount:
    """Fetch all available account data from Tesla Owner API."""
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "tesla-cli/0.1.0"}
    account = TeslaAccount()

    try:
        with httpx.Client(timeout=15) as client:
            # User profile
            resp = client.get(
                "https://owner-api.teslamotors.com/api/1/users/me",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json().get("response", {})
                account.email = data.get("email", "")
                account.full_name = data.get("full_name", "")
                account.vault_uuid = data.get("vault_uuid", "")

            # Feature config
            resp = client.get(
                "https://owner-api.teslamotors.com/api/1/users/feature_config",
                headers=headers,
            )
            if resp.status_code == 200:
                account.feature_config = resp.json().get("response", {})

            # Onboarding
            resp = client.get(
                "https://owner-api.teslamotors.com/api/1/users/onboarding_data",
                headers=headers,
            )
            if resp.status_code == 200:
                account.onboarding_data = resp.json().get("response", {})

            # Service scheduling
            resp = client.get(
                "https://owner-api.teslamotors.com/api/1/users/service_scheduling_data",
                headers=headers,
            )
            if resp.status_code == 200:
                sdata = resp.json().get("response", {})
                account.service_scheduling_enabled = bool(sdata.get("enabled_vins"))

    except Exception:
        logger.warning("Tesla account fetch failed", exc_info=True)

    return account


# ── Dossier Builder ─────────────────────────────────────────────────────────


class DossierBackend:
    """Build and maintain the comprehensive vehicle dossier."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=30)

    def build_dossier(self) -> VehicleDossier:
        """Build the full dossier from all available sources."""
        from tesla_cli.core.backends.order import OrderBackend
        from tesla_cli.cli.output import console

        cfg = load_config()
        vin = cfg.general.default_vin
        rn = cfg.order.reservation_number

        # Load existing dossier or create new
        dossier = self._load_dossier()
        if not dossier:
            dossier = VehicleDossier(vin=vin, reservation_number=rn)

        console.print("[dim]Decoding VIN...[/dim]")
        dossier.vin_decode = decode_vin(vin)

        # Order data
        console.print("[dim]Fetching order data from Tesla...[/dim]")
        try:
            order_backend = OrderBackend()
            orders = order_backend.get_orders()
            for order in orders if isinstance(orders, list) else [orders]:
                if order.get("referenceNumber") == rn:
                    # Decode option codes
                    mkt = order.get("mktOptions", "")
                    if mkt:
                        dossier.option_codes = decode_option_codes(mkt)

                    # Order timeline
                    snapshot = OrderSnapshot(
                        order_status=order.get("orderStatus", ""),
                        order_substatus=order.get("orderSubstatus", ""),
                        vin=order.get("vin", ""),
                        raw=order,
                    )
                    dossier.order = OrderTimeline(
                        reservation_number=rn,
                        vehicle_map_id=order.get("vehicleMapId", 0),
                        country_code=order.get("countryCode", ""),
                        locale=order.get("locale", ""),
                        is_b2b=order.get("isB2b", False),
                        is_used=order.get("isUsed", False),
                        is_tesla_assist_enabled=order.get("isTeslaAssistEnabled", False),
                        current=snapshot,
                    )

                    # Append to history if different from last
                    self._append_history(dossier, snapshot)
                    break
        except Exception as e:
            logger.warning("Order fetch failed: %s", e, exc_info=True)
            console.print(f"[yellow]Order fetch failed: {e}[/yellow]")

        # Tesla account
        console.print("[dim]Fetching account data...[/dim]")
        try:
            order_backend = OrderBackend()
            token = order_backend._get_access_token()
            dossier.account = fetch_tesla_account(token)
        except Exception:
            pass

        # Vehicle specs (from decoded VIN + options)
        console.print("[dim]Building vehicle specs...[/dim]")
        dossier.specs = self._build_specs(dossier)

        # Logistics
        console.print("[dim]Building logistics info...[/dim]")
        dossier.logistics = self._build_logistics(dossier)

        # Ship tracking
        console.print("[dim]Fetching ship tracking data...[/dim]")
        ships = fetch_tesla_ships()
        if ships:
            # Assign the most likely carrier
            dossier.logistics.ship = ships[0]  # Best guess

        # Recalls
        console.print("[dim]Checking recalls...[/dim]")
        dossier.recalls = fetch_tesla_recalls(vin)

        # NHTSA decode (may fail for non-US VINs)
        console.print("[dim]Querying NHTSA...[/dim]")
        nhtsa = fetch_nhtsa_decode(vin)
        if nhtsa:
            dossier.raw_snapshots.append({"source": "nhtsa", "timestamp": str(datetime.now()), "data": nhtsa})

        # RUNT (Colombia) — live query
        console.print("[dim]Querying RUNT (live)...[/dim]")
        try:
            from tesla_cli.core.backends.runt import RuntBackend
            runt_backend = RuntBackend()
            dossier.runt = runt_backend.query_by_vin(vin)
            dossier.runt.queried_at = datetime.now()
        except Exception as e:
            console.print(f"[yellow]RUNT query failed: {e}[/yellow]")
            # Keep existing data if query fails

        # Load delivery appointment from cache
        console.print("[dim]Loading delivery appointment data...[/dim]")
        try:
            from tesla_cli.core.backends.order import DELIVERY_CACHE_FILE, OrderBackend
            if DELIVERY_CACHE_FILE.exists():
                order_be = OrderBackend()
                appt = order_be.get_delivery_appointment(rn)
                if appt.date_utc:
                    # Store delivery date in dossier for phase computation
                    dossier.real_status.delivery_date = appt.date_utc[:10]  # YYYY-MM-DD
                    dossier.real_status.delivery_location = appt.location_name
                    dossier.real_status.delivery_appointment = appt.appointment_text
        except Exception as e:
            console.print(f"[dim]Delivery cache: {e}[/dim]")

        # Compute real status from all sources
        console.print("[dim]Computing real status...[/dim]")
        dossier.real_status = self._compute_real_status(dossier)

        # Save
        dossier.last_updated = datetime.now()
        dossier.update_count += 1
        self._save_dossier(dossier)
        self._save_snapshot(dossier)

        return dossier

    def _compute_real_status(self, d: VehicleDossier) -> RealStatus:
        """Compute actual vehicle status from ALL sources.

        Tesla's API for Colombia stays at BOOKED even when the car is
        already in-country, registered in RUNT, and ready for delivery.
        We use multi-source intelligence to determine the real phase.
        """
        rs = RealStatus()

        # Tesla API signal
        rs.tesla_api_status = d.order.current.order_status

        # VIN assigned?
        rs.vin_assigned = bool(d.vin)

        # RUNT signals
        rs.runt_status = d.runt.estado
        rs.in_runt = d.runt.estado == "REGISTRADO"
        rs.has_placa = bool(d.runt.placa)
        rs.has_soat = d.runt.soat_vigente

        # Delivery date (from delivery cache, set before this method is called)
        rs.delivery_date = d.real_status.delivery_date or ""
        rs.delivery_location = getattr(d.real_status, "delivery_location", "") or ""
        rs.delivery_appointment = getattr(d.real_status, "delivery_appointment", "") or ""

        # Derive timeline flags from all signals
        rs.is_produced = rs.vin_assigned  # VIN = built
        rs.is_shipped = rs.in_runt  # if in RUNT, it was shipped
        rs.is_in_country = rs.in_runt  # RUNT registration requires physical presence
        rs.is_customs_cleared = rs.in_runt  # can't register without customs clearance
        rs.is_registered = rs.in_runt
        rs.is_delivery_scheduled = bool(rs.delivery_date)
        rs.is_delivered = rs.has_placa and rs.has_soat  # placa + SOAT = on the road

        # Determine phase
        if rs.is_delivered:
            rs.phase = "delivered"
            rs.phase_description = "Entregado — en circulación"
        elif rs.is_delivery_scheduled:
            rs.phase = "delivery_scheduled"
            if rs.delivery_appointment:
                rs.phase_description = rs.delivery_appointment
            elif rs.delivery_location:
                rs.phase_description = f"Entrega programada: {rs.delivery_date} — {rs.delivery_location}"
            else:
                rs.phase_description = f"Entrega programada: {rs.delivery_date}"
        elif rs.is_registered:
            rs.phase = "registered"
            rs.phase_description = "Registrado en RUNT — pendiente matrícula y entrega"
        elif rs.is_in_country:
            rs.phase = "in_country"
            rs.phase_description = "En Colombia — pendiente registro"
        elif rs.is_shipped:
            rs.phase = "shipped"
            rs.phase_description = "En tránsito marítimo"
        elif rs.is_produced:
            rs.phase = "produced"
            rs.phase_description = "Producido — VIN asignado, pendiente envío"
        else:
            rs.phase = "ordered"
            rs.phase_description = "Orden confirmada — en espera"

        return rs

    def _get_epa_data(self) -> dict:
        """Get EPA specs dynamically. Priority: mission-control-data.json → API → fallback."""
        # 1. Try mission-control-data.json (most recent, already cached)
        mc_paths = [
            Path(__file__).parent.parent.parent.parent / "mission-control-data.json",
            Path.cwd() / "mission-control-data.json",
        ]
        for p in mc_paths:
            if p.exists():
                try:
                    mc = json.loads(p.read_text())
                    epa = mc.get("epa", {})
                    if isinstance(epa, dict) and "_meta" in epa:
                        epa = epa.get("data", epa)
                    if epa and epa.get("ev_motor"):
                        return epa
                except Exception:
                    pass

        # 2. Try EPA API directly
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    "https://www.fueleconomy.gov/ws/rest/vehicle/49744",
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    raw = resp.json()
                    return {
                        "ev_motor": raw.get("evMotor", ""),
                        "range_mi": raw.get("range"),
                        "range_city_mi": raw.get("rangeCity"),
                        "range_hwy_mi": raw.get("rangeHwy"),
                        "mpge_combined": raw.get("comb08"),
                        "charge_240v_hrs": raw.get("charge240"),
                        "curb_weight_lbs": None,  # EPA doesn't have weight
                    }
        except Exception:
            pass

        # 3. Fallback
        return {}

    def _build_specs(self, d: VehicleDossier) -> VehicleSpecs:
        """Build vehicle specs from decoded VIN, options, and EPA data."""
        vd = d.vin_decode
        year = int(vd.model_year) if vd.model_year.isdigit() else 0
        epa = self._get_epa_data()

        # Find specific options
        ext_color = ""
        interior = ""
        wheels = ""
        supercharging = ""
        connectivity = ""
        for oc in d.option_codes.codes:
            if oc.category == "paint":
                ext_color = oc.description_es
            elif oc.category == "interior":
                interior = oc.description_es
            elif oc.category == "wheels":
                wheels = oc.description_es
            elif oc.category == "autopilot":
                pass
            elif oc.category == "charging":
                supercharging = oc.description_es
            elif oc.category == "connectivity":
                connectivity = oc.description_es

        # Motor config from EPA
        ev_motor = epa.get("ev_motor", "")
        if ev_motor:
            motor_config = f"Dual Motor AWD ({ev_motor})"
            # Parse HP from kW: "90 and 200 kW ACPM" → 290 kW → 389 hp
            import re
            kw_values = re.findall(r"(\d+)\s*kW", ev_motor)
            total_kw = sum(int(k) for k in kw_values) if kw_values else 0
            hp = int(total_kw * 1.341) if total_kw else 389  # fallback
        else:
            motor_config = "Dual Motor AWD (90 kW front + 200 kW rear ACPM)"
            hp = 389

        # Range from EPA (convert mi → km) or fallback to WLTP
        epa_range_mi = epa.get("range_mi")
        range_km = int(float(epa_range_mi) * 1.60934) if epa_range_mi else 600  # WLTP fallback

        return VehicleSpecs(
            model="Model Y",
            variant="Long Range Dual Motor AWD",
            generation="Juniper (2025+ refresh)",
            model_year=year,
            factory=vd.plant,
            battery_type=vd.battery_chemistry,
            battery_capacity_kwh=79.0,  # Tesla does not publish; estimated
            range_km=range_km,
            motor_config=motor_config,
            horsepower=hp,
            zero_to_100_kmh=4.8,  # tesla.com/es_CO — not in EPA
            top_speed_kmh=201,  # tesla.com/es_CO — not in EPA
            curb_weight_kg=2029,  # tesla.com US (4473 lbs) — not in EPA
            dimensions="4791 x 1981 x 1623 mm",  # tesla.com US — not in EPA
            seating=5,
            wheels=wheels or "19\" Gemini",
            exterior_color=ext_color or "Stealth Grey",
            interior=interior or "Premium Black",
            autopilot_hardware="HW5 (AI5)",
            has_fsd=False,
            supercharging=supercharging or "Pay Per Use",
            connectivity=connectivity or "Standard",
        )

    def _build_logistics(self, d: VehicleDossier) -> Logistics:
        """Build logistics from VIN decode."""
        vd = d.vin_decode
        return Logistics(
            factory=vd.plant or "Gigafactory Shanghai",
            departure_port="Shanghai / Nangang Terminal",
            arrival_port="Cartagena or Buenaventura (Colombia)",
            destination_country=d.order.country_code or "CO",
            estimated_transit_days=35,  # Shanghai→Colombia typical
        )

    def _append_history(self, dossier: VehicleDossier, snapshot: OrderSnapshot) -> None:
        """Add snapshot to history if different from last."""
        if not dossier.order.history:
            dossier.order.history.append(snapshot)
            return

        last = dossier.order.history[-1]
        if (
            last.order_status != snapshot.order_status
            or last.order_substatus != snapshot.order_substatus
            or last.vin != snapshot.vin
            or last.delivery_window_start != snapshot.delivery_window_start
        ):
            dossier.order.history.append(snapshot)

    def _load_dossier(self) -> VehicleDossier | None:
        """Load existing dossier from disk."""
        if DOSSIER_FILE.exists():
            try:
                data = json.loads(DOSSIER_FILE.read_text())
                return VehicleDossier.model_validate(data)
            except Exception:
                return None
        return None

    def _save_dossier(self, dossier: VehicleDossier) -> None:
        """Save dossier to disk."""
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        DOSSIER_FILE.write_text(
            dossier.model_dump_json(indent=2, exclude_none=True)
        )

    def _save_snapshot(self, dossier: VehicleDossier) -> None:
        """Save a timestamped snapshot for historical record."""
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SNAPSHOTS_DIR / f"snapshot_{ts}.json"
        path.write_text(
            dossier.model_dump_json(indent=2, exclude_none=True)
        )

    def get_history(self) -> list[dict]:
        """List all historical snapshots."""
        if not SNAPSHOTS_DIR.exists():
            return []
        snapshots = []
        for f in sorted(SNAPSHOTS_DIR.glob("snapshot_*.json")):
            try:
                data = json.loads(f.read_text())
                snapshots.append({
                    "file": f.name,
                    "timestamp": data.get("last_updated", ""),
                    "order_status": data.get("order", {}).get("current", {}).get("order_status", ""),
                })
            except Exception:
                continue
        return snapshots
