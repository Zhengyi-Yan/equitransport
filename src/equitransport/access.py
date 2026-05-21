"""Public transport stop access metrics."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

from .data import NZTM_CRS, WGS84_CRS, _require_columns, load_gtfs_stops, load_gtfs_stops_with_modes


def prepare_sa1_centroids(sa1_gdf: gpd.GeoDataFrame, nzdep_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Create SA1 centroid points with population and parent SA2 code attached."""

    _require_columns(sa1_gdf, {"SA12023_code", "geometry"}, "sa1_gdf")
    _require_columns(nzdep_df, {"SA12023_code", "SA22023_code", "URPopnSA1_2023"}, "nzdep_df")

    sa1 = sa1_gdf.copy()
    nzdep = nzdep_df[["SA12023_code", "SA22023_code", "URPopnSA1_2023"]].copy()
    sa1["SA12023_code"] = sa1["SA12023_code"].astype(str)
    nzdep["SA12023_code"] = nzdep["SA12023_code"].astype(str)
    nzdep["SA22023_code"] = nzdep["SA22023_code"].astype(str)
    nzdep["URPopnSA1_2023"] = pd.to_numeric(nzdep["URPopnSA1_2023"], errors="coerce")

    joined = sa1.merge(nzdep, on="SA12023_code", how="inner")
    joined = joined.dropna(subset=["URPopnSA1_2023"])

    if joined.crs is None:
        joined = joined.set_crs(NZTM_CRS)
    joined = joined.to_crs(NZTM_CRS)
    joined["geometry"] = joined.geometry.centroid

    return gpd.GeoDataFrame(
        joined[["SA12023_code", "SA22023_code", "URPopnSA1_2023", "geometry"]],
        geometry="geometry",
        crs=NZTM_CRS,
    )


def _prepare_stops(
    stops_gdf: gpd.GeoDataFrame | None,
    stops_path: str | Path | None,
    gtfs_dir: str | Path | None,
) -> gpd.GeoDataFrame:
    if stops_gdf is None:
        if gtfs_dir is not None:
            stops = load_gtfs_stops_with_modes(gtfs_dir)
        elif stops_path is not None:
            stops = load_gtfs_stops(stops_path)
        else:
            raise ValueError("Provide one of stops_gdf, gtfs_dir, or stops_path")
    else:
        stops = stops_gdf.copy()
        if "geometry" not in stops.columns and {"stop_lon", "stop_lat"}.issubset(stops.columns):
            stops = gpd.GeoDataFrame(
                stops,
                geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
                crs=WGS84_CRS,
            )
        if stops.crs is None:
            stops = stops.set_crs(WGS84_CRS)
        stops = stops.to_crs(NZTM_CRS)
    return stops


def _access_quintile(access: pd.Series) -> pd.Series:
    return pd.cut(
        access.clip(lower=0, upper=100),
        bins=[0, 20, 40, 60, 80, 100],
        labels=[1, 2, 3, 4, 5],
        include_lowest=True,
    ).astype("Int64")


def _mode_column(stops: gpd.GeoDataFrame) -> str | None:
    for column in ["mode", "route_type"]:
        if column in stops.columns:
            return column
    return None


def _mode_weight(value: object, mode_weights: dict[str, float]) -> float:
    route_type_map = {
        0: "train",
        1: "train",
        2: "train",
        3: "bus",
        4: "ferry",
    }
    if pd.isna(value):
        return 1.0
    if isinstance(value, (int, float, np.integer, np.floating)):
        mode = route_type_map.get(int(value))
        return float(mode_weights.get(mode, 1.0)) if mode else 1.0

    text = str(value).strip().lower()
    if "ferry" in text:
        return float(mode_weights.get("ferry", 1.0))
    if "train" in text or "rail" in text:
        return float(mode_weights.get("train", 1.0))
    if "bus" in text:
        return float(mode_weights.get("bus", 1.0))
    return float(mode_weights.get(text, 1.0))


