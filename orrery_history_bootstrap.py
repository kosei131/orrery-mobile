"""Pinned source bootstrap for a small DEMO history check; no installation or orders."""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from uuid import uuid4

REVISION = '44fe7cb35fe682a8f048d0a6bb375f1dda3bca96'
PINS = {'lsr02_mt5_bridge.py': 'd7a798e286d36418f702bd78f434dc62c5f930bbdb524270da047cd0403aaf16', 'lsr02_regime.py': '8b4a504caeea2fd7f7654b2cbe673b9c4a4c5ebd35fbb69d873a89d1c6c8bab9', 'lsr02_replay.py': 'bd7d3e43428126794923bebe1e4e51a012b49340abf8788c4f2ead826f817383', 'lsr02_sequence.py': '043f037cffdf1b30cb89be3a95176672900447fbccce4891c4f0d1d722a2f1da', 'lsr02_structure.py': '873fe9d8951d80dc2e79082f5bee9c3ba162a3b0c77ba7c212a4cc94d0c04a1b', 'lsr03_adapter.py': '6470b4122d1731446d9836929a7c8dfd95abf94ef2ff454a482f2ee4f7bc70ff', 'lsr03_mt5_pilot.py': '5114058e0fb3aeb480f6101bc792f642b4ef54fc8eb618042be76149ec6599a8', 'lsr03_tick_study.py': '9a6ae6ee7124d466016063767c9eeadce459d42a51503233453b243f00b8c9b6', 'lsr03_vhf.py': '20d7b8486434af192078cdeba8349900a407c9e9197183a0c4c8b1698c90b0ba', 'lsr04_account_gate.py': 'b5e15e6f3346353d977c3aec8602b5d418da588fc9c120ae3808d0e10e0a5c13', 'lsr04_daily_reconciliation.py': '8e08f8aa9f956fc784fbe88cc674094c673b0cbc6ed1da65c18a30848f6264bd', 'lsr04_deal_groups.py': 'bd58424a99a70ef5cbf49ab60746630db819cc969f9aef24adf578855598dfc4', 'lsr04_mt5_account_sync.py': '9ab7934a5d62321fd6657c8b516ce22d2b5971b5abdcd755f2601f1c0021780c', 'lsr04_mt5_adaptive.py': '536ecc420a5c84467f944940b1d0ff115297e4a9d0ef268f3a7ce833dcaa07b9', 'lsr04_mt5_position_risk.py': '9db0c4915853195cd3584a15f517d963107dd21199577230a75c930566bf51c5', 'lsr04_mt5_ticks.py': '2dc13298cf4f95c65a066de18ed144922959976952b3274c2d3c629ea295d477', 'lsr04_tick_archive.py': 'e77594d24005c71da743364a7e638ab7d52617afcefd5b93c54e576e53d61da7', 'lsr04_tick_catalog.py': 'd2385d494f7e4d3d50a1b07c519cd0795fbb4158f0b290296777fe0a87d8da87', 'lsr04_tick_fills.py': 'ff30b59e09e52d521103d6debd31d75419544489759308955ddb261a4281b3fc', 'lsr04_tick_quality.py': '354fa24c975c96ecc00a2f0ffe2f6f38b0df86975ff147044593bb8145b279f3', 'orrery_mt5_history_check.py': 'ba45ddf6062c34aca5219668d81ae9f38f49a747e1bfe1ef706afc67f36f10aa'}
MAX_BYTES = 2*1024*1024


def fetch(name):
    url = 'https://raw.githubusercontent.com/kosei131/orrery-mobile/' + REVISION + '/' + name
    with urllib.request.urlopen(url, timeout=30) as response:
        if response.geturl() != url:
            raise ValueError('Unexpected download redirect')
        return response.read(MAX_BYTES+1)


def prepare(parent, *, download=fetch):
    # Fresh exclusive folder, no reuse of user ZIP, source tree or old variables.
    root = Path(parent)/str(uuid4())
    root.mkdir(parents=True, exist_ok=False)
    for name, pin in PINS.items():
        data = download(name)
        if not isinstance(data, bytes) or len(data)>MAX_BYTES or sha256(data).hexdigest()!=pin:
            raise ValueError('Pinned source mismatch')
        with (root/name).open('xb') as stream:
            stream.write(data)
        compile(data, name, 'exec')  # syntax only, no imports or terminal connection
    # Written only after every expected file has been checked.
    with (root/'SOURCE_REVISION.txt').open('x', encoding='ascii') as stream:
        stream.write(REVISION+'\n')
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    try:
        if sys.platform!='win32' or sys.version_info[:2]!=(3,12):
            raise ValueError('Windows Python 3.12 required')
        parent = Path(os.environ['LOCALAPPDATA'])/'ORRERYFX'/'history-check-source'
        root = prepare(parent)
        print('PINNED_SOURCE_VERIFIED:', REVISION, flush=True)
        if args.verify_only:
            print('VERIFY_ONLY: No MT5 connection requested.')
            return 0
        # Fixed runner and arguments; never invokes pip, login or an order call.
        result = subprocess.run([sys.executable, str(root/'orrery_mt5_history_check.py')],
                                cwd=root, timeout=120, check=False)
        return result.returncode
    except subprocess.TimeoutExpired:
        print('BLOCKED: History check timed out. No successful result is assumed.')
        return 1
    except Exception:
        print('BLOCKED: Download, source verification or startup failed.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
