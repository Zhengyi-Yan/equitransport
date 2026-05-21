import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

from equitransport import compute_access, decile_to_quintile, gini, load_gtfs_stops_with_modes, load_nzdep


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


def test_load_nzdep_missing_sa2_code_raises_error(sample_sa2_gdf, sample_nzdep_df):
    bad_gdf = sample_sa2_gdf.drop(columns=["SA22023_code"])

    with pytest.raises(KeyError):
        load_nzdep(bad_gdf, nzdep_df=sample_nzdep_df)


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


def test_gini_equal_values_returns_zero():
    assert gini([50, 50, 50]) == 0


def test_gini_empty_returns_nan():
    assert pd.isna(gini([None, float("nan")]))


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
