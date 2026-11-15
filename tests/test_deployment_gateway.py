from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import requests

from deploy.gateway import create_server


def test_passcode_gate_and_api_proxy(tmp_path):
    class API(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            body=b'{"ok":true}';self.send_response(200);self.send_header('Content-Length',str(len(body)));self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
        def do_POST(self):
            size=int(self.headers['Content-Length']);self.rfile.read(size);self.send_response(202);self.send_header('Content-Length','0');self.end_headers()
    api=ThreadingHTTPServer(('127.0.0.1',0),API);Thread(target=api.serve_forever,daemon=True).start()
    (tmp_path/'index.html').write_text('<h1>Real frontend</h1>')
    origin='https://demo.example';gateway=create_server(passcode='a-strong-demo-code',session_key='a'*64,origin=origin,static_dir=tmp_path,port=0,api_port=api.server_port)
    Thread(target=gateway.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{gateway.server_port}'
    try:
        assert requests.get(base+'/',allow_redirects=False).status_code==303
        assert requests.get(base+'/api/v1/regions').status_code==401
        assert requests.post(base+'/login',data={'code':'a-strong-demo-code'},headers={'Origin':'https://attacker.example'}).status_code==403
        assert requests.post(base+'/login',data={'code':'wrong-code'},headers={'Origin':origin}).status_code==401
        login=requests.post(base+'/login',data={'code':'a-strong-demo-code'},headers={'Origin':origin},allow_redirects=False)
        assert login.status_code==303
        cookie=login.headers['Set-Cookie'];assert all(x in cookie for x in ('Secure','HttpOnly','SameSite=Strict'))
        headers={'Cookie':cookie.split(';')[0]}
        assert 'Real frontend' in requests.get(base+'/',headers=headers).text
        assert requests.get(base+'/api/v1/regions',headers=headers).json()=={'ok':True}
        assert requests.post(base+'/api/v1/regions/a/research',headers={**headers,'Origin':'https://attacker.example'},json={}).status_code==403
        assert requests.post(base+'/api/v1/regions/a/research',headers={**headers,'Origin':origin},json={}).status_code==202
    finally:
        gateway.shutdown();gateway.server_close();api.shutdown();api.server_close()


def test_login_attempts_are_rate_limited_and_cookie_tampering_fails(tmp_path):
    (tmp_path/'index.html').write_text('frontend')
    origin='https://demo.example'
    gateway=create_server(passcode='secure-demo-code',session_key='b'*64,origin=origin,static_dir=tmp_path,port=0)
    Thread(target=gateway.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{gateway.server_port}'
    try:
        for _ in range(8):
            assert requests.post(base+'/login',data={'code':'wrong'},headers={'Origin':origin}).status_code==401
        assert requests.post(base+'/login',data={'code':'secure-demo-code'},headers={'Origin':origin}).status_code==429
        assert requests.get(base+'/api/v1/regions',headers={'Cookie':'earthrisk_session=9999999999.bad.invalid'}).status_code==401
    finally:
        gateway.shutdown();gateway.server_close()
