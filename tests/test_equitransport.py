import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from equitransport import load_nzdep, compute_access, decile_to_quintile


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
def sample_sa2_with_nzdep(sample_sa2_gdf):
    gdf = sample_sa2_gdf.copy()
    gdf["population"] = [1000, 800]
    gdf["weighted_nzdep"] = [3.5, 8.2]
    gdf["nzdep_quintile"] = [2, 5]
    return gdf


def test_load_nzdep_happy_path(sample_sa2_gdf):
    result = load_nzdep(sample_sa2_gdf)

    assert isinstance(result, gpd.GeoDataFrame)
    assert "population" in result.columns
    assert "weighted_nzdep" in result.columns
    assert "nzdep_quintile" in result.columns


def test_compute_access_uses_projected_crs(sample_sa2_with_nzdep):
    result = compute_access(
        sample_sa2_with_nzdep,
        metric_col="pct_population_within_400m"
    )

    assert result.crs is not None
    assert result.crs.to_epsg() == 2193


def test_load_nzdep_missing_sa2_code_raises_error(sample_sa2_gdf):
    bad_gdf = sample_sa2_gdf.drop(columns=["SA22023_code"])

    with pytest.raises(KeyError):
        load_nzdep(bad_gdf)


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