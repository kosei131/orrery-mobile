"""Optional loopback entry point behind explicitly configured Tailscale Serve.
Trusts Serve identity only on the local PC. Not a TLS server or installer.
Existing snapshot viewer/token gates and strategy files remain unchanged.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import secrets
from orrery_research_status import make_server, token_file
from lsr04_tick_archive import _decode, _read_metadata, _pin

PORT = 8767


def settings(value):
    if not isinstance(value, dict) or set(value) != {'enabled','public_host','allowed_login_sha256'}:
        raise ValueError('Exact private settings required')
    if value['enabled'] is not True: raise ValueError('Tailnet viewer disabled')
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if not isinstance(value['public_host'], str) or not re.fullmatch(label+r'\.'+label+r'\.ts\.net', value['public_host']):
        raise ValueError('Exact tailnet HTTPS hostname required')
    _pin(value['allowed_login_sha256'])
    return dict(value)


def make_tailnet_server(folder, receipt_path, token, config, *, port=PORT):
    config = settings(config)
    # Reuse the existing audit and protected API, without opening a second
    # generic proxy or exposing the old MT5 account dashboard.
    server = make_server(folder, receipt_path, token, port=port)
    original = server.RequestHandlerClass

    class Handler(original):
        def do_GET(self):
            if len(self.path) > 512 or sum(len(k)+len(v) for k,v in self.headers.items()) > 16384:
                self.deny(413); return
            hosts = self.headers.get_all('Host', [])
            logins = self.headers.get_all('Tailscale-User-Login', [])
            origins = self.headers.get_all('Origin', [])
            host = config['public_host']
            if (len(hosts) != 1 or hosts[0] not in {host, host+':443'}
                or len(logins) != 1 or len(logins[0]) > 254 or not logins[0].isascii()
                or not logins[0] or any(ord(c) <= 32 or ord(c) == 127 for c in logins[0])
                or not secrets.compare_digest(sha256(logins[0].encode('ascii')).hexdigest(), config['allowed_login_sha256'])
                or len(origins) > 1 or (origins and origins[0] not in {'https://'+host, 'https://'+host+':443'})
                or self.headers.get('Sec-Fetch-Site') in {'cross-site','same-site'}):
                self.deny(403); return
            # Only after checking the external Host, same-origin HTTPS context
            # and configured owner identity, adapt to the old loopback gate.
            del self.headers['Host']; self.headers['Host'] = f'127.0.0.1:{self.server.server_port}'
            if origins: del self.headers['Origin']
            del self.headers['Tailscale-User-Login']
            super().do_GET()

    server.RequestHandlerClass = Handler
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True); parser.add_argument('--receipt', required=True)
    parser.add_argument('--token-file', required=True); parser.add_argument('--config', required=True)
    args = parser.parse_args(argv); server = None
    try:
        config = settings(_decode(_read_metadata(Path(args.config)).decode('utf-8-sig')))
        server = make_tailnet_server(args.run, args.receipt, token_file(args.token_file), config)
        print('ORRERY optional Serve entry listening on loopback port 8767.', flush=True)
        print('Requires private Serve HTTPS, verified device policy and viewer key. Not live worker monitoring.', flush=True)
        server.serve_forever(); return 0
    except KeyboardInterrupt: return 0
    except Exception:
        print('TAILNET_VIEWER_UNAVAILABLE', flush=True); return 1
    finally:
        if server is not None: server.server_close()


if __name__ == '__main__': raise SystemExit(main())
