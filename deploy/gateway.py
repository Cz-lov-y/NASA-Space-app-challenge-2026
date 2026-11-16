#!/usr/bin/env python3
"""Passcode gateway for a small EarthRisk demo behind a trusted TLS proxy.

Only bind to loopback; the TLS proxy must overwrite X-Real-IP and strip
untrusted forwarding headers. Secrets are supplied through the environment.
"""
from collections import defaultdict, deque
import hashlib
import hmac
from http import cookies
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import os
from pathlib import Path
import secrets
import sqlite3
from threading import Lock
import time
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[1]
LOGIN_PAGE=b'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EarthRisk access</title><style>body{font:16px system-ui;background:#e8f5fa;color:#17334a;display:grid;place-items:center;min-height:100vh;margin:0}.box{background:white;border:1px solid #b8d7e4;border-radius:16px;padding:2rem;width:min(360px,80vw);box-shadow:0 8px 30px #25485b25}h1{font-size:24px}input,button{box-sizing:border-box;width:100%;padding:12px;margin-top:10px;border-radius:8px;font:inherit}input{border:1px solid #8aadb9}button{color:white;background:#075b73;border:0;cursor:pointer}</style><div class="box"><h1>EarthRisk</h1><p>Enter the access code to explore the map.</p><form method="post" action="/login"><label for="code">Access code</label><input id="code" name="code" type="password" autocomplete="current-password" required autofocus><button type="submit">Continue</button></form></div></html>'''
SESSION_SECONDS=12*60*60

class Limit:
    def __init__(self): self.lock=Lock();self.values=defaultdict(deque)
    def allow(self,key,count,seconds):
        now=time.monotonic()
        with self.lock:
            # Bound memory even under a stream of different client addresses.
            if len(self.values)>10000:
                for k in list(self.values):
                    if not self.values[k] or now-self.values[k][-1]>3600:del self.values[k]
                if len(self.values)>10000:return False
            events=self.values[key]
            while events and now-events[0]>=seconds:events.popleft()
            if len(events)>=count:return False
            events.append(now);return True