def _weighted_access(
    sa1_centroids: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    distance: float,
    mode_weights: dict[str, float],
) -> pd.DataFrame:
    mode_col = _mode_column(stops)
    if mode_col is None or stops.empty or sa1_centroids.empty:
        return pd.DataFrame({"SA22023_code": sa1_centroids["SA22023_code"].unique(), "weighted_access_score": np.nan})

    weighted_stops = stops[[mode_col, "geometry"]].copy()
    weighted_stops["_stop_weight"] = weighted_stops[mode_col].map(lambda value: _mode_weight(value, mode_weights))
    weighted_stops["geometry"] = weighted_stops.geometry.buffer(distance)

    joined = gpd.sjoin(
        sa1_centroids[["SA22023_code", "URPopnSA1_2023", "geometry"]],
        gpd.GeoDataFrame(weighted_stops[["_stop_weight", "geometry"]], geometry="geometry", crs=NZTM_CRS),
        how="left",
        predicate="within",
    )

    sa1_scores = (
        joined.groupby(joined.index)["_stop_weight"]
        .sum(min_count=1)
        .reindex(sa1_centroids.index)
        .fillna(0)
    )
    scores = sa1_centroids[["SA22023_code", "URPopnSA1_2023"]].copy()
    scores["_score"] = sa1_scores.to_numpy()
    scores["_weighted_score"] = scores["URPopnSA1_2023"] * scores["_score"]

    agg = (
        scores.groupby("SA22023_code", as_index=False)
        .agg(_weighted_score=("_weighted_score", "sum"), _population=("URPopnSA1_2023", "sum"))
    )
    agg["weighted_access_score"] = np.where(
        agg["_population"] > 0,
        agg["_weighted_score"] / agg["_population"],
        np.nan,
    )
    return agg[["SA22023_code", "weighted_access_score"]]


def compute_access(
    gdf: gpd.GeoDataFrame,
    metric_col: str = "pct_population_within_400m",
    sa1_gdf: gpd.GeoDataFrame | None = None,
    nzdep_df: pd.DataFrame | None = None,
    stops_gdf: gpd.GeoDataFrame | None = None,
    stops_path: str | Path | None = None,
    gtfs_dir: str | Path | None = None,
    distance: float = 400,
    mode_weights: dict[str, float] | None = None,
) -> gpd.GeoDataFrame:
    """Calculate buffer-based public transport access for each SA2."""

    _require_columns(gdf, {"SA22023_code", "population", "geometry"}, "gdf")
    if sa1_gdf is None or nzdep_df is None:
        raise ValueError("sa1_gdf and nzdep_df are required for SA1 population-weighted access")

    sa2 = gdf.copy()
    sa2["SA22023_code"] = sa2["SA22023_code"].astype(str)
    if sa2.crs is None:
        sa2 = sa2.set_crs(NZTM_CRS)
    sa2 = sa2.to_crs(NZTM_CRS)

    stops = _prepare_stops(stops_gdf, stops_path, gtfs_dir)
    sa1_centroids = prepare_sa1_centroids(sa1_gdf, nzdep_df)
    sa1_centroids = sa1_centroids[sa1_centroids["SA22023_code"].isin(sa2["SA22023_code"])].copy()

    if stops.empty:
        coverage_geometry = None
    else:
        coverage_geometry = unary_union(stops.geometry.buffer(distance).to_list())

    if coverage_geometry is None or coverage_geometry.is_empty or sa1_centroids.empty:
        sa1_centroids["has_access_400m"] = False
    else:
        sa1_centroids["has_access_400m"] = sa1_centroids.geometry.within(coverage_geometry)

    sa1_centroids["covered_population"] = np.where(
        sa1_centroids["has_access_400m"],
        sa1_centroids["URPopnSA1_2023"],
        0,
    )

    access = (
        sa1_centroids.groupby("SA22023_code", as_index=False)
        .agg(population_within_400m=("covered_population", "sum"))
    )
    result = sa2.merge(access, on="SA22023_code", how="left")
    result["population_within_400m"] = result["population_within_400m"].fillna(0)
    result["pct_population_within_400m"] = np.where(
        result["population"] > 0,
        result["population_within_400m"] / result["population"] * 100,
        0,
    )

    if metric_col != "pct_population_within_400m":
        result[metric_col] = result["pct_population_within_400m"]

    result["access_quintile"] = _access_quintile(result["pct_population_within_400m"])

    weights = {"bus": 2, "train": 5, "ferry": 1} if mode_weights is None else mode_weights
    weighted_access = _weighted_access(sa1_centroids, stops, distance, weights)
    result = result.merge(weighted_access, on="SA22023_code", how="left")
    if "weighted_access_score" not in result.columns:
        result["weighted_access_score"] = np.nan

    return gpd.GeoDataFrame(result, geometry=sa2.geometry.name, crs=NZTM_CRS)
