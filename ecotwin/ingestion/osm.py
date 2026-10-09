"""Bounded Overpass GeoJSON conversion and offline PBF parsing."""
import json
from pathlib import Path
from shapely.geometry import Polygon,LineString,Point,mapping,shape
from shapely.ops import polygonize,unary_union
from ecotwin.errors import TwinError

URL='https://overpass-api.de/api/interpreter'
KEYS=['building','highway','leisure','natural','waterway','landuse','amenity','power']

def category(tags):
    if 'building' in tags: return 'building'
    if 'highway' in tags: return 'road'
    if tags.get('natural')=='tree': return 'mapped_tree'
    if tags.get('natural')=='water' or 'waterway' in tags: return 'water'
    if tags.get('leisure') in {'park','garden'}: return 'park'
    if tags.get('natural')=='wood': return 'wood'
    if tags.get('amenity') in {'recycling','waste_disposal'}: return 'waste_facility'
    if 'power' in tags: return 'power'
    return 'landuse'

def fetch_osm(client,boundary):
    w,s,e,n=boundary.bounds
    selectors=''.join(f'nwr["{key}"]({s},{w},{n},{e});' for key in KEYS)
    document=client.request('POST',URL,data={'data':f'[out:json][timeout:25];({selectors});out geom;'}).json()
    features=[]
    for item in document.get('elements',[]):
        tags=item.get('tags',{})
        if not any(k in tags for k in KEYS):continue
        geom=None
        if item['type']=='node':
            geom=Point(item['lon'],item['lat'])
        elif item['type']=='way':
            coordinates=[(p['lon'],p['lat']) for p in item.get('geometry',[])]
            if len(coordinates)>=2:
                geom=Polygon(coordinates) if coordinates[0]==coordinates[-1] and len(coordinates)>=4 and (('building' in tags or 'landuse' in tags or 'leisure' in tags or tags.get('natural') in {'water','wood'}) and tags.get('area')!='no') else LineString(coordinates)
        elif item['type']=='relation':
            outer=[];inner=[]
            for member in item.get('members',[]):
                coords=[(p['lon'],p['lat']) for p in member.get('geometry',[])]
                if len(coords)>=2:
                    (inner if member.get('role')=='inner' else outer).append(LineString(coords))
            if outer:
                geom=unary_union(list(polygonize(outer))).difference(unary_union(list(polygonize(inner))))
        if geom is not None and not geom.is_empty:
            features.append({'type':'Feature','id':f"osm:{item['type']}/{item['id']}",'properties':tags,'geometry':mapping(geom)})
    return {'type':'FeatureCollection','features':features}

def parse_geojson(document,boundary):
    if document.get('type')!='FeatureCollection':
        raise TwinError('UPSTREAM_PAYLOAD_INVALID','OSM cache must be a GeoJSON FeatureCollection')
    seen=set();output=[];rejected=0
    for item in document['features']:
        if len(output)>=250000:
            raise TwinError('MODEL_INPUT_UNSUPPORTED','Study area exceeds 250000 vector features')
        identifier=str(item.get('id',''))
        if not identifier.startswith(('osm:node/','osm:way/','osm:relation/')):
            raise TwinError('UPSTREAM_PAYLOAD_INVALID','OSM features require typed provider identifiers')
        if identifier in seen:continue
        seen.add(identifier)
        geom=shape(item['geometry'])
        if not geom.is_valid:
            rejected+=1;continue
        geom=geom.intersection(boundary)
        if geom.is_empty:continue
        output.append({'provider_feature_id':identifier,'category':category(item['properties']),'tags':item['properties'],'geom':geom})
    return output,rejected

def pbf_geojson(path: Path):
    import osmium
    import shapely.wkb
    factory=osmium.geom.WKBFactory()
    features=[]
    class Handler(osmium.SimpleHandler):
        def add(self,obj,kind,method):
            tags=dict(obj.tags)
            if not any(k in tags for k in KEYS):return
            try:
                geom=shapely.wkb.loads(getattr(factory,method)(obj),hex=True)
                features.append({'type':'Feature','id':f'osm:{kind}/{obj.id}','properties':tags,'geometry':mapping(geom)})
            except RuntimeError as exc:
                raise TwinError('UPSTREAM_PAYLOAD_INVALID','PBF has unresolved geometry; crop with complete references') from exc
        def node(self,obj):self.add(obj,'node','create_point')
        def way(self,obj):
            if not obj.is_closed():self.add(obj,'way','create_linestring')
        def area(self,obj):
            self.add(obj,'way' if obj.from_way() else 'relation','create_multipolygon')
    Handler().apply_file(str(path),locations=True)
    return {'type':'FeatureCollection','features':features}
