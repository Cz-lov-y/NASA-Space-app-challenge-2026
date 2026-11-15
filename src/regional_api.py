"""Local JSON API for the human-built globe; reading data never starts research."""
from collections import OrderedDict
from copy import deepcopy
from functools import lru_cache
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
from threading import Event, Lock
from urllib.parse import parse_qs, urlsplit

from src.regional_research import load_cached_report, qualitative_context_key, research_context_key
from src.regional_workflow import REGIONAL, ROOT, load_region
from src.region_transport import build_region_detail
from src.research_jobs import ResearchJobs

ALLOWED_ORIGINS = frozenset(('http://127.0.0.1:3000', 'http://localhost:3000'))
# Trusted host suffixes observed on official Canadian government pages. A host
# match is not proof of legal applicability, current policy status or review.
OFFICIAL_DOMAINS = {'Canada': ['canada.ca', 'gc.ca']}
SETTINGS = ('MODEL_API_KEY','MODEL_BASE_URL','MODEL_NAME','POLICY_SEARCH_API_KEY')
REGION_PATTERN = re.compile(r'grid_r(\d{2})_c(\d{2})\Z')


class APIError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


@lru_cache(maxsize=256)
def _digest(path, mtime, size):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _file_digest(path):
    stat = path.stat()
    return _digest(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _analysis(bundle):
    record = bundle.get('screening') or {}
    return deepcopy(record.get('available_indicator_analysis') or record.get('analysis') or {
        'region': bundle['region_id'], 'data_quality': {'qa_reviewed': False, 'synthetic_demo': False},
        'limitations': ['Paired regional analysis is unavailable.']})


class RegionalAPI:
    """Server-owned configuration and jobs; never accept provider settings in JSON.

    A single trusted local user's service. It is not an authenticated production
    multi-user API. Live POST access requires explicit server enablement.
    """
    def __init__(self, *, directory=REGIONAL, cache_dir=None, report_dir=None,
                 settings=None, live_enabled=False, jobs=None, fine_directory=None, tile_index=None,
                 global_raw_directory=None, global_cache_directory=None, global_wait_seconds=30,
                 native_modis_cache=None,native_modis_jobs=None,enable_native_modis=True):
        self.directory = Path(directory)
        self.fine_directory = Path(fine_directory or ROOT / "data/processed/fine/central_us")
        self._registered_fine = fine_directory is None
        self.tile_index = Path(tile_index or ROOT / 'data/processed/fine/tiles.json')
        self.global_raw_directory = Path(global_raw_directory or ROOT/'data/raw/gldas')
        self.global_cache_directory = Path(global_cache_directory or ROOT/'.cache/global_cells')
        if not isinstance(global_wait_seconds,(int,float)) or not math.isfinite(global_wait_seconds) or global_wait_seconds<=0:
            raise ValueError('Global wait must be finite and positive')
        self._global_wait_seconds=global_wait_seconds
        self._global_inflight=None
        self._global_cache_guard = Lock()
        self._global_memory = OrderedDict()
        from src.global_cell_modis import NativeModisJobs
        self.native_modis_cache=Path(native_modis_cache or ROOT/'.cache/global_modis')
        self.native_modis_jobs=native_modis_jobs or NativeModisJobs(cache_directory=self.native_modis_cache)
        self.enable_native_modis=bool(enable_native_modis)
        self.cache_dir = Path(cache_dir or ROOT / '.cache/regional_research')
        self.report_dir = Path(report_dir or ROOT / 'data/research')
        self._settings = {key: value for key,value in (settings or {}).items() if key in SETTINGS}
        self.live_enabled = bool(live_enabled)
        self.jobs = jobs if jobs is not None else ResearchJobs()

    def _global_source_signature(self):
        files=sorted(self.global_raw_directory.glob('*.nc4'))
        boundary=ROOT/'data/processed/regional/naturalearth_countries.geojson'
        if boundary.exists():
            files.append(boundary)
        return tuple((str(path.resolve()),path.stat().st_mtime_ns,path.stat().st_size) for path in files)

    def _global_native(self,region_id):
        from src.global_cell_data import load_global_cell
        from src.global_cell_analysis import analyze_global_cell
        signature=self._global_source_signature()
        key=(region_id,signature)
        with self._global_cache_guard:
            if key in self._global_memory:
                self._global_memory.move_to_end(key)
                return deepcopy(self._global_memory[key])
            record=self._global_inflight
            owner=record is None
            if owner:
                record={'key':key,'event':Event(),'result':None,'error':(503,'global_cell_unavailable')}
                self._global_inflight=record
            elif record['key']!=key:
                raise APIError(429,'global_cell_busy')
        if not owner:
            # React development reruns and repeated clicks share the physical
            # scan. They must not overwrite success with an artificial busy error.
            if not record['event'].wait(self._global_wait_seconds):
                raise APIError(503,'global_cell_wait_timeout')
            if record['error']:
                raise APIError(*record['error'])
            return deepcopy(record['result'])
        try:
            raw=load_global_cell(region_id,raw_directory=self.global_raw_directory,
                                 cache_directory=self.global_cache_directory)
            result=analyze_global_cell(raw)
            if self._global_source_signature()!=signature:
                raise APIError(409,'global_source_changed_retry')
            with self._global_cache_guard:
                self._global_memory[key]=deepcopy(result)
                self._global_memory.move_to_end(key)
                while len(self._global_memory)>16:
                    self._global_memory.popitem(last=False)
                record['result']=deepcopy(result)
                record['error']=None
            return result
        except APIError as exc:
            record['error']=(exc.status,exc.code)
            raise
        except Exception:
            record['error']=(503,'global_cell_unavailable')
            raise APIError(503,'global_cell_unavailable') from None
        finally:
            with self._global_cache_guard:
                self._global_inflight=None
                record['event'].set()

    def _registered_native(self,region_id):
        from src.fine_grid import cell_bbox,parse_cell_id
        from src.fine_workflow import load_tile_index
        bbox=cell_bbox(*parse_cell_id(region_id))
        registry=load_tile_index(index_path=self.tile_index)
        return any(t['bbox'][0]<=bbox[0] and t['bbox'][1]<=bbox[1]
                   and t['bbox'][2]>=bbox[2] and t['bbox'][3]>=bbox[3] for t in registry['tiles'])

    def _bundle(self, region_id):
        fine = region_id.startswith('gldas025_')
        if not fine:
            match = REGION_PATTERN.fullmatch(region_id)
            if not match or int(match[1]) >= 18 or int(match[2]) >= 36:
                raise APIError(404,'unknown_region')
        try:
            if fine:
                if self._registered_fine:
                    from src.fine_grid import parse_cell_id
                    parse_cell_id(region_id)
                    if self.tile_index.is_file() and self._registered_native(region_id):
                        from src.fine_workflow import load_registered_fine_region
                        bundle = load_registered_fine_region(region_id,index_path=self.tile_index)
                    else:
                        from src.global_cell_modis import batch_tile_directory
                        batch=batch_tile_directory(region_id)
                        if batch is not None:
                            bundle=load_region(region_id,directory=batch)
                            bundle['provenance']['global_batch_scope']='single-tile exploratory; not worldwide adjusted'
                        else:
                            bundle = self._global_native(region_id)
                            bundle['on_demand_native']=True
                            try:
                                from src.global_cell_modis import cached_native_modis
                                from src.global_screening import screen_global_cell
                                paired=cached_native_modis(bundle,cache_directory=self.native_modis_cache)
                                if paired is not None:
                                    bundle=screen_global_cell(paired)
                                    bundle['on_demand_native']=True
                            except (OSError,ValueError,KeyError,TypeError):
                                bundle['native_modis_error']='native_modis_cache_invalid'
                else:
                    from src.fine_workflow import load_fine_region
                    bundle = load_fine_region(region_id, directory=self.fine_directory)
            else:
                bundle = load_region(region_id, directory=self.directory)
        except ValueError as exc:
            from src.fine_workflow import FineCollectionStale
            if isinstance(exc,FineCollectionStale):
                raise APIError(409,'fine_collection_rebuild_required') from None
            raise APIError(404,'unknown_region') from None
        except (OSError, KeyError, TypeError):
            raise APIError(503,'regional_release_unavailable') from None
        if bundle['screening_status'] != 'current':
            raise APIError(409,'screening_rebuild_required')
        for jurisdiction in bundle['research_context']['jurisdictions']:
            if jurisdiction.get('name') in OFFICIAL_DOMAINS:
                jurisdiction['official_domains'] = deepcopy(OFFICIAL_DOMAINS[jurisdiction['name']])
        return bundle

    def _ndvi_state(self,bundle,*,start=False,retry=False):
        if not bundle.get('on_demand_native'):
            return None
        if bundle.get('native_modis_error'):
            return {'state':'failed','error_code':bundle['native_modis_error'],'retryable':False}
        if bundle['provenance'].get('native_ndvi'):
            return {'state':'complete','completed_years':22,'total_years':22,'retryable':False}
        if not bundle['observations'].value.notna().any():
            return {'state':'not_applicable','error_code':'no_valid_native_soil','retryable':False}
        if not self.enable_native_modis:
            return {'state':'unavailable','error_code':'native_modis_disabled','retryable':False}
        if not start:return {'state':'not_requested','retryable':True}
        state=self.native_modis_jobs.submit(bundle,retry=retry)
        if state.get('request_id'):
            state['poll_url']=f"/api/v1/data-jobs/{state['request_id']}?region_id={bundle['region_id']}&context_key={state['context_key']}"
        state['retry_url']=f"/api/v1/regions/{bundle['region_id']}/ndvi"
        return state

    def _detail(self,bundle,*,start_native=False):
        detail=build_region_detail(bundle)
        if detail.get('screening') and bundle['provenance'].get('family_id'):
            detail['screening'].setdefault('family_scope','Joint correction across six frozen selected tiles; not a worldwide search')
            detail['screening']['family_id']=bundle['provenance']['family_id']
        if detail.get('screening') and bundle['provenance'].get('global_batch_scope'):
            detail['screening']['family_scope']=bundle['provenance']['global_batch_scope']
            detail['screening']['probability']=None
        detail['research']=self._descriptor(bundle)
        if 'availability' in bundle:detail['availability']=deepcopy(bundle['availability'])
        if 'status' in bundle:detail['status']=bundle['status']
        detail['hasData']=bool(bundle['observations']['value'].notna().any()) if 'value' in bundle['observations'] else False
        state=self._ndvi_state(bundle,start=start_native)
        if state is not None:detail['ndvi_retrieval']=state
        return detail

    def _descriptor(self, bundle):
        region = bundle['region_id']
        return {'context_key': research_context_key(bundle['research_context']),
                'can_start_live': self.live_enabled and all(self._settings.get(k) for k in SETTINGS)
                    and bool(bundle['research_context']['jurisdictions']),
                'start_url': f'/api/v1/regions/{region}/research',
                'cached_url': f'/api/v1/regions/{region}/research/cached',
                'jurisdictions': deepcopy(bundle['research_context']['jurisdictions']),
                'limitations': ['Official-domain matching does not validate policy status or geographic applicability.']}

    def handle(self, method, target, body=None):
        """Return (HTTP status, JSON payload); no raw errors or credential output."""
        try:
            return self._handle(method,target,body)
        except APIError as exc:
            return exc.status, {'error': {'code': exc.code}}
        except (OSError, ValueError, KeyError, TypeError):
            return 503, {'error': {'code':'backend_unavailable'}}

    def _handle(self, method,target,body):
        url = urlsplit(target)
        if url.scheme or url.netloc or url.fragment:
            raise APIError(400,'invalid_target')
        path = url.path
        query = parse_qs(url.query,keep_blank_values=True)
        if path not in ('/api/v1/fine-regions','/api/v1/cell','/api/v1/global-screened-cells') and not path.startswith(('/api/v1/jobs/','/api/v1/data-jobs/')) and query:
            raise APIError(400,'unexpected_query')
        if method == 'GET' and path in ('/health','/api/v1/health'):
            return 200, {'status':'ok','api_version':'v1','live_enabled':self.live_enabled,
                'configured':{key:bool(self._settings.get(key)) for key in SETTINGS},
                'release_files_present':all((self.directory/name).is_file() for name in
                    ('catalog.json','monthly_timeseries.csv','screening.json','map_screening.geojson'))}
        if method=='GET' and path=='/api/v1/global-screened-cells':
            if set(query)-{'limit','offset'} or any(len(v)!=1 for v in query.values()):
                raise APIError(400,'invalid_page')
            try:
                limit=int(query.get('limit',['1000'])[0]);offset=int(query.get('offset',['0'])[0])
                if not 1<=limit<=1000 or offset<0:raise ValueError()
            except ValueError:raise APIError(400,'invalid_page') from None
            from src.global_cell_modis import all_screened_summaries
            return 200,all_screened_summaries(cache_directory=self.native_modis_cache,limit=limit,offset=offset)
        data_match=re.fullmatch(r'/api/v1/data-jobs/([a-f0-9]{32})',path)
        if method=='GET' and data_match:
            if set(query)!={'region_id','context_key'} or any(len(v)!=1 or not v[0] for v in query.values()):
                raise APIError(400,'region_and_context_required')
            rid=query['region_id'][0]
            state=self.native_modis_jobs.poll(data_match[1],region_id=rid,context_key=query['context_key'][0])
            if state['state']=='complete':
                base=self._global_native(rid)
                current_key=hashlib.sha256((rid+base['research_context']['dataset_version']).encode()).hexdigest()
                if current_key!=query['context_key'][0]:
                    raise APIError(409,'native_data_source_changed')
                state['detail']=self._detail(self._bundle(rid),start_native=False)
            return (404 if state['state']=='unknown' else 409 if state['state']=='stale' else 200),state
        if method == 'GET' and path == '/api/v1/cell':
            if set(query)!={'lon','lat'} or any(len(v)!=1 or not v[0] for v in query.values()):
                raise APIError(400,'longitude_and_latitude_required')
            try:
                lon,lat=float(query['lon'][0]),float(query['lat'][0])
                if not math.isfinite(lon) or not math.isfinite(lat) or not -180<=lon<=180 or not -90<=lat<=90:
                    raise ValueError('Invalid coordinate')
                from src.global_cell_data import locate_cell
                found=locate_cell(lon,lat)
            except ValueError:
                raise APIError(400,'invalid_coordinate') from None
            region=found.get('region_id')
            return 200, {'schema_version':'global-cell-lookup-1',**found,
                'coordinates':{'lon':lon,'lat':lat},
                'detail_url':f'/api/v1/regions/{region}' if region else None,
                'limitations':['Cell geometry does not establish product availability; inspect actual cell observations.']}
        if method == 'GET' and path == '/api/v1/fine-tiles':
            if not self._registered_fine or not self.tile_index.is_file():
                raise APIError(404,'tile_registry_unavailable')
            from src.fine_workflow import fine_tiles
            return 200, fine_tiles(index_path=self.tile_index)
        if method == 'GET' and path == '/api/v1/fine-regions':
            if set(query)-{'tile_id'} or ('tile_id' in query and (len(query['tile_id'])!=1 or not query['tile_id'][0])):
                raise APIError(400,'invalid_tile_query')
            if self._registered_fine and self.tile_index.is_file():
                from src.fine_workflow import load_tile_index,registered_fine_map,DEFAULT_TILE
                registry = load_tile_index(index_path=self.tile_index)
                tile_id = query.get('tile_id',[DEFAULT_TILE])[0]
                if tile_id not in {tile['id'] for tile in registry['tiles']}:
                    raise APIError(404,'unknown_tile')
                try:
                    return 200, registered_fine_map(tile_id,index_path=self.tile_index)
                except ValueError:
                    raise APIError(409,'fine_collection_rebuild_required') from None
            if query:
                raise APIError(400,'tile_selection_not_configured')
            from src.fine_workflow import fine_map
            return 200, fine_map(directory=self.fine_directory)
        if method == 'GET' and path == '/api/v1/regions':
            self._bundle('grid_r00_c00')
            payload = json.loads((self.directory/'map_screening.geojson').read_text())
            if (payload.get('source_csv_sha256') != _file_digest(self.directory/'monthly_timeseries.csv')
                    or payload.get('source_catalog_sha256') != _file_digest(self.directory/'catalog.json')):
                raise APIError(409,'map_rebuild_required')
            return 200,payload
        match = re.fullmatch(r'/api/v1/regions/([^/]+)(/(?:research(?:/cached)?|ndvi))?',path)
        if match:
            bundle = self._bundle(match[1])
            suffix = match[2]
            if method == 'GET' and suffix is None:
                return 200,self._detail(bundle,start_native=True)
            if method=='POST' and suffix=='/ndvi':
                if body!={}:raise APIError(400,'data_body_must_be_empty_object')
                state=self._ndvi_state(bundle,start=True,retry=True)
                if state is None:raise APIError(409,'not_on_demand_cell')
                return 202,state
            if method == 'GET' and suffix == '/research/cached':
                context = bundle['research_context']
                key = research_context_key(context)
                candidates = (self.cache_dir/(key+'.json'),
                              self.cache_dir/'contexts'/(qualitative_context_key(context)+'.json'),
                              self.report_dir/(bundle['region_id']+'_context_brief.json'))
                for candidate in candidates:
                    try:
                        report = load_cached_report(candidate,_analysis(bundle),context,allow_data_revision=True)
                        if not (bundle.get('screening') or {}).get('analysis'):
                            report['limitations'].append('Paired regional analysis is unavailable; research provides jurisdiction context only.')
                        return 200,report
                    except ValueError:
                        continue
                raise APIError(404,'matching_cached_research_unavailable')
            if method == 'POST' and suffix == '/research':
                if body != {}:
                    raise APIError(400,'research_body_must_be_empty_object')
                if not self.live_enabled:
                    raise APIError(403,'live_research_disabled')
                if not all(self._settings.get(key) for key in SETTINGS):
                    raise APIError(503,'research_not_configured')
                if not bundle['research_context']['jurisdictions']:
                    raise APIError(409,'research_needs_jurisdiction')
                try:
                    request = self.jobs.submit(bundle,environ=self._settings,cache_dir=self.cache_dir)
                except RuntimeError:
                    raise APIError(429,'research_queue_busy') from None
                request['poll_url'] = f"/api/v1/jobs/{request['request_id']}?region_id={bundle['region_id']}&context_key={request['context_key']}"
                return 202,request
            raise APIError(405,'method_not_allowed')
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})',path)
        if match and method == 'GET':
            if set(query) != {'region_id','context_key'} or any(len(v)!=1 or not v[0] for v in query.values()):
                raise APIError(400,'region_and_context_required')
            region,key = query['region_id'][0],query['context_key'][0]
            bundle = self._bundle(region)
            if research_context_key(bundle['research_context']) != key:
                raise APIError(409,'research_context_stale')
            result = self.jobs.poll(match[1],region_id=region,context_key=key)
            return (404 if result['state']=='unknown' else 409 if result['state']=='stale' else 200),result
        raise APIError(404,'route_not_found')

    def close(self):
        self.jobs.close(wait=False)
        self.native_modis_jobs.close()


