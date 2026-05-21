"""Public transport access equity tools for Auckland."""

from __future__ import annotations

__version__ = "0.1.0"

from .access import compute_access, prepare_sa1_centroids
from .data import (
    load_auckland_sa1_boundaries,
    load_auckland_sa2_boundaries,
    load_gtfs_stops,
    load_gtfs_stops_with_modes,
    load_nzdep,
    load_statsnz_wfs_layer,
)
from .equity import equity_summary, gini
from .utils import decile_to_quintile

__all__ = [
    "__version__",
    "compute_access",
    "decile_to_quintile",
    "equity_summary",
    "gini",
    "load_auckland_sa1_boundaries",
    "load_auckland_sa2_boundaries",
    "load_gtfs_stops",
    "load_gtfs_stops_with_modes",
    "load_nzdep",
    "load_statsnz_wfs_layer",
    "prepare_sa1_centroids",
]
