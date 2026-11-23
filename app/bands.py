"""Band parsing and matching (inclusive bounds)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


class BandParseError(ValueError):
    pass


def parse_band_label(label: str) -> tuple[Decimal, Decimal | None]:
    label = label.strip()
    if not label:
        raise BandParseError("empty band")
    if label.endswith("+"):
        try:
            return Decimal(label[:-1].strip()), None
        except InvalidOperation as e:
            raise BandParseError(f"invalid open band: {label}") from e
    if "-" in label:
        lo, hi = label.split("-", 1)
        try:
            return Decimal(lo.strip()), Decimal(hi.strip())
        except InvalidOperation as e:
            raise BandParseError(f"invalid band: {label}") from e
    raise BandParseError(f"invalid band format: {label}")


def in_band(value: Decimal, lo: Decimal, hi: Decimal | None) -> bool:
    if value < lo:
        return False
    if hi is None:
        return True
    return value <= hi


def bands_overlap(
    a_lo: Decimal, a_hi: Decimal | None, b_lo: Decimal, b_hi: Decimal | None
) -> bool:
    a_end = a_hi if a_hi is not None else Decimal("Infinity")
    b_end = b_hi if b_hi is not None else Decimal("Infinity")
    return a_lo <= b_end and b_lo <= a_end


def check_band_list_overlaps(
    bands: list[tuple[Decimal, Decimal | None]], label: str
) -> list[str]:
    errors: list[str] = []
    for i, (lo, hi) in enumerate(bands):
        if hi is not None and lo > hi:
            errors.append(f"{label}: min {lo} > max {hi}")
    for i in range(len(bands)):
        for j in range(i + 1, len(bands)):
            if bands_overlap(bands[i][0], bands[i][1], bands[j][0], bands[j][1]):
                errors.append(f"{label}: bands {i + 1} and {j + 1} overlap")
    return errors