"""Data loading and joining helpers."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import numpy as np
import pandas as pd


NZTM_CRS = "EPSG:2193"
WGS84_CRS = "EPSG:4326"
DEFAULT_STATSNZ_WFS_BASE_URL = "https://datafinder.stats.govt.nz/services;key={api_key}/wfs/"
SA1_2023_LAYER_ID = 111208
SA2_HIGHER_GEOGRAPHIES_2023_LAYER_ID = 111218


def _require_columns(frame: pd.DataFrame | gpd.GeoDataFrame, columns: set[str], name: str) -> None:
    missing = columns.difference(frame.columns)
    if missing:
        raise KeyError(f"{name} is missing required columns: {', '.join(sorted(missing))}")


def _get_config_value(name: str, default=None):
    try:
        from . import config
    except ImportError as exc:
        if default is not None:
            return default
        raise ValueError(
            f"{name} was not provided and equitransport.config could not be imported"
        ) from exc
    return getattr(config, name, default)


def _statsnz_wfs_url(
    layer_id: int,
    api_key: str | None = None,
    base_url: str | None = None,
    cql_filter: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> str:
    if api_key is None:
        api_key = _get_config_value("STATSNZ_API_KEY")
    if base_url is None:
        base_url = _get_config_value("STATSNZ_WFS_BASE_URL", DEFAULT_STATSNZ_WFS_BASE_URL)

    service_url = base_url.format(api_key=api_key)
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": f"datafinder.stats.govt.nz:layer-{layer_id}",
        "outputFormat": "json",
        "srsName": NZTM_CRS,
    }
    if cql_filter:
        params["CQL_FILTER"] = cql_filter
    if bbox is not None:
        minx, miny, maxx, maxy = bbox
        params["bbox"] = f"{minx},{miny},{maxx},{maxy},{NZTM_CRS}"

    return f"{service_url}?{urlencode(params, safe=',:')}"


def _normalise_boundary_columns(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    renamed = gdf.rename(
        columns={
            "SA12023_V1_00": "SA12023_code",
            "SA22023_V1_00": "SA22023_code",
            "SA22023_V1_00_NAME": "SA22023_name",
        }
    ).copy()
    for column in ["SA12023_code", "SA22023_code"]:
        if column in renamed.columns:
            renamed[column] = renamed[column].astype(str)
    return renamed


def load_statsnz_wfs_layer(
    layer_id: int,
    api_key: str | None = None,
    base_url: str | None = None,
    cql_filter: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    cache_path: str | Path | None = None,
) -> gpd.GeoDataFrame:
    """Load a Stats NZ Datafinder WFS layer as a GeoDataFrame.

    If ``cache_path`` exists, it is read instead of calling the API. If it does
    not exist, the API result is saved there after download.
    """

    if cache_path is not None:
        cache = Path(cache_path)
        if cache.exists():
            return _normalise_boundary_columns(gpd.read_file(cache)).to_crs(NZTM_CRS)

    url = _statsnz_wfs_url(layer_id, api_key=api_key, base_url=base_url, cql_filter=cql_filter, bbox=bbox)
    gdf = gpd.read_file(url)
    if gdf.crs is None:
        gdf = gdf.set_crs(NZTM_CRS)
    gdf = _normalise_boundary_columns(gdf).to_crs(NZTM_CRS)

    if cache_path is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache, driver="GPKG")

    return gdf


def load_auckland_sa2_boundaries(
    api_key: str | None = None,
    cache_path: str | Path | None = None,
) -> gpd.GeoDataFrame:
    """Load Auckland SA2 boundaries from Stats NZ Datafinder WFS."""

    layer_id = _get_config_value(
        "SA2_HIGHER_GEOGRAPHIES_2023_LAYER_ID",
        SA2_HIGHER_GEOGRAPHIES_2023_LAYER_ID,
    )
    gdf = load_statsnz_wfs_layer(
        layer_id=layer_id,
        api_key=api_key,
        cql_filter="REGC2023_V1_00_NAME='Auckland Region'",
        cache_path=cache_path,
    )
    _require_columns(gdf, {"SA22023_code", "SA22023_name", "geometry"}, "Auckland SA2 boundaries")
    return gdf


def load_auckland_sa1_boundaries(
    sa2_gdf: gpd.GeoDataFrame,
    api_key: str | None = None,
    cache_path: str | Path | None = None,
) -> gpd.GeoDataFrame:
    """Load SA1 boundaries intersecting the Auckland SA2 extent from WFS."""

    layer_id = _get_config_value("SA1_2023_LAYER_ID", SA1_2023_LAYER_ID)
    sa2 = sa2_gdf.to_crs(NZTM_CRS)
    gdf = load_statsnz_wfs_layer(
        layer_id=layer_id,
        api_key=api_key,
        bbox=tuple(sa2.total_bounds),
        cache_path=cache_path,
    )
    _require_columns(gdf, {"SA12023_code", "geometry"}, "Auckland SA1 boundaries")
    return gdf


def load_nzdep(
    sa2_gdf: gpd.GeoDataFrame,
    nzdep_path: str | Path | None = None,
    nzdep_df: pd.DataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Join NZDep deprivation and population data to Auckland SA2 polygons.

    NZDep rows are supplied at SA1 level and aggregated to SA2 using
    ``URPopnSA1_2023`` as the population weight.
    """

    _require_columns(sa2_gdf, {"SA22023_code"}, "sa2_gdf")

    if nzdep_df is None and nzdep_path is None:
        raise ValueError("Provide either nzdep_path or nzdep_df")
    if nzdep_df is not None and nzdep_path is not None:
        raise ValueError("Provide only one of nzdep_path or nzdep_df")

    nzdep = pd.read_csv(nzdep_path) if nzdep_df is None else nzdep_df.copy()
    _require_columns(
        nzdep,
        {
            "SA12023_code",
            "SA22023_code",
            "NZDep2023",
            "NZDep2023_Score",
            "URPopnSA1_2023",
        },
        "NZDep data",
    )

    sa2 = sa2_gdf.copy()
    sa2["SA22023_code"] = sa2["SA22023_code"].astype(str)
    nzdep["SA12023_code"] = nzdep["SA12023_code"].astype(str)
    nzdep["SA22023_code"] = nzdep["SA22023_code"].astype(str)

    valid_sa2_codes = set(sa2["SA22023_code"])
    nzdep = nzdep[nzdep["SA22023_code"].isin(valid_sa2_codes)].copy()

    for column in ["NZDep2023", "NZDep2023_Score", "URPopnSA1_2023"]:
        nzdep[column] = pd.to_numeric(nzdep[column], errors="coerce")

    nzdep = nzdep.dropna(subset=["NZDep2023", "NZDep2023_Score", "URPopnSA1_2023"])

    nzdep["_nzdep_weighted"] = nzdep["NZDep2023"] * nzdep["URPopnSA1_2023"]
    nzdep["_score_weighted"] = nzdep["NZDep2023_Score"] * nzdep["URPopnSA1_2023"]

    grouped = (
        nzdep.groupby("SA22023_code", as_index=False)
        .agg(
            population=("URPopnSA1_2023", "sum"),
            _nzdep_weighted=("_nzdep_weighted", "sum"),
            _score_weighted=("_score_weighted", "sum"),
            sa1_count=("SA12023_code", "count"),
        )
    )

    grouped["weighted_nzdep"] = np.where(
        grouped["population"] > 0,
        grouped["_nzdep_weighted"] / grouped["population"],
        np.nan,
    )
    grouped["weighted_nzdep_score"] = np.where(
        grouped["population"] > 0,
        grouped["_score_weighted"] / grouped["population"],
        np.nan,
    )
    grouped["nzdep_quintile"] = pd.cut(
        grouped["weighted_nzdep"],
        bins=[0, 2, 4, 6, 8, 10],
        labels=[1, 2, 3, 4, 5],
        include_lowest=True,
    ).astype("Int64")

    grouped = grouped[
        [
            "SA22023_code",
            "population",
            "weighted_nzdep",
            "weighted_nzdep_score",
            "nzdep_quintile",
            "sa1_count",
        ]
    ]

    result = sa2.merge(grouped, on="SA22023_code", how="left")
    return gpd.GeoDataFrame(result, geometry=sa2.geometry.name, crs=sa2.crs)


