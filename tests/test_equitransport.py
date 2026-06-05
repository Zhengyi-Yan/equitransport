import geopandas as gpd
import matplotlib
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

matplotlib.use("Agg")

from equitransport import (
    compute_access,
    decile_to_quintile,
    equity_summary,
    gini,
    load_gtfs_stops,
    load_gtfs_stops_with_modes,
    load_nzdep,
    load_statsnz_wfs_layer,
    prepare_sa1_centroids,
)
from equitransport.plotting import (
    plot_access_map,
    plot_nzdep_map,
    plot_quintile_access_bar,
    plot_worst_gaps_map,
)


@pytest.fixture
def sample_sa2_gdf():
    return gpd.GeoDataFrame(
        {
            "SA22023_code": ["100001", "100002"],
            "SA22023_name": ["Area A", "Area B"],
        },
        geometry=[
            Polygon([(0, 0), (0, 1000), (1000, 1000), (1000, 0)]),
            Polygon([(1000, 0), (1000, 1000), (2000, 1000), (2000, 0)]),
        ],
        crs="EPSG:2193",
    )


@pytest.fixture
def sample_nzdep_df():
    return pd.DataFrame(
        {
            "SA12023_code": ["s1", "s2", "s3", "s4"],
            "SA22023_code": ["100001", "100001", "100002", "100002"],
            "SA22023_name": ["Area A", "Area A", "Area B", "Area B"],
            "NZDep2023": [2, 6, 9, 10],
            "NZDep2023_Score": [900, 1000, 1200, 1300],
            "URPopnSA1_2023": [100, 300, 200, 200],
        }
    )


@pytest.fixture
def sample_sa1_gdf():
    return gpd.GeoDataFrame(
        {"SA12023_code": ["s1", "s2", "s3", "s4"]},
        geometry=[
            Polygon([(100, 100), (100, 300), (300, 300), (300, 100)]),
            Polygon([(600, 100), (600, 300), (800, 300), (800, 100)]),
            Polygon([(1200, 100), (1200, 300), (1400, 300), (1400, 100)]),
            Polygon([(1600, 100), (1600, 300), (1800, 300), (1800, 100)]),
        ],
        crs="EPSG:2193",
    )


@pytest.fixture
def sample_stops_gdf():
    return gpd.GeoDataFrame(
        {"stop_id": ["stop-1"], "stop_name": ["Mock stop"]},
        geometry=[Point(200, 200)],
        crs="EPSG:2193",
    )


def test_load_nzdep_happy_path(sample_sa2_gdf, sample_nzdep_df):
    result = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)

    assert isinstance(result, gpd.GeoDataFrame)
    assert "population" in result.columns
    assert "weighted_nzdep" in result.columns
    assert "nzdep_quintile" in result.columns
    assert result.loc[result["SA22023_code"] == "100001", "population"].item() == 400
    assert result.loc[result["SA22023_code"] == "100001", "weighted_nzdep"].item() == 5


def test_compute_access_uses_projected_crs(sample_sa2_gdf, sample_nzdep_df, sample_sa1_gdf, sample_stops_gdf):
    sa2 = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)
    result = compute_access(
        sa2,
        metric_col="pct_population_within_400m",
        sa1_gdf=sample_sa1_gdf,
        nzdep_df=sample_nzdep_df,
        stops_gdf=sample_stops_gdf,
    )

    assert result.crs is not None
    assert result.crs.to_epsg() == 2193
    assert "pct_population_within_400m" in result.columns


def test_compute_access_calculates_population_and_custom_metric(
    sample_sa2_gdf,
    sample_nzdep_df,
    sample_sa1_gdf,
    sample_stops_gdf,
):
    sa2 = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)
    result = compute_access(
        sa2,
        metric_col="access_percent",
        sa1_gdf=sample_sa1_gdf,
        nzdep_df=sample_nzdep_df,
        stops_gdf=sample_stops_gdf,
    )

    area_a = result.loc[result["SA22023_code"] == "100001"].iloc[0]
    area_b = result.loc[result["SA22023_code"] == "100002"].iloc[0]
    assert area_a["population_within_400m"] == 100
    assert area_a["pct_population_within_400m"] == 25
    assert area_a["access_percent"] == 25
    assert area_b["pct_population_within_400m"] == 0
    assert pd.isna(area_a["weighted_access_score"])


def test_compute_access_with_mode_weights_creates_weighted_score(
    sample_sa2_gdf,
    sample_nzdep_df,
    sample_sa1_gdf,
):
    sa2 = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)
    stops = gpd.GeoDataFrame(
        {"stop_id": ["bus-stop", "rail-stop"], "mode": ["bus", "rail"]},
        geometry=[Point(200, 200), Point(700, 200)],
        crs="EPSG:2193",
    )

    result = compute_access(
        sa2,
        sa1_gdf=sample_sa1_gdf,
        nzdep_df=sample_nzdep_df,
        stops_gdf=stops,
        mode_weights={"bus": 2, "train": 5, "ferry": 1},
    )

    score = result.loc[result["SA22023_code"] == "100001", "weighted_access_score"].item()
    assert score == pytest.approx(4.25)


