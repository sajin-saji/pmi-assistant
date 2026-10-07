"""Lookup tables from ISO standards used by the rule engine.

Values are the published table values; only the size ranges a small machined part needs are included.
"""

# ISO 2768-1 general tolerances for linear dimensions, permissible deviation (+/- mm).
# Each row: (upper limit of nominal size range, fine "f", medium "m")
_ISO2768_LINEAR = [
    (3, 0.05, 0.1),
    (6, 0.05, 0.1),
    (30, 0.1, 0.2),
    (120, 0.15, 0.3),
    (400, 0.2, 0.5),
    (1000, 0.3, 0.8),
    (2000, 0.5, 1.2),
]


def iso2768_linear(nominal_mm: float, tol_class: str = "m") -> float:
    """Permissible deviation (+/-) for a linear size under ISO 2768-1."""
    if nominal_mm < 0.5:
        raise ValueError("ISO 2768-1 linear tolerances start at 0.5 mm")
    col = {"f": 1, "m": 2}[tol_class]
    for row in _ISO2768_LINEAR:
        if nominal_mm <= row[0]:
            return row[col]
    raise ValueError(f"{nominal_mm} mm is outside the supported ISO 2768-1 range")


# ISO 286-1 standard tolerance grade IT7 in micrometres. Row: (over, up to and including, IT7)
_IT7_UM = [
    (3, 6, 12),
    (6, 10, 15),
    (10, 18, 18),
    (18, 30, 21),
    (30, 50, 25),
    (50, 80, 30),
    (80, 120, 35),
    (120, 180, 40),
]


def h7_deviations(nominal_mm: float) -> tuple[float, float]:
    """Upper and lower deviation (mm) of an H7 hole: lower = 0, upper = IT7."""
    for lo, hi, it7 in _IT7_UM:
        if lo < nominal_mm <= hi:
            return round(it7 / 1000, 3), 0.0
    raise ValueError(f"H7 table does not cover {nominal_mm} mm")


# ISO 286-1 standard tolerance grade IT13 in micrometres (ISO 273 medium series uses H13)
_IT13_UM = [(3, 6, 180), (6, 10, 220), (10, 18, 270), (18, 30, 330)]


def h13_upper(nominal_mm: float) -> float:
    """Upper deviation (mm) of an H13 hole; the lower deviation is 0, so MMC = nominal size."""
    for lo, hi, it13 in _IT13_UM:
        if lo < nominal_mm <= hi:
            return round(it13 / 1000, 3)
    raise ValueError(f"H13 table does not cover {nominal_mm} mm")


# ISO 273 clearance holes for metric bolts, medium series (mm)
CLEARANCE_MEDIUM = {"M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6, "M8": 9.0, "M10": 11.0, "M12": 13.5}

# Nominal major diameter of metric coarse threads (mm)
THREAD_NOMINAL = {"M3": 3.0, "M4": 4.0, "M5": 5.0, "M6": 6.0, "M8": 8.0, "M10": 10.0, "M12": 12.0}


def floating_fastener_position_tol(fastener: str) -> float:
    """Position tolerance (diameter, at MMC) for a floating-fastener joint: T = H - F.

    H is the hole at MMC. Because the clearance hole is toleranced H13 (lower deviation 0), MMC = nominal.
    """
    return round(CLEARANCE_MEDIUM[fastener] - THREAD_NOMINAL[fastener], 3)


def fixed_fastener_position_tol(fastener: str) -> float:
    """Position tolerance per part for a fixed-fastener joint, split equally: T = (H - F) / 2."""
    return round((CLEARANCE_MEDIUM[fastener] - THREAD_NOMINAL[fastener]) / 2, 3)
