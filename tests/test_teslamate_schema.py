"""Schema drift sentinel for TeslaMate's `charges` table.

The backend relies on seven specific columns. If upstream TeslaMate removes or
renames any of them, our backend queries break silently. This test pins the
DDL snapshot and asserts the columns we rely on are present.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "teslamate_schema" / "charges_v1.30.sql"

REQUIRED_COLUMNS = (
    "date",
    "battery_level",
    "charger_power",
    "charger_actual_current",
    "charger_voltage",
    "charger_phases",
    "ideal_battery_range_km",
)


def test_charges_schema_has_required_columns():
    assert FIXTURE.exists(), f"Schema fixture missing: {FIXTURE}"
    ddl = FIXTURE.read_text()
    for col in REQUIRED_COLUMNS:
        assert col in ddl, f"Missing column in charges DDL: {col}"