def test_compute_access_accepts_lon_lat_stop_frame(sample_sa2_gdf, sample_nzdep_df, sample_sa1_gdf):
    sa2 = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)
    stops = gpd.GeoDataFrame({"stop_id": ["s1"], "stop_lon": [174.76], "stop_lat": [-36.85]})

    result = compute_access(
        sa2,
        sa1_gdf=sample_sa1_gdf,
        nzdep_df=sample_nzdep_df,
        stops_gdf=stops,
    )

    assert result.crs.to_epsg() == 2193
    assert result["population_within_400m"].sum() == 0


def test_compute_access_requires_supporting_inputs(sample_sa2_gdf, sample_nzdep_df, sample_sa1_gdf):
    sa2 = load_nzdep(sample_sa2_gdf, nzdep_df=sample_nzdep_df)

    with pytest.raises(ValueError, match="sa1_gdf and nzdep_df"):
        compute_access(sa2, stops_gdf=gpd.GeoDataFrame(geometry=[]))

    with pytest.raises(ValueError, match="Provide one of"):
        compute_access(sa2, sa1_gdf=sample_sa1_gdf, nzdep_df=sample_nzdep_df)


def test_prepare_sa1_centroids_drops_missing_population(sample_sa1_gdf, sample_nzdep_df):
    nzdep = sample_nzdep_df.copy()
    nzdep.loc[nzdep["SA12023_code"] == "s4", "URPopnSA1_2023"] = None

    result = prepare_sa1_centroids(sample_sa1_gdf, nzdep)

    assert set(result["SA12023_code"]) == {"s1", "s2", "s3"}
    assert result.crs.to_epsg() == 2193
    assert result.geometry.geom_type.eq("Point").all()


def test_load_nzdep_missing_sa2_code_raises_error(sample_sa2_gdf, sample_nzdep_df):
    bad_gdf = sample_sa2_gdf.drop(columns=["SA22023_code"])

    with pytest.raises(KeyError):
        load_nzdep(bad_gdf, nzdep_df=sample_nzdep_df)


def test_load_nzdep_requires_one_data_source(sample_sa2_gdf, sample_nzdep_df, tmp_path):
    nzdep_path = tmp_path / "nzdep.csv"
    sample_nzdep_df.to_csv(nzdep_path, index=False)

    with pytest.raises(ValueError, match="Provide either"):
        load_nzdep(sample_sa2_gdf)

    with pytest.raises(ValueError, match="Provide only one"):
        load_nzdep(sample_sa2_gdf, nzdep_path=nzdep_path, nzdep_df=sample_nzdep_df)


def test_load_nzdep_reads_csv_and_handles_zero_population(sample_sa2_gdf, sample_nzdep_df, tmp_path):
    nzdep = sample_nzdep_df.copy()
    nzdep.loc[nzdep["SA22023_code"] == "100001", "URPopnSA1_2023"] = 0
    nzdep_path = tmp_path / "nzdep.csv"
    nzdep.to_csv(nzdep_path, index=False)

    result = load_nzdep(sample_sa2_gdf, nzdep_path=nzdep_path)

    area_a = result.loc[result["SA22023_code"] == "100001"].iloc[0]
    assert area_a["population"] == 0
    assert pd.isna(area_a["weighted_nzdep"])
    assert pd.isna(area_a["weighted_nzdep_score"])


def test_load_gtfs_stops_projects_and_drops_invalid_rows(tmp_path):
    stops_path = tmp_path / "stops.txt"
    pd.DataFrame(
        {
            "stop_id": ["valid", "invalid"],
            "stop_lat": [-36.85, None],
            "stop_lon": [174.76, 174.77],
        }
    ).to_csv(stops_path, index=False)

    result = load_gtfs_stops(stops_path)

    assert list(result["stop_id"]) == ["valid"]
    assert result.crs.to_epsg() == 2193


def test_load_statsnz_wfs_layer_uses_existing_cache(tmp_path, sample_sa2_gdf):
    cache_path = tmp_path / "sa2.gpkg"
    raw = sample_sa2_gdf.rename(
        columns={
            "SA22023_code": "SA22023_V1_00",
            "SA22023_name": "SA22023_V1_00_NAME",
        }
    )
    raw.to_file(cache_path, driver="GPKG")

    result = load_statsnz_wfs_layer(123, cache_path=cache_path)

    assert {"SA22023_code", "SA22023_name"}.issubset(result.columns)
    assert result["SA22023_code"].map(type).eq(str).all()
    assert result.crs.to_epsg() == 2193


@pytest.mark.parametrize(
    "decile, expected_quintile",
    [
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 2),
        (5, 3),
        (6, 3),
        (7, 4),
        (8, 4),
        (9, 5),
        (10, 5),
    ],
)
def test_decile_to_quintile_parametrised(decile, expected_quintile):
    assert decile_to_quintile(decile) == expected_quintile


