"""Air chargeable weight for airport-to-airport quotes.

Chargeable weight is the greater of actual weight and volume weight.
The desk uses 167 kg per cubic metre (IATA 6,000 cm³/kg, stated as 167).
Rating the sell rate on actual kilograms alone undercharges loose cartons.
"""

from __future__ import annotations

AIR_KG_PER_CBM = 167


def volume_weight_kg(cbm: float) -> float:
    if cbm < 0:
        raise ValueError("cbm must be >= 0")
    return round(cbm * AIR_KG_PER_CBM, 1)


def chargeable_kg(actual_kg: float, cbm: float | None) -> tuple[float, float | None]:
    """Return (chargeable kg, volume weight kg).

    Volume weight is None when cubic metres were not supplied. Actual weight
    is used only in that case, or when the cargo is denser than 167 kg/cbm.
    """
    if actual_kg < 0:
        raise ValueError("actual_kg must be >= 0")
    if cbm is None:
        return actual_kg, None
    volumetric = volume_weight_kg(cbm)
    return max(actual_kg, volumetric), volumetric


def rate_air_leg(
    *,
    actual_kg: float,
    cbm: float | None,
    origin: str,
    destination: str,
    rate_eur_per_kg: float,
) -> dict[str, float | str | None]:
    """Rate one air leg on chargeable weight.

    The per-kg sell rate is supplied by the rate sheet. This function only
    chooses the weight that rate is applied to.
    """
    chargeable, volumetric = chargeable_kg(actual_kg, cbm)
    return {
        "origin": origin,
        "destination": destination,
        "chargeable_kg": chargeable,
        "volume_weight_kg": volumetric,
        "rate_eur_per_kg": rate_eur_per_kg,
    }
