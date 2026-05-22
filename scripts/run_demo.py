"""Run the end-to-end Auckland public transport equity workflow.

SA1 and SA2 boundaries are downloaded from the Stats NZ Datafinder WFS API and
cached under ``outputs/cache``. NZDep and GTFS are read from local files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from equitransport import (
    compute_access,
    equity_summary,
    load_auckland_sa1_boundaries,
    load_auckland_sa2_boundaries,
    load_nzdep,
)
from equitransport.plotting import (
    plot_access_map,
    plot_nzdep_map,
    plot_quintile_access_bar,
    plot_worst_gaps_map,
)

DATA_DIR = Path("src/equitransport/data")
NZDEP_PATH = DATA_DIR / "NZDep2023.csv"
GTFS_DIR = DATA_DIR / "gtfs"
OUTPUT_DIR = Path("outputs")
CACHE_DIR = OUTPUT_DIR / "cache"

# Paste your Stats NZ Datafinder API key here.
# Create a key at: https://datafinder.stats.govt.nz/
STATSNZ_API_KEY = "PASTE_YOUR_STATSNZ_API_KEY_HERE"


def main() -> None:
    """Run the demo workflow and save tabular and map outputs."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if STATSNZ_API_KEY == "PASTE_YOUR_STATSNZ_API_KEY_HERE":
        raise ValueError("Paste your Stats NZ Datafinder API key into STATSNZ_API_KEY before running the demo.")

    sa2_gdf = load_auckland_sa2_boundaries(
        api_key=STATSNZ_API_KEY,
        cache_path=CACHE_DIR / "auckland_sa2.gpkg",
    )
    sa1_gdf = load_auckland_sa1_boundaries(
        sa2_gdf,
        api_key=STATSNZ_API_KEY,
        cache_path=CACHE_DIR / "auckland_sa1.gpkg",
    )
    nzdep_df = pd.read_csv(NZDEP_PATH)

    sa2 = load_nzdep(sa2_gdf, nzdep_df=nzdep_df)
    sa2 = compute_access(
        sa2,
        sa1_gdf=sa1_gdf,
        nzdep_df=nzdep_df,
        gtfs_dir=GTFS_DIR,
    )
    summary, gini_value, sa2_final = equity_summary(sa2)
    weighted_summary, weighted_gini_value, _ = equity_summary(sa2, access_col="weighted_access_score")

    sa2_final.to_file(OUTPUT_DIR / "sa2_equity.gpkg", driver="GPKG")
    summary.to_csv(OUTPUT_DIR / "equity_summary.csv", index=False)
    weighted_summary.to_csv(OUTPUT_DIR / "weighted_access_summary.csv", index=False)

    plot_nzdep_map(sa2_final, OUTPUT_DIR / "nzdep_map.png")
    plot_access_map(sa2_final, output_path=OUTPUT_DIR / "access_map.png")
    plot_access_map(
        sa2_final,
        access_col="weighted_access_score",
        output_path=OUTPUT_DIR / "weighted_access_map.png",
    )
    plot_worst_gaps_map(sa2_final, OUTPUT_DIR / "worst_gaps_map.png")
    plot_quintile_access_bar(summary, OUTPUT_DIR / "access_by_quintile.png")

    print(f"Auckland access Gini: {gini_value:.3f}")
    print(f"Auckland weighted access Gini: {weighted_gini_value:.3f}")
    print(f"Saved outputs to {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
