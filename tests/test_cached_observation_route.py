from src.regional_api import RegionalAPI


def test_cached_observations_never_start_native_retrieval():
    api = RegionalAPI.__new__(RegionalAPI)
    calls = []
    api._bundle = lambda region_id, raw_only=False: {'region_id': region_id}
    api._raw_observations = lambda bundle, start_native=False: calls.append(start_native) or bundle
    route = '/api/v1/regions/gldas025_r388_c0328/observations'
    assert api.handle('GET', route + '?start_native=0')[0] == 200
    assert calls == [False]
    assert api.handle('GET', route)[0] == 200
    assert calls == [False, True]
    for query in ('start_native=bad', 'start_native=0&start_native=1', 'other=1'):
        assert api.handle('GET', route + '?' + query)[0] == 400
