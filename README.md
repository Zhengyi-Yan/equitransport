# equitransport

`equitransport` is a Python package for asking a practical GIS and public
transport equity question:

> Does Auckland's public transport access reach the most deprived neighbourhoods?

The package combines Auckland SA2/SA1 boundaries, NZDep deprivation data, and
GTFS public transport stop data. It produces SA2-level deprivation and access
metrics, an Auckland-wide access inequality Gini coefficient, NZDep quintile
summary tables, and static maps.

## Installation

```bash
uv sync
uv run pytest -v
```

For a local editable install:

```bash
uv pip install -e .
```

## Required Datasets

The demo downloads SA1 and SA2 boundaries from the Stats NZ Datafinder WFS API
using a user-supplied API key, then caches them in `outputs/cache`.

You need a Stats NZ Datafinder API key for the boundary downloads. Pass it
directly to the boundary loader functions with `api_key=...`; do not commit API
keys to Git.

You provide these datasets as local files or already-loaded DataFrames:

- NZDep CSV with `SA12023_code`, `SA22023_code`, `SA22023_name`, `NZDep2023`,
  `NZDep2023_Score`, and `URPopnSA1_2023`.
- GTFS `stops.txt` with `stop_id`, `stop_name`, `stop_lat`, and `stop_lon`.

The package can also work with already-loaded boundary GeoDataFrames:

- Auckland SA2 boundaries with `SA22023_code`, `SA22023_name`, and `geometry`.
- Auckland SA1 boundaries with `SA12023_code` and `geometry`.

All distance and buffer operations use EPSG:2193.

## Example Usage

```python
import pandas as pd

from equitransport import (
    compute_access,
    equity_summary,
    load_auckland_sa1_boundaries,
    load_auckland_sa2_boundaries,
    load_nzdep,
)
from equitransport.plotting import plot_access_map, plot_nzdep_map, plot_worst_gaps_map

api_key = "PASTE_YOUR_STATSNZ_API_KEY_HERE"

sa2_gdf = load_auckland_sa2_boundaries(
    api_key=api_key,
    cache_path="outputs/cache/auckland_sa2.gpkg",
)
sa1_gdf = load_auckland_sa1_boundaries(
    sa2_gdf,
    api_key=api_key,
    cache_path="outputs/cache/auckland_sa1.gpkg",
)
nzdep_df = pd.read_csv("src/equitransport/data/NZDep2023.csv")

sa2 = load_nzdep(sa2_gdf, nzdep_df=nzdep_df)
sa2 = compute_access(
    sa2,
    sa1_gdf=sa1_gdf,
    nzdep_df=nzdep_df,
    gtfs_dir="src/equitransport/data/gtfs",
)

summary, gini_value, sa2_final = equity_summary(sa2)

plot_nzdep_map(sa2_final, "outputs/nzdep_map.png")
plot_access_map(sa2_final, output_path="outputs/access_map.png")
plot_worst_gaps_map(sa2_final, "outputs/worst_gaps_map.png")
```

## Normal vs Weighted Access

`compute_access()` creates the normal access metric:

- `pct_population_within_400m`: percentage of each SA2 population within 400 m
  of any public transport stop.

If you pass a full GTFS folder with `gtfs_dir=...`, it also creates:

- `weighted_access_score`: a population-weighted score that accounts for nearby
  route-serving stops and simple mode weights.

Default mode weights are:

```python
{
    "bus": 2,
    "train": 5,
    "ferry": 1,
}
```

Use normal access outputs:

```python
summary, gini_value, sa2_final = equity_summary(
    sa2,
    access_col="pct_population_within_400m",
)

plot_access_map(
    sa2_final,
    access_col="pct_population_within_400m",
    output_path="outputs/access_map.png",
)
```

Use weighted access outputs:

```python
weighted_summary, weighted_gini_value, sa2_final = equity_summary(
    sa2,
    access_col="weighted_access_score",
)

plot_access_map(
    sa2_final,
    access_col="weighted_access_score",
    output_path="outputs/weighted_access_map.png",
)
```

Custom mode weights can be passed to `compute_access()`:

```python
sa2 = compute_access(
    sa2,
    sa1_gdf=sa1_gdf,
    nzdep_df=nzdep_df,
    gtfs_dir="src/equitransport/data/gtfs",
    mode_weights={
        "bus": 1,
        "train": 4,
        "ferry": 2,
    },
)
```

You can also run the demo script after pasting your API key into
`STATSNZ_API_KEY` near the top of `scripts/run_demo.py`:

```bash
uv run python scripts/run_demo.py
```

## Main Functions

- `load_auckland_sa2_boundaries()` downloads Auckland SA2 boundaries from the
  Stats NZ/Datafinder WFS API.
- `load_auckland_sa1_boundaries()` downloads SA1 boundaries covering Auckland
  from the Stats NZ/Datafinder WFS API.
- `load_nzdep()` joins and population-weights NZDep SA1 data to SA2 polygons.
- `load_gtfs_stops()` loads GTFS stop points and projects them to EPSG:2193.
- `load_gtfs_stops_with_modes()` joins GTFS `stop_times.txt`, `trips.txt`, and
  `routes.txt` so stops carry route mode information from `route_type`.
- `prepare_sa1_centroids()` creates population-bearing SA1 centroid points.
- `compute_access()` calculates the percentage of each SA2 population within a
  straight-line stop buffer, using SA1 centroids.
- `gini()` calculates access inequality.
- `equity_summary()` creates a five-row NZDep quintile summary and a
  `worst_gap` flag.
- Plotting helpers create NZDep, access, worst-gap, and quintile bar charts.

## Example Outputs

The workflow can produce:

- `outputs/sa2_equity.gpkg`
- `outputs/equity_summary.csv`
- `outputs/nzdep_map.png`
- `outputs/access_map.png`
- `outputs/worst_gaps_map.png`
- `outputs/access_by_quintile.png`

## Limitations

- The access method uses a 400 m straight-line buffer, not walking network
  distance.
- SA1 centroids approximate population location.
- Stop proximity does not measure service frequency, reliability, travel time,
  fares, accessibility, or route usefulness.
- The optional mode-weighted score is a simple nearby-stop score, not a service
  frequency or destination usefulness measure.

## Future Improvements

- Network-based walking distance.
- Service frequency weighting.
- Interactive web dashboard.
- Support for other cities.