def load_gtfs_stops(stops_path: str | Path) -> gpd.GeoDataFrame:
    """Load GTFS ``stops.txt`` and return stop points in EPSG:2193."""

    stops = pd.read_csv(stops_path)
    _require_columns(stops, {"stop_lat", "stop_lon"}, "GTFS stops")

    stops = stops.copy()
    stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
    stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
    stops = stops.dropna(subset=["stop_lat", "stop_lon"])

    gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs=WGS84_CRS,
    )
    return gdf.to_crs(NZTM_CRS)


def load_gtfs_stops_with_modes(gtfs_dir: str | Path) -> gpd.GeoDataFrame:
    """Load GTFS stops with route mode information attached.

    Standard GTFS stores mode in ``routes.txt`` as ``route_type``, not in
    ``stops.txt``. This helper joins ``stop_times.txt`` to ``trips.txt`` and
    ``routes.txt`` so each stop is represented once per route type that serves
    it.
    """

    gtfs = Path(gtfs_dir)
    stops = load_gtfs_stops(gtfs / "stops.txt")

    stop_times = pd.read_csv(gtfs / "stop_times.txt", usecols=["trip_id", "stop_id"])
    trips = pd.read_csv(gtfs / "trips.txt", usecols=["trip_id", "route_id"])
    routes = pd.read_csv(gtfs / "routes.txt", usecols=["route_id", "route_type"])

    for frame, columns, name in [
        (stop_times, {"trip_id", "stop_id"}, "GTFS stop_times"),
        (trips, {"trip_id", "route_id"}, "GTFS trips"),
        (routes, {"route_id", "route_type"}, "GTFS routes"),
    ]:
        _require_columns(frame, columns, name)

    stop_modes = (
        stop_times.merge(trips, on="trip_id", how="inner")
        .merge(routes, on="route_id", how="inner")
        [["stop_id", "route_type"]]
        .drop_duplicates()
    )
    stop_modes["stop_id"] = stop_modes["stop_id"].astype(str)
    stops["stop_id"] = stops["stop_id"].astype(str)

    merged = stops.merge(stop_modes, on="stop_id", how="inner")
    return gpd.GeoDataFrame(merged, geometry=stops.geometry.name, crs=stops.crs)
