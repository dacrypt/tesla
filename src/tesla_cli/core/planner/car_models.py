"""Mapping from tesla-cli aliases to ABRP car_model identifiers.

Used only for --abrp-link — no impact on routing or charger selection.
Reference: https://abetterrouteplanner.com (see car list in browser).
"""

from __future__ import annotations

# Conservative, common-Tesla-only default set. Users can override per-call with --car.
TESLA_CAR_MODELS: dict[str, str] = {
    "model_y_lr": "tesla:my:22:bt37:lr",
    "model_y_p": "tesla:my:22:bt37:p",
    "model_y_rwd": "tesla:my:22:bt37:rwd",
    "model_3_lr": "tesla:m3:22:bt37:lr",
    "model_3_p": "tesla:m3:22:bt37:p",
    "model_3_rwd": "tesla:m3:22:bt37:rwd",
    "model_s_lr": "tesla:ms:22:100:lr",
    "model_s_p": "tesla:ms:22:100:p",
    "model_x_lr": "tesla:mx:22:100:lr",
    "cybertruck": "tesla:ct:24:123:awd",
}


def resolve_car_model(alias_or_id: str | None) -> str | None:
    """Resolve alias to ABRP car model id. Pass through already-formatted ids."""
    if not alias_or_id:
        return None
    # Pass through already-formatted ABRP ids (contain colons)
    if ":" in alias_or_id:
        return alias_or_id
    return TESLA_CAR_MODELS.get(alias_or_id)
