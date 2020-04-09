import os

import pytest
import shapely.geometry
from flask import Response
from flask.testing import FlaskClient
from typing import Union, Callable

import dummy_impl
from openeo.capabilities import ComparableVersion
from openeo.internal.process_graph_visitor import ProcessGraphVisitor
from openeo_driver.errors import ProcessGraphMissingException
from openeo_driver.views import app
from .data import load_json, get_path

os.environ["DRIVER_IMPLEMENTATION_PACKAGE"] = "dummy_impl"


@pytest.fixture(params=["0.4.0", "1.0.0"])
def api_version(request):
    return request.param


@pytest.fixture
def client():
    app.config['TESTING'] = True
    return app.test_client()


class ApiTester:
    """Helper container class for compact writing of api version aware `views` tests"""

    def __init__(self, api_version: str, client: FlaskClient, impl=dummy_impl):
        self.api_version = api_version
        self.client = client
        self.impl = impl

    def url(self, path):
        """Get verioned url from non-versioned path"""
        return "/openeo/{v}/{p}".format(v=self.api_version, p=path.lstrip("/"))

    def load_json(self, filename, preprocess: Callable = None) -> dict:
        """Load test process graph from json file"""
        version = ".".join(self.api_version.split(".")[:2])
        return load_json("pg/{v}/{f}".format(v=version, f=filename), preprocess=preprocess)

    def post_result(self, process_graph: dict, path="/result") -> Response:
        """Post process graph to API and get response"""
        if ComparableVersion("1.0.0").or_higher(self.api_version):
            data = {"process": {'process_graph': process_graph}}
        else:
            data = {'process_graph': process_graph}
        return self.client.post(
            path=self.url(path),
            content_type='application/json',
            json=data,
        )

    def check_result(self, process_graph: Union[dict, str], path="/result"):
        """Post a process_graph (as dict or by filename), get response and do basic checks."""
        if isinstance(process_graph, str):
            # Assume it is a file name
            process_graph = self.load_json(process_graph)
        response = self.post_result(process_graph, path=path)
        # TODO Make basic asserts optional?
        assert response.status_code == 200
        assert response.content_length > 0
        return response

    @property
    def collections(self) -> dict:
        return self.impl.collections


@pytest.fixture
def api(api_version, client) -> ApiTester:
    dummy_impl.collections = {}
    return ApiTester(api_version=api_version, client=client, impl=dummy_impl)


def test_udf_runtimes(api):
    runtimes = api.client.get(api.url('/udf_runtimes')).json
    assert "Python" in runtimes


