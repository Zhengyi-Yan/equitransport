"""Equity summary metrics."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from .access import _access_quintile
from .data import _require_columns
from .utils import decile_to_quintile


def gini(values, weights=None) -> float:
    """Calculate a Gini coefficient for an array-like set of values."""

    x = np.asarray(values, dtype=float)
    if weights is None:
        mask = ~np.isnan(x)
        x = x[mask]
        if x.size == 0:
            return float("nan")
        if np.allclose(x, x[0]):
            return 0.0
        if np.sum(x) == 0:
            return 0.0
        x = np.sort(x)
        n = x.size
        coefficient = np.sum((2 * np.arange(1, n + 1) - n - 1) * x) / (n * np.sum(x))
        return float(np.clip(coefficient, 0, 1))

    w = np.asarray(weights, dtype=float)
    mask = ~np.isnan(x) & ~np.isnan(w) & (w > 0)
    x = x[mask]
    w = w[mask]
    if x.size == 0:
        return float("nan")
    if np.allclose(x, x[0]):
        return 0.0
    order = np.argsort(x)
    x = x[order]
    w = w[order]
    cumw = np.cumsum(w)
    cumxw = np.cumsum(x * w)
    if cumw[-1] <= 0 or cumxw[-1] == 0:
        return 0.0
    coefficient = np.sum(cumxw[1:] * cumw[:-1] - cumxw[:-1] * cumw[1:]) / (cumxw[-1] * cumw[-1])
    return float(np.clip(coefficient, 0, 1))


def _weighted_mean(group: pd.DataFrame, value_col: str, weight_col: str) -> float:
    valid = group[[value_col, weight_col]].dropna()
    valid = valid[valid[weight_col] > 0]
    if valid.empty:
        return float("nan")
    return float(np.average(valid[value_col], weights=valid[weight_col]))


def equity_summary(
    gdf: gpd.GeoDataFrame,
    access_col: str = "pct_population_within_400m",
    deprivation_col: str = "nzdep_quintile",
):
    """Create NZDep quintile access summaries and choropleth-ready flags."""

    _require_columns(gdf, {deprivation_col, "population", access_col}, "gdf")
    result = gdf.copy()

    grouped = result.groupby(deprivation_col, dropna=False)
    summary = grouped.agg(
        sa2_count=(access_col, "count"),
        population=("population", "sum"),
        mean_access=(access_col, "mean"),
        min_access=(access_col, "min"),
        max_access=(access_col, "max"),
    )
    summary["population_weighted_access"] = grouped.apply(
        lambda group: _weighted_mean(group, access_col, "population"),
        include_groups=False,
    )
    summary = summary.reindex([1, 2, 3, 4, 5])
    summary["sa2_count"] = summary["sa2_count"].fillna(0).astype(int)
    summary["population"] = summary["population"].fillna(0)
    summary = summary.reset_index().rename(columns={deprivation_col: "nzdep_quintile"})
    summary = summary[
        [
            "nzdep_quintile",
            "sa2_count",
            "population",
            "mean_access",
            "population_weighted_access",
            "min_access",
            "max_access",
        ]
    ]

    gini_value = gini(result[access_col], weights=result["population"])

    if "access_quintile" not in result.columns:
        result["access_quintile"] = _access_quintile(result[access_col])
    result["worst_gap"] = (result[deprivation_col] == 5) & (result["access_quintile"] == 1)

    return summary, gini_value, gpd.GeoDataFrame(result, geometry=result.geometry.name, crs=result.crs)
