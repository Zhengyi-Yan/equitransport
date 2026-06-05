"""Small shared utilities for equitransport."""

from __future__ import annotations

import math


def decile_to_quintile(decile: int | float) -> int:
    """Convert an NZDep decile from 1-10 into a quintile from 1-5.

    Parameters
    ----------
    decile:
        NZDep decile value.

    Returns
    -------
    int
        NZDep quintile from 1 to 5.
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