def test_execute_simple_download(api):
    api.check_result("basic.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].download.call_count == 1


def test_load_collection(api):
    api.check_result({
        'collection': {
            'process_id': 'load_collection',
            'arguments': {'id': 'S2_FAPAR_CLOUDCOVER'},
            'result': True
        }
    })


def test_execute_filter_temporal(api):
    api.check_result({
        'filter_temp': {
            'process_id': 'filter_temporal',
            'arguments': {
                'data': {
                    'from_node': 'collection'
                },
                'extent': ['2018-01-01', '2018-12-31']
            },
            'result': True
        },
        'collection': {
            'process_id': 'load_collection',
            'arguments': {
                'id': 'S2_FAPAR_CLOUDCOVER'
            }
        }
    })


def test_execute_apply_kernel(api):
    kernel_list = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
    api.check_result("apply_kernel.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_kernel.call_count == 1
    np_kernel = api.collections["S2_FAPAR_CLOUDCOVER"].apply_kernel.call_args[0][0]
    assert np_kernel.tolist() == kernel_list
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_kernel.call_args[0][1] == 3


def test_load_collection_filter(api):
    api.check_result({
        'collection': {
            'process_id': 'load_collection',
            'arguments': {
                'id': 'S2_FAPAR_CLOUDCOVER',
                'spatial_extent': {
                    'west': 5.027, 'east': 5.0438, 'north': 51.2213,
                    'south': 51.1974, 'crs': 'EPSG:4326'
                },
                'temporal_extent': ['2018-01-01', '2018-12-31']
            },
            'result': True
        }
    })
    assert api.collections['S2_FAPAR_CLOUDCOVER'].download.call_count == 1
    assert api.collections['S2_FAPAR_CLOUDCOVER'].viewingParameters == {
        'version': api.api_version, 'from': '2018-01-01', 'to': '2018-12-31',
        'left': 5.027, 'right': 5.0438, 'top': 51.2213, 'bottom': 51.1974, 'srs': 'EPSG:4326'}


def test_execute_apply_unary(api):
    api.check_result("apply_unary.json")


def test_execute_apply_run_udf(api):
    api.check_result("apply_run_udf.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_tiles.call_count == 1


def test_execute_reduce_temporal_run_udf(api):
    api.check_result("reduce_temporal_run_udf.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_tiles_spatiotemporal.call_count == 1


def test_execute_reduce_bands_run_udf(api):
    api.check_result("reduce_bands_run_udf.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_tiles.call_count == 1


def test_execute_apply_dimension_temporal_run_udf(api):
    api.check_result("apply_dimension_temporal_run_udf.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_tiles_spatiotemporal.call_count == 1
    assert api.collections["S2_FAPAR_CLOUDCOVER"].apply_dimension.call_count == 1


def test_execute_reduce_max(api):
    api.check_result("reduce_max.json")


def test_execute_merge_cubes(api):
    api.check_result("merge_cubes.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].merge.call_count == 1
    args, kwargs = api.collections["S2_FAPAR_CLOUDCOVER"].merge.call_args
    assert args[1:] == ('or',)


def test_execute_reduce_bands(api):
    api.check_result("reduce_bands.json")


def test_execute_mask(api):
    if api.api_version.startswith("1.0"):
        pytest.skip("TODO #33 #32 aggregate_spatial not supported yet")

    api.check_result("mask.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].mask.call_count == 1

    def check_params(viewing_parameters):
        assert viewing_parameters['left'] == pytest.approx(7.022705078125007)
        assert viewing_parameters['bottom'] == pytest.approx(51.29289899553571)
        assert viewing_parameters['right'] == pytest.approx(7.659912109375007)
        assert viewing_parameters['top'] == pytest.approx(51.75432477678571)
        assert viewing_parameters['srs'] == 'EPSG:4326'

    check_params(api.collections['PROBAV_L3_S10_TOC_NDVI_333M_V2'].viewingParameters)
    check_params(api.collections['S2_FAPAR_CLOUDCOVER'].viewingParameters)


def test_execute_mask_polygon(api):
    if api.api_version.startswith("1.0"):
        pytest.skip("TODO #33 #31 mask_polygon not yet supported")
    api.check_result("mask_polygon.json")
    assert api.collections["S2_FAPAR_CLOUDCOVER"].mask.call_count == 1
    assert isinstance(api.collections["S2_FAPAR_CLOUDCOVER"].mask.call_args[1]['polygon'], shapely.geometry.Polygon)


def test_preview_aggregate_temporal_max(api):
    api.check_result("aggregate_temporal_max.json")


def test_execute_zonal_statistics(api):
    resp = api.check_result("zonal_statistics.json")
    assert resp.json == {
        "2015-07-06T00:00:00": [2.9829132080078127],
        "2015-08-22T00:00:00": [None]
    }
    assert api.collections['S2_FAPAR_CLOUDCOVER'].viewingParameters['srs'] == 'EPSG:4326'


def test_create_wmts_040(api):
    process_graph = api.load_json("filter_temporal.json")
    post_data = {
        "type": 'WMTS',
        "process_graph": process_graph,
        "custom_param": 45,
        "title": "My Service",
        "description": "Service description"
    }
    resp = api.client.post('/openeo/0.4.0/services', content_type='application/json', json=post_data)
    assert resp.status_code == 201
    assert resp.headers['OpenEO-Identifier'] == 'c63d6c27-c4c2-4160-b7bd-9e32f582daec'
    assert resp.headers['Location'].endswith("/services/c63d6c27-c4c2-4160-b7bd-9e32f582daec/service/wmts")

    tiled_viewing_service = api.collections["S2"].tiled_viewing_service
    assert tiled_viewing_service.call_count == 1
    ProcessGraphVisitor.dereference_from_node_arguments(process_graph)
    tiled_viewing_service.assert_called_with(
        service_type="WMTS",
        process_graph=process_graph,
        post_data=post_data
    )


def test_create_wmts_100(api):
    process_graph = api.load_json("filter_temporal.json")
    post_data = {
        "type": 'WMTS',
        "process": {
            "process_graph": process_graph,
            "id": "filter_temporal_wmts"
        },
        "custom_param": 45,
        "title": "My Service",
        "description": "Service description"
    }
    resp = api.client.post('/openeo/1.0.0/services', content_type='application/json', json=post_data)
    assert resp.status_code == 201
    assert resp.headers['OpenEO-Identifier'] == 'c63d6c27-c4c2-4160-b7bd-9e32f582daec'
    assert resp.headers['Location'].endswith("/services/c63d6c27-c4c2-4160-b7bd-9e32f582daec/service/wmts")

    tiled_viewing_service = api.collections["S2"].tiled_viewing_service
    assert tiled_viewing_service.call_count == 1
    ProcessGraphVisitor.dereference_from_node_arguments(process_graph)
    tiled_viewing_service.assert_called_with(
        service_type="WMTS",
        process_graph=process_graph,
        post_data=post_data
    )



def test_read_vector(api):
    process_graph = api.load_json(
        "read_vector.json",
        preprocess=lambda s: s.replace("PLACEHOLDER", str(get_path("GeometryCollection.geojson")))
    )
    resp = api.check_result(process_graph)
    assert b'NaN' not in resp.data
    assert resp.json == {
        "2015-07-06T00:00:00": [2.9829132080078127],
        "2015-08-22T00:00:00": [None]
    }


def test_load_collection_without_spatial_extent_incorporates_read_vector_extent(api):
    process_graph = api.load_json(
        "read_vector_spatial_extent.json",
        preprocess=lambda s: s.replace("PLACEHOLDER", str(get_path("GeometryCollection.geojson")))
    )
    resp = api.check_result(process_graph)
    assert b'NaN' not in resp.data
    assert resp.json == {
        "2015-07-06T00:00:00": [2.9829132080078127],
        "2015-08-22T00:00:00": [None]
    }
    viewing_parameters = api.collections['PROBAV_L3_S10_TOC_NDVI_333M_V2'].viewingParameters
    assert viewing_parameters['left'] == pytest.approx(5.07616)
    assert viewing_parameters['bottom'] == pytest.approx(51.2122)
    assert viewing_parameters['right'] == pytest.approx(5.16685)
    assert viewing_parameters['top'] == pytest.approx(51.2689)
    assert viewing_parameters['srs'] == 'EPSG:4326'


def test_read_vector_from_feature_collection(api):
    process_graph = api.load_json(
        "read_vector_feature_collection.json",
        preprocess=lambda s: s.replace("PLACEHOLDER", str(get_path("FeatureCollection.geojson")))
    )
    resp = api.check_result(process_graph)
    assert b'NaN' not in resp.data
    assert resp.json == {
        "2015-07-06T00:00:00": [2.9829132080078127],
        "2015-08-22T00:00:00": [None]
    }


def test_no_nested_JSONResult(api):
    resp = api.client.post(
        path=api.url("/result"),
        content_type='application/json',
        json=api.load_json("no_nested_json_result.json"),
    )
    assert resp.status_code == 200
    assert resp.content_length > 0


def test_timeseries_point_with_bbox(api):
    process_graph = {
        "loadcollection1": {
            'process_id': 'load_collection',
            'arguments': {'id': 'S2_FAPAR_CLOUDCOVER'},
        },
        "filterbbox": {
            "process_id": "filter_bbox",
            "arguments": {
                "data": {"from_node": "loadcollection1"},
                "extent": {"west": 3, "east": 6, "south": 50, "north": 51, "crs": "EPSG:4326"}
            },
            "result": True
        }
    }
    resp = api.check_result(process_graph, path="/timeseries/point?x=1&y=2")
    assert resp.json == {"viewingParameters": {
        "left": 3, "right": 6, "bottom": 50, "top": 51, "srs": "EPSG:4326", "version": api.api_version
    }}


def test_load_disk_data(api):
    api.check_result("load_disk_data.json")


def test_mask_with_vector_file(api):
    process_graph = api.load_json(
        "mask_with_vector_file.json",
        preprocess=lambda s: s.replace("PLACEHOLDER", str(get_path("mask_polygons_3.43_51.00_3.46_51.02.json")))
    )
    api.check_result(process_graph)


def test_aggregate_feature_collection(api):
    api.check_result("aggregate_feature_collection.json")


def test_post_result_process_100(client):
    api = ApiTester(api_version="1.0.0", client=client, impl=dummy_impl)
    response = api.client.post(
        path=api.url('/result'),
        json={"process": {"process_graph": api.load_json("basic.json")}},
    )
    assert response.status_code == 200
    assert response.content_length > 0


def test_missing_process_graph(api):
    response = api.client.post(
        path=api.url('/result'),
        json={"foo": "bar"},
    )
    assert response.status_code == ProcessGraphMissingException.status_code
    assert response.json['code'] == 'ProcessGraphMissing'
