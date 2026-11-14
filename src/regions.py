"""Stable, exhaustive 10-degree geographic cells; no inferred jurisdictions."""
import math

RADIUS_M = 6371007.181


def make_grid():
    features = []
    for row in range(18):
        south = -90 + row * 10
        north = south + 10
        for col in range(36):
            west, east = -180 + col * 10, -170 + col * 10
            rid = f'grid_r{row:02d}_c{col:02d}'
            area = RADIUS_M**2 * math.radians(10) * (math.sin(math.radians(north)) - math.sin(math.radians(south)))
            features.append({'type': 'Feature', 'id': rid,
                'geometry': {'type': 'Polygon', 'coordinates': [[[west,south],[east,south],[east,north],[west,north],[west,south]]]},
                'properties': {'region_id': rid, 'name': f'{south} to {north} N, {west} to {east} E',
                    'bbox': [west,south,east,north], 'centroid': [(west+east)/2,(south+north)/2],
                    'region_area_m2': area, 'crs': 'EPSG:4326', 'variables': [],
                    'data_status': 'pending', 'jurisdictions': [], 'jurisdiction_status': 'not_resolved'}})
    return {'type': 'FeatureCollection', 'features': features}


def add_jurisdictions(catalog, boundaries):
    """Intersect coarse public-domain country polygons, including coastal cells.

    Area fractions rank geographic overlaps; they do not establish legal authority.
    Natural Earth depiction is approximate and includes disputed-boundary choices.
    """
    from shapely.geometry import shape
    from pyproj import Geod
    geod = Geod(a=RADIUS_M, b=RADIUS_M)
    countries = [(shape(f['geometry']),f['properties']) for f in boundaries['features']]
    for feature in catalog['features']:
        polygon=shape(feature['geometry']);overlaps=[]
        for country, props in countries:
            if not polygon.intersects(country): continue
            overlap=polygon.intersection(country)
            if overlap.is_empty or overlap.area==0: continue
            # Geodesic area correctly handles the pole; use positive polygon areas.
            def area(g):
                if g.geom_type=='Polygon': return abs(geod.geometry_area_perimeter(g)[0])
                if hasattr(g,'geoms'): return sum(area(part) for part in g.geoms)
                return 0
            size=area(overlap)
            if size<=0: continue
            name=props.get('ADMIN') or props.get('NAME')
            overlaps.append({'name':name,'country_code':props.get('ISO_A2_EH') or props.get('ISO_A2'),
                'overlap_area_m2':size,'region_area_fraction':size/feature['properties']['region_area_m2'],
                'boundary_source':'Natural Earth 1:110m admin_0_countries',
                'uncertainty':'Coarse geographic intersection; disputed boundaries and policy authority require source review.'})
        total=sum(x['overlap_area_m2'] for x in overlaps)
        for item in overlaps: item['land_area_fraction']=item['overlap_area_m2']/total
        feature['properties']['jurisdictions']=sorted(overlaps,key=lambda x:x['overlap_area_m2'],reverse=True)
        feature['properties']['jurisdiction_status']='geographic_candidates' if overlaps else 'no_country_overlap_in_coarse_boundary'
    return catalog