@pytest.mark.parametrize("decile", [None, "not-a-number", 0, 11, float("nan")])
def test_decile_to_quintile_rejects_invalid_values(decile):
    with pytest.raises(ValueError):
        decile_to_quintile(decile)


def test_gini_equal_values_returns_zero():
    assert gini([50, 50, 50]) == 0


def test_gini_empty_returns_nan():
    assert pd.isna(gini([None, float("nan")]))


def test_gini_handles_weighted_and_zero_sum_cases():
    assert gini([0, 0, 0]) == 0
    assert gini([1, 2, 3], weights=[1, 2, 3]) > 0
    assert gini([1, 2, 3], weights=[0, 0, 0]) != gini([1, 2, 3], weights=[1, 1, 1])
    assert pd.isna(gini([1, 2], weights=[None, 0]))


def test_equity_summary_groups_quintiles_and_flags_worst_gap(sample_sa2_gdf):
    gdf = sample_sa2_gdf.copy()
    gdf["population"] = [100, 200]
    gdf["nzdep_quintile"] = [1, 5]
    gdf["pct_population_within_400m"] = [90, 10]

    summary, gini_value, result = equity_summary(gdf)

    assert list(summary["nzdep_quintile"]) == [1, 2, 3, 4, 5]
    assert summary.loc[summary["nzdep_quintile"] == 1, "population_weighted_access"].item() == 90
    assert summary.loc[summary["nzdep_quintile"] == 5, "population_weighted_access"].item() == 10
    assert gini_value > 0
    assert result.loc[result["SA22023_code"] == "100002", "worst_gap"].item()


def test_equity_summary_requires_access_columns(sample_sa2_gdf):
    with pytest.raises(KeyError):
        equity_summary(sample_sa2_gdf)


def test_load_gtfs_stops_with_modes(tmp_path):
    gtfs_dir = tmp_path / "gtfs"
    gtfs_dir.mkdir()
    pd.DataFrame(
        {
            "stop_id": ["s1", "s2"],
            "stop_name": ["Bus stop", "Train stop"],
            "stop_lat": [-36.85, -36.86],
            "stop_lon": [174.76, 174.77],
        }
    ).to_csv(gtfs_dir / "stops.txt", index=False)
    pd.DataFrame({"trip_id": ["t1", "t2"], "stop_id": ["s1", "s2"]}).to_csv(
        gtfs_dir / "stop_times.txt", index=False
    )
    pd.DataFrame({"trip_id": ["t1", "t2"], "route_id": ["r1", "r2"]}).to_csv(
        gtfs_dir / "trips.txt", index=False
    )
    pd.DataFrame({"route_id": ["r1", "r2"], "route_type": [3, 2]}).to_csv(
        gtfs_dir / "routes.txt", index=False
    )

    result = load_gtfs_stops_with_modes(gtfs_dir)

    assert isinstance(result, gpd.GeoDataFrame)
    assert set(result["route_type"]) == {2, 3}
    assert result.crs.to_epsg() == 2193


def test_plotting_helpers_return_axes_and_save_files(sample_sa2_gdf, tmp_path):
    gdf = sample_sa2_gdf.copy()
    gdf["population"] = [100, 200]
    gdf["nzdep_quintile"] = [1, 5]
    gdf["pct_population_within_400m"] = [80, 10]
    gdf["weighted_access_score"] = [3, 1]
    gdf["worst_gap"] = [False, True]

    nzdep_path = tmp_path / "nzdep.png"
    access_path = tmp_path / "access.png"
    gap_path = tmp_path / "gaps.png"

    fig, ax = plot_nzdep_map(gdf, nzdep_path, exclude_sa2_names=None, urban_zoom=False)
    assert ax.get_title() == "Auckland SA2 NZDep Quintile"
    assert nzdep_path.exists()
    fig.clf()

    fig, ax = plot_access_map(
        gdf,
        access_col="weighted_access_score",
        output_path=access_path,
        exclude_sa2_names=None,
        urban_zoom=False,
    )
    assert ax.get_title() == "Auckland SA2 Public Transport Access"
    assert access_path.exists()
    fig.clf()

    fig, ax = plot_worst_gaps_map(gdf, gap_path, exclude_sa2_names=None, urban_zoom=False)
    assert ax.get_title() == "High Deprivation and Low Public Transport Access"
    assert gap_path.exists()
    fig.clf()


def test_plot_quintile_access_bar_saves_file(tmp_path):
    summary = pd.DataFrame(
        {
            "nzdep_quintile": [1, 2, 3, 4, 5],
            "population_weighted_access": [90, 80, 70, 60, 50],
        }
    )
    output_path = tmp_path / "bar.png"

    fig, ax = plot_quintile_access_bar(summary, output_path)

    assert ax.get_xlabel() == "NZDep quintile"
    assert output_path.exists()
    fig.clf()
