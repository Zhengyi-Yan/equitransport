"""Matplotlib plotting helpers for equitransport outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_EXCLUDED_MAP_SA2_NAMES = {
    "Barrier Islands",
    "Bays Waiheke Island",
    "Gulf Islands",
    "Oneroa East-Palm Beach",
    "Oneroa West",
    "Onetangi",
    "Ostend",
    "Surfdale",
    "Waiheke East",
}
DEFAULT_WATER_COLOR = "#d7ecf4"


def _save(fig, output_path: str | Path | None) -> None:
    if output_path is not None:
        fig.savefig(output_path, dpi=200, bbox_inches="tight")


def _map_gdf(
    gdf,
    exclude_sa2_names: set[str] | None = None,
    exclude_unpopulated: bool = True,
):
    plot_gdf = gdf.copy()
    if exclude_sa2_names is not None and "SA22023_name" in plot_gdf.columns:
        plot_gdf = plot_gdf[~plot_gdf["SA22023_name"].isin(exclude_sa2_names)]
    if exclude_unpopulated and "population" in plot_gdf.columns:
        plot_gdf = plot_gdf[plot_gdf["population"].notna() & (plot_gdf["population"] > 0)]
    return plot_gdf.copy()


def _set_zoomed_extent(ax, gdf, padding: float = 0.03, urban_zoom: bool = True) -> None:
    if gdf.empty:
        return
    if urban_zoom and len(gdf) > 20:
        centroids = gdf.geometry.centroid
        minx = centroids.x.quantile(0.02)
        maxx = centroids.x.quantile(0.98)
        miny = centroids.y.quantile(0.02)
        maxy = centroids.y.quantile(0.98)
    else:
        minx, miny, maxx, maxy = gdf.total_bounds
    width = maxx - minx
    height = maxy - miny
    ax.set_xlim(minx - width * padding, maxx + width * padding)
    ax.set_ylim(miny - height * padding, maxy + height * padding)


def _style_map_ax(ax, water_color: str) -> None:
    ax.set_facecolor(water_color)
    ax.patch.set_visible(True)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    for spine in ax.spines.values():
        spine.set_visible(False)


def plot_nzdep_map(
    gdf,
    output_path: str | Path | None = None,
    exclude_sa2_names: set[str] | None = DEFAULT_EXCLUDED_MAP_SA2_NAMES,
    exclude_unpopulated: bool = True,
    urban_zoom: bool = True,
    water_color: str = DEFAULT_WATER_COLOR,
):
    """Plot Auckland SA2s coloured by NZDep quintile."""

    plot_gdf = _map_gdf(gdf, exclude_sa2_names, exclude_unpopulated)
    fig, ax = plt.subplots(figsize=(9, 9))
    plot_gdf.plot(column="nzdep_quintile", cmap="OrRd", legend=True, ax=ax, missing_kwds={"color": "lightgrey"})
    ax.set_title("Auckland SA2 NZDep Quintile")
    _set_zoomed_extent(ax, plot_gdf, urban_zoom=urban_zoom)
    _style_map_ax(ax, water_color)
    _save(fig, output_path)
    return fig, ax


def plot_access_map(
    gdf,
    access_col: str = "pct_population_within_400m",
    output_path: str | Path | None = None,
    exclude_sa2_names: set[str] | None = DEFAULT_EXCLUDED_MAP_SA2_NAMES,
    exclude_unpopulated: bool = True,
    urban_zoom: bool = True,
    water_color: str = DEFAULT_WATER_COLOR,
):
    """Plot Auckland SA2s coloured by public transport access."""

    plot_gdf = _map_gdf(gdf, exclude_sa2_names, exclude_unpopulated)
    fig, ax = plt.subplots(figsize=(9, 9))
    plot_gdf.plot(column=access_col, cmap="viridis", legend=True, ax=ax, missing_kwds={"color": "lightgrey"})
    ax.set_title("Auckland SA2 Public Transport Access")
    _set_zoomed_extent(ax, plot_gdf, urban_zoom=urban_zoom)
    _style_map_ax(ax, water_color)
    _save(fig, output_path)
    return fig, ax


def plot_worst_gaps_map(
    gdf,
    output_path: str | Path | None = None,
    exclude_sa2_names: set[str] | None = DEFAULT_EXCLUDED_MAP_SA2_NAMES,
    exclude_unpopulated: bool = True,
    urban_zoom: bool = True,
    water_color: str = DEFAULT_WATER_COLOR,
):
    """Plot high-deprivation, low-access SA2s."""

    plot_gdf = _map_gdf(gdf, exclude_sa2_names, exclude_unpopulated)
    fig, ax = plt.subplots(figsize=(9, 9))
    plot_gdf.plot(color="#dddddd", edgecolor="white", linewidth=0.2, ax=ax)
    gaps = plot_gdf[plot_gdf["worst_gap"].fillna(False)]
    if not gaps.empty:
        gaps.plot(color="#b2182b", edgecolor="white", linewidth=0.4, ax=ax)
    ax.set_title("High Deprivation and Low Public Transport Access")
    _set_zoomed_extent(ax, plot_gdf, urban_zoom=urban_zoom)
    _style_map_ax(ax, water_color)
    _save(fig, output_path)
    return fig, ax


def plot_quintile_access_bar(summary, output_path: str | Path | None = None):
    """Plot population-weighted access by NZDep quintile."""

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(summary["nzdep_quintile"].astype(str), summary["population_weighted_access"], color="#2c7fb8")
    ax.set_title("Population-Weighted Access by NZDep Quintile")
    ax.set_xlabel("NZDep quintile")
    ax.set_ylabel("Population within 400 m of a stop (%)")
    _save(fig, output_path)
    return fig, ax
