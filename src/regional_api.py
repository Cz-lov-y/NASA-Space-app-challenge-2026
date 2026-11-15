"""Local JSON API for the human-built globe; reading data never starts research."""
from copy import deepcopy
from functools import lru_cache
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from src.regional_research import load_cached_report, research_context_key
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


@lru_cache(maxsize=16)
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
                 settings=None, live_enabled=False, jobs=None):
        self.directory = Path(directory)
        self.cache_dir = Path(cache_dir or ROOT / '.cache/regional_research')
        self.report_dir = Path(report_dir or ROOT / 'data/research')
        self._settings = {key: value for key,value in (settings or {}).items() if key in SETTINGS}
        self.live_enabled = bool(live_enabled)
        self.jobs = jobs if jobs is not None else ResearchJobs()

    def _bundle(self, region_id):
        match = REGION_PATTERN.fullmatch(region_id)
        if not match or int(match[1]) >= 18 or int(match[2]) >= 36:
            raise APIError(404,'unknown_region')
        try:
            bundle = load_region(region_id, directory=self.directory)
        except (OSError, ValueError, KeyError, TypeError):
            raise APIError(503,'regional_release_unavailable') from None
        if bundle['screening_status'] != 'current':
            raise APIError(409,'screening_rebuild_required')
        for jurisdiction in bundle['research_context']['jurisdictions']:
            if jurisdiction.get('name') in OFFICIAL_DOMAINS:
                jurisdiction['official_domains'] = deepcopy(OFFICIAL_DOMAINS[jurisdiction['name']])
        return bundle

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
        if path != '/api/v1/jobs/' and not path.startswith('/api/v1/jobs/') and query:
            raise APIError(400,'unexpected_query')
        if method == 'GET' and path in ('/health','/api/v1/health'):
            return 200, {'status':'ok','api_version':'v1','live_enabled':self.live_enabled,
                'configured':{key:bool(self._settings.get(key)) for key in SETTINGS},
                'release_files_present':all((self.directory/name).is_file() for name in
                    ('catalog.json','monthly_timeseries.csv','screening.json','map_screening.geojson'))}
        if method == 'GET' and path == '/api/v1/regions':
            self._bundle('grid_r00_c00')
            payload = json.loads((self.directory/'map_screening.geojson').read_text())
            if (payload.get('source_csv_sha256') != _file_digest(self.directory/'monthly_timeseries.csv')
                    or payload.get('source_catalog_sha256') != _file_digest(self.directory/'catalog.json')):
                raise APIError(409,'map_rebuild_required')
            return 200,payload
        match = re.fullmatch(r'/api/v1/regions/([^/]+)(/research(?:/cached)?)?',path)
        if match:
            bundle = self._bundle(match[1])
            suffix = match[2]
            if method == 'GET' and suffix is None:
                detail = build_region_detail(bundle)
                detail['research'] = self._descriptor(bundle)
                return 200,detail
            if method == 'GET' and suffix == '/research/cached':
                context = bundle['research_context']
                key = research_context_key(context)
                candidates = (self.cache_dir/(key+'.json'),
                              self.report_dir/(bundle['region_id']+'_context_brief.json'))
                for candidate in candidates:
                    try:
                        report = load_cached_report(candidate,_analysis(bundle),context)
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