class ResearchQuota:
    """Persistent per-address and shared daily limits, charged only on POST."""
    def __init__(self,path,per_hour=3,per_day=30):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.per_hour=per_hour;self.per_day=per_day;self.lock=Lock()
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests (client TEXT NOT NULL, created REAL NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS requests_created ON requests(created)')
    def allow(self,client):
        now=time.time()
        with self.lock,sqlite3.connect(self.path,timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM requests WHERE created < ?', (now-86400,))
            daily=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
            hourly=db.execute('SELECT COUNT(*) FROM requests WHERE client=? AND created>=?',(client,now-3600)).fetchone()[0]
            if daily>=self.per_day or hourly>=self.per_hour:return False
            db.execute('INSERT INTO requests(client,created) VALUES(?,?)',(client,now))
            return True


def create_server(*, passcode='', session_key='', origin, static_dir=ROOT/'frontend/dist', port=8081, api_port=8000, public=False, quota_path=ROOT/'.cache/public_research_quota.sqlite', research_per_hour=3, research_per_day=30):
    if not public and (not passcode or len(passcode)<10 or not session_key or len(session_key)<32):
        raise ValueError('A passcode of at least 10 characters and a session key of at least 32 characters are required')
    if not origin.startswith('https://') or urlsplit(origin).path not in ('','/'):
        raise ValueError('A public HTTPS origin is required')
    origin=origin.rstrip('/');static=Path(static_dir).resolve();limiter=Limit()
    key=session_key.encode();expected=passcode.encode()
    quota=ResearchQuota(quota_path,research_per_hour,research_per_day)
    def signed():
        expiry=str(int(time.time())+SESSION_SECONDS)
        nonce=secrets.token_hex(16);payload=f'{expiry}.{nonce}'
        return payload+'.'+hmac.new(key,payload.encode(),hashlib.sha256).hexdigest()
    def authenticated(header):
        try:
            jar=cookies.SimpleCookie();jar.load(header or '');value=jar['earthrisk_session'].value
            expiry,nonce,signature=value.split('.')
            payload=f'{expiry}.{nonce}'
            return int(expiry)>=int(time.time()) and hmac.compare_digest(signature,hmac.new(key,payload.encode(),hashlib.sha256).hexdigest())
        except (KeyError,ValueError,cookies.CookieError):return False
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def send_body(self,status,body,content_type='text/plain; charset=utf-8',headers=()):
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            for k,v in headers:self.send_header(k,v)
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def client(self):
            value=self.headers.get('X-Real-IP','')
            return value[:64] if value else self.client_address[0]
        def valid_origin(self):return self.headers.get('Origin')==origin
        def login(self):
            if not self.valid_origin():
                self.close_connection=True;return self.send_body(403,b'Forbidden')
            if not limiter.allow(('login',self.client()),8,600):
                self.close_connection=True;return self.send_body(429,b'Try again later.')
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>1024 or self.headers.get('Transfer-Encoding'):raise ValueError()
                data=parse_qs(self.rfile.read(size).decode('utf-8'),keep_blank_values=True)
                code=data.get('code',[])
                if len(code)!=1:raise ValueError()
            except (ValueError,UnicodeDecodeError):return self.send_body(400,b'Invalid request')
            if not hmac.compare_digest(code[0].encode(),expected):return self.send_body(401,LOGIN_PAGE,'text/html; charset=utf-8')
            cookie=f'earthrisk_session={signed()}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Strict'
            return self.send_body(303,b'',headers=[('Set-Cookie',cookie),('Location','/')])
        def proxy(self,path,body=None):
            if self.command=='POST' and not self.valid_origin():return self.send_body(403,b'Forbidden')
            if self.command=='POST' and '/research' in path and not quota.allow(self.client()):return self.send_body(429,b'{"error":{"code":"research_limit_reached"}}','application/json')
            if self.command=='POST' and path.split('?')[0].endswith('/ndvi') and not limiter.allow(('ndvi',self.client()),20,3600):return self.send_body(429,b'Too many data requests')
            if self.command=='GET' and '/observations' in path and 'start_native=0' not in path and not limiter.allow(('observations',self.client()),40,3600):return self.send_body(429,b'Too many location requests')
            try:
                connection=HTTPConnection('127.0.0.1',api_port,timeout=45)
                headers={'Host':f'127.0.0.1:{api_port}'}
                if body is not None:headers['Content-Type']='application/json'
                connection.request(self.command,path,body=body,headers=headers)
                response=connection.getresponse();data=response.read();ctype=response.getheader('Content-Type','application/json');status=response.status;connection.close()
                return self.send_body(status,data,ctype)
            except (OSError,TimeoutError):return self.send_body(503,b'{"error":{"code":"service_unavailable"}}','application/json')
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/login':
                return self.send_body(303,b'',headers=[('Location','/')]) if public else self.send_body(200,LOGIN_PAGE,'text/html; charset=utf-8')
            if not public and not authenticated(self.headers.get('Cookie')):
                if path.startswith('/api/'):return self.send_body(401,b'{"error":{"code":"authentication_required"}}','application/json')
                return self.send_body(303,b'',headers=[('Location','/login')])
            if path.startswith('/api/') or path=='/health':return self.proxy(self.path)
            try:
                candidate=(static/path.lstrip('/')).resolve()
                if not candidate.is_relative_to(static):raise ValueError()
                if not candidate.is_file():candidate=static/'index.html'
                content=candidate.read_bytes()
                return self.send_body(200,content,mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream')
            except (OSError,ValueError):return self.send_body(404,b'Not found')
        def do_POST(self):
            path=urlsplit(self.path).path
            if path=='/login':
                if public:
                    self.close_connection=True;return self.send_body(404,b'Not found')
                return self.login()
            if not public and not authenticated(self.headers.get('Cookie')):
                self.close_connection=True;return self.send_body(401,b'Authentication required')
            if not path.startswith('/api/'):
                self.close_connection=True;return self.send_body(404,b'Not found')
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>1024 or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';',1)[0]!='application/json':raise ValueError()
                body=self.rfile.read(size)
            except ValueError:
                self.close_connection=True;return self.send_body(400,b'Invalid request')
            return self.proxy(self.path,body)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    return server


def main():
    server=create_server(passcode=os.environ.get('EARTHRISK_PASSCODE',''),session_key=os.environ.get('EARTHRISK_SESSION_KEY',''),origin=os.environ['EARTHRISK_PUBLIC_ORIGIN'],port=int(os.environ.get('EARTHRISK_GATEWAY_PORT','8081')),public=os.environ.get('EARTHRISK_PUBLIC_ACCESS')=='1',research_per_hour=int(os.environ.get('EARTHRISK_RESEARCH_PER_HOUR','3')),research_per_day=int(os.environ.get('EARTHRISK_RESEARCH_PER_DAY','30')))
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
