import geopandas as gpd
import pytest
import xarray
from shapely.geometry import Polygon, MultiPolygon

from openeo_driver.datacube import DriverVectorCube
from openeo_driver.testing import DictSubSet
from .data import get_path


class TestDriverVectorCube:

    @pytest.fixture
    def gdf(self) -> gpd.GeoDataFrame:
        """Fixture for a simple GeoPandas DataFrame from file"""
        path = str(get_path("geojson/FeatureCollection02.json"))
        df = gpd.read_file(path)
        return df

    def test_basic(self, gdf):
        vc = DriverVectorCube(gdf)
        assert vc.get_bounding_box() == (1, 1, 5, 4)

    def test_to_multipolygon(self, gdf):
        vc = DriverVectorCube(gdf)
        mp = vc.to_multipolygon()
        assert isinstance(mp, MultiPolygon)
        assert len(mp) == 2
        assert mp.equals(MultiPolygon([
            Polygon([(1, 1), (2, 3), (3, 1), (1, 1)]),
            Polygon([(4, 2), (5, 4), (3, 4), (4, 2)]),
        ]))

    def test_get_geometries(self, gdf):
        vc = DriverVectorCube(gdf)
        geometries = vc.get_geometries()
        assert len(geometries) == 2
        expected_geometries = [
            Polygon([(1, 1), (2, 3), (3, 1), (1, 1)]),
            Polygon([(4, 2), (5, 4), (3, 4), (4, 2)]),
        ]
        for geometry, expected in zip(geometries, expected_geometries):
            assert geometry.equals(expected)

    def test_to_geojson(self, gdf):
        vc = DriverVectorCube(gdf)
        assert vc.to_geojson() == DictSubSet({
            "type": "FeatureCollection",
            "features": [
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((1, 1), (3, 1), (2, 3), (1, 1)),)},
                    "properties": {"id": "first", "pop": 1234},
                }),
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((4, 2), (5, 4), (3, 4), (4, 2)),)},
                    "properties": {"id": "second", "pop": 5678},
                }),
            ]
        })

    def test_to_wkt(self, gdf):
        vc = DriverVectorCube(gdf)
        assert vc.to_wkt() == (
            ['POLYGON ((1 1, 3 1, 2 3, 1 1))', 'POLYGON ((4 2, 5 4, 3 4, 4 2))'],
            'EPSG:4326',
        )

    def test_with_cube_to_geojson(self, gdf):
        vc1 = DriverVectorCube(gdf)
        dims, coords = vc1.get_xarray_cube_basics()
        dims += ("bands",)
        coords["bands"] = ["red", "green"]
        cube = xarray.DataArray(data=[[1, 2], [3, 4]], dims=dims, coords=coords)
        vc2 = vc1.with_cube(cube, flatten_prefix="bandz")
        assert vc1.to_geojson() == DictSubSet({
            "type": "FeatureCollection",
            "features": [
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((1, 1), (3, 1), (2, 3), (1, 1)),)},
                    "properties": {"id": "first", "pop": 1234},
                }),
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((4, 2), (5, 4), (3, 4), (4, 2)),)},
                    "properties": {"id": "second", "pop": 5678},
                }),
            ]
        })
        assert vc2.to_geojson() == DictSubSet({
            "type": "FeatureCollection",
            "features": [
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((1, 1), (3, 1), (2, 3), (1, 1)),)},
                    "properties": {"id": "first", "pop": 1234, "bandz~red": 1, "bandz~green": 2},
                }),
                DictSubSet({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": (((4, 2), (5, 4), (3, 4), (4, 2)),)},
                    "properties": {"id": "second", "pop": 5678, "bandz~red": 3, "bandz~green": 4},
                }),
            ]
        })

    @pytest.mark.parametrize(["geojson", "expected"], [
        (
                {"type": "Polygon", "coordinates": [[(1, 1), (3, 1), (2, 3), (1, 1)]]},
                [
                    DictSubSet({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": (((1, 1), (3, 1), (2, 3), (1, 1),),)},
                        "properties": {},
                    }),
                ],
        ),
        (
                {"type": "MultiPolygon", "coordinates": [[[(1, 1), (3, 1), (2, 3), (1, 1)]]]},
                [
                    DictSubSet({
                        "type": "Feature",
                        "geometry": {"type": "MultiPolygon", "coordinates": [(((1, 1), (3, 1), (2, 3), (1, 1),),)]},
                        "properties": {},
                    }),
                ],
        ),
        (
                {
                    "type": "Feature",
                    "geometry": {"type": "MultiPolygon", "coordinates": [[[(1, 1), (3, 1), (2, 3), (1, 1)]]]},
                    "properties": {"id": "12_3"},
                },
                [
                    DictSubSet({
                        "type": "Feature",
                        "geometry": {"type": "MultiPolygon", "coordinates": [(((1, 1), (3, 1), (2, 3), (1, 1),),)]},
                        "properties": {"id": "12_3"},
                    }),
                ],
        ),
        (
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": [[(1, 1), (3, 1), (2, 3), (1, 1)]]},
                            "properties": {"id": 1},
                        },
                        {
                            "type": "Feature",
                            "geometry": {"type": "MultiPolygon", "coordinates": [[[(1, 1), (3, 1), (2, 3), (1, 1)]]]},
                            "properties": {"id": 2},
                        },
                    ],
                },
                [
                    DictSubSet({
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": (((1, 1), (3, 1), (2, 3), (1, 1),),)},
                        "properties": {"id": 1},
                    }),
                    DictSubSet({
                        "type": "Feature",
                        "geometry": {"type": "MultiPolygon", "coordinates": [(((1, 1), (3, 1), (2, 3), (1, 1),),)]},
                        "properties": {"id": 2},
                    }),
                ],
        ),
    ])
    def test_from_geojson(self, geojson, expected):
        vc = DriverVectorCube.from_geojson(geojson)
        assert vc.to_geojson() == DictSubSet({
            "type": "FeatureCollection",
            "features": expected,
        })
