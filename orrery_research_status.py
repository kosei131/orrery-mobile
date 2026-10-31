"""Loopback-only authenticated viewer of one re-audited research snapshot.
No MT5, job submission, arbitrary files, remote host option or live heartbeat.
"""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit
from orrery_research_summary import build_summary, _uuid
from lsr04_tick_archive import _decode, _encode, _read_metadata

HOST, PORT = '127.0.0.1', 8766
MAX_RESPONSE = 65536
TOKEN_PATTERN = r'[A-Za-z0-9_-]{43}'


def token_file(path):
    """Create only if absent. POSIX mode 0600; Windows ACL needs local review."""
    path = Path(path)
    if not path.exists():
        token = secrets.token_urlsafe(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            stream.write(token + '\n'); stream.flush(); os.fsync(stream.fileno())
    if path.is_symlink() or not path.is_file(): raise ValueError('Private regular key file required')
    with path.open('rb') as stream: raw = stream.read(129)
    token = raw.decode('ascii').strip()
    if len(raw) > 128 or not re.fullmatch(TOKEN_PATTERN, token): raise ValueError('Invalid key')
    return token


def make_server(folder, receipt_path, token, *, port=PORT):
    """Audit once at startup, serve a fixed allowlisted in-memory snapshot.

    port=0 is for tests. Host remains loopback even with an alternate port.
    A browser refresh never starts a replay or implies current worker activity.
    """
    if not isinstance(token, str) or not re.fullmatch(TOKEN_PATTERN, token): raise ValueError('Strong key required')
    run_id = _uuid(Path(folder).name)
    receipt = _decode(_read_metadata(Path(receipt_path)).decode('utf-8-sig'))
    summary = build_summary(folder, receipt)
    audited_at = datetime.now(timezone.utc).isoformat()
    # Bytes are generated only by the audit/projector, never by a generic file server.
    responses = {
        '/api/health': _encode(dict(viewer_online=True, snapshot_audited_at_utc=audited_at,
            worker_liveness_verified=False, execution_allowed=False)),
        '/api/runs': _encode(dict(snapshot_audited_at_utc=audited_at, runs=[dict(run_id=run_id,
            audit_status=summary['audit_status'])], worker_liveness_verified=False)),
        '/api/runs/' + run_id + '/summary': _encode(dict(summary,
            snapshot_audited_at_utc=audited_at, snapshot_is_fixed=True)),
    }
    root = Path(__file__).resolve().parent
    assets = {
        '/': ((root/'orrery-research-status.html').read_bytes(), 'text/html; charset=utf-8'),
        '/viewer.js': ((root/'orrery-research-status.js').read_bytes(), 'text/javascript; charset=utf-8'),
        '/viewer.css': ((root/'orrery-research-status.css').read_bytes(), 'text/css; charset=utf-8'),
    }
    if any(len(v) > MAX_RESPONSE for v in responses.values()) or any(len(v[0]) > MAX_RESPONSE for v in assets.values()):
        raise ValueError('Viewer response budget')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'ORRERY'
        sys_version = ''
        def setup(self):
            super().setup(); self.connection.settimeout(5)
        def log_message(self, *args): pass
        def send(self, code, data, content_type='application/json; charset=utf-8'):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers(); self.wfile.write(data)
        def deny(self, code): self.send(code, b'{"error":"UNAVAILABLE"}')
        def do_GET(self):
            if len(self.path) > 512 or sum(len(k)+len(v) for k,v in self.headers.items()) > 16384:
                self.deny(413); return
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            hosts = self.headers.get_all('Host', [])
            if (len(hosts) != 1 or hosts[0] not in allowed or self.headers.get('Origin')
                or self.headers.get('Sec-Fetch-Site') in {'cross-site', 'same-site'}):
                self.deny(403); return
            url = urlsplit(self.path)
            if url.scheme or url.netloc or url.query or url.fragment:
                self.deny(400); return
            if url.path in assets:
                data, kind = assets[url.path]; self.send(200, data, kind); return
            # Authenticate all API paths before looking up a run or route.
            if url.path.startswith('/api/'):
                auth = self.headers.get_all('Authorization', [])
                expected = ('Bearer ' + token).encode('ascii')
                if len(auth) != 1 or not secrets.compare_digest(auth[0].encode('utf-8'), expected):
                    self.deny(403); return
                if url.path in responses: self.send(200, responses[url.path]); return
            self.deny(404)
        def do_POST(self): self.deny(405)
        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = do_POST

    return HTTPServer((HOST, port), Handler)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True); p.add_argument('--receipt', required=True)
    p.add_argument('--token-file', required=True)
    args = p.parse_args(argv)
    server = None
    try:
        key = token_file(args.token_file)
        server = make_server(args.run, args.receipt, key)
        print('ORRERY research viewer: http://127.0.0.1:8766', flush=True)
        print('Enter the private key file contents in the local page. Never share the key.', flush=True)
        print('Fixed saved snapshot; worker activity is NOT monitored. No remote access or orders.', flush=True)
        server.serve_forever()
        return 0
    except KeyboardInterrupt: return 0
    except Exception:
        print('VIEWER_UNAVAILABLE', flush=True); return 1
    finally:
        if server is not None: server.server_close()


if __name__ == '__main__': raise SystemExit(main())