def make_server(api=None, *, host='127.0.0.1', port=8000):
    """Create a loopback-only HTTP server. No request or secret access logs."""
    if host not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Only loopback hosts are supported')
    api = api or RegionalAPI()
    # IPv4 loopback keeps behavior consistent for localhost across platforms.
    address = '127.0.0.1' if host in ('localhost','::1') else host
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self,*args):
            pass
        def _reply(self,status,payload):
            try:
                content = json.dumps(payload,allow_nan=False,separators=(',',':')).encode()
            except (ValueError,TypeError):
                status,content = 503,b'{"error":{"code":"invalid_backend_payload"}}'
            self.send_response(status)
            origin=self.headers.get('Origin')
            if origin in ALLOWED_ORIGINS:
                self.send_header('Access-Control-Allow-Origin',origin)
                self.send_header('Vary','Origin')
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(content)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            if self.command=='OPTIONS':
                self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers','Content-Type')
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError,ConnectionResetError):
                pass
        def _allowed(self):
            # Exact Origin checks plus loopback Host validation limit browser
            # cross-site access and DNS-rebinding; this is not authentication.
            origin=self.headers.get('Origin')
            if origin is not None and origin not in ALLOWED_ORIGINS:
                self._reply(403,{'error':{'code':'origin_not_allowed'}})
                return False
            host=self.headers.get('Host','')
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if host not in allowed:
                self._reply(403,{'error':{'code':'host_not_allowed'}})
                return False
            return True
        def do_OPTIONS(self):
            if self._allowed():
                self._reply(200,{'status':'ok'})
        def do_GET(self):
            if self._allowed():
                self._reply(*api.handle('GET',self.path))
        def do_POST(self):
            if not self._allowed():
                self.close_connection=True
                return
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if not 0 < length <= 1024 or self.headers.get('Transfer-Encoding'):
                    raise ValueError()
                if self.headers.get('Content-Type','').split(';',1)[0].strip()!='application/json':
                    raise ValueError()
                body=json.loads(self.rfile.read(length))
            except (ValueError,UnicodeDecodeError):
                self.close_connection=True
                self._reply(400,{'error':{'code':'invalid_json_body'}})
                return
            self._reply(*api.handle('POST',self.path,body))
    server=ThreadingHTTPServer((address,port),Handler)
    server.daemon_threads=True
    return server
