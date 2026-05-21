"""Small shared utilities for equitransport."""

from __future__ import annotations

import math


def decile_to_quintile(decile: int | float) -> int:
    """Convert an NZDep decile from 1-10 into a quintile from 1-5.

    Deciles 1-2 map to quintile 1, 3-4 to quintile 2, 5-6 to quintile 3,
    7-8 to quintile 4, and 9-10 to quintile 5. Float values are accepted and
    classified using the same upper-bound binning, so 2.5 maps to quintile 2.

    Parameters
    ----------
    decile:
        Numeric NZDep decile value.

    Returns
    -------
    int
        NZDep quintile from 1 to 5.

    Raises
    ------
    ValueError
        If the decile is missing, non-numeric, below 1, or above 10.
    """

    if decile is None:
        raise ValueError("decile must not be missing")

    try:
        value = float(decile)
    except (TypeError, ValueError) as exc:
        raise ValueError("decile must be numeric") from exc

    if math.isnan(value) or value < 1 or value > 10:
        raise ValueError("decile must be between 1 and 10")

    return int(math.ceil(value / 2))
