"""Guided Windows entry point to the existing read-only account pilot.
No terminal connection in this launcher; the child runner owns DEMO checks.
"""
import subprocess
import sys
from pathlib import Path
from START_REAL_MT5_PILOT import ask
from lsr03_mt5_account_pilot import _settings, verify_pilot_bundle
from lsr04_tick_archive import _decode, _read_metadata


def main(root=None):
    if sys.platform != 'win32':
        raise RuntimeError('Run this launcher on Windows with the logged-in DEMO terminal')
    root = Path(root or Path(__file__).resolve().parent).resolve()
    runner = root / 'lsr03_mt5_account_pilot.py'
    if not runner.is_file():
        raise ValueError('Account pilot runner missing from this checkout')
    print('ORRERY: two independent $3000 research accounts; NO orders.')
    print('XAUUSD / same USD DEMO only. Current-spec estimate, not historical proof.')
    print('No passwords or login IDs. Costs must be documented USD PER LOT.')
    pilot = Path(ask('Existing capture directory')).expanduser().resolve()
    pin = ask('Independently retained capture run_sha256 (do not recompute from this folder)')
    manifest, files = verify_pilot_bundle(pilot, pin)
    spec = manifest.get('broker_valuation_spec')
    if (files['settings.json'].get('symbol') != 'XAUUSD' or not isinstance(spec, dict)
            or spec.get('currency_profit') != 'USD'):
        raise ValueError('New USD-profit XAUUSD capture required; no guessed conversion')
    print('Use account_pilot_settings.example.json to prepare a separate local settings file.')
    config = Path(ask('Completed account settings JSON path')).expanduser().resolve()
    _settings(_decode(_read_metadata(config)))
    terminal = Path(ask('MT5 terminal64.exe absolute path',
                        r'C:\Program Files\MetaTrader 5\terminal64.exe')).expanduser()
    if not terminal.is_absolute() or not terminal.is_file():
        raise ValueError('Existing absolute terminal path required')
    folder = ask('New output directory name', 'orrery_account_real_001')
    if not folder or Path(folder).name != folder:
        raise ValueError('Use a single new directory name')
    output = (root / folder).resolve()
    if output == root or root not in output.parents or output.exists():
        raise ValueError('Output must be a new directory inside this checkout')
    command = [sys.executable, str(runner), '--pilot', str(pilot),
               '--pilot-run-sha256', pin, '--config', str(config),
               '--output', str(output), '--terminal-path', str(terminal)]
    result = subprocess.call(command, cwd=root)
    if result == 0:
        print(f'Report: {output / "account_report.json"}')
        print('Inspect OPEN/skipped trades and costs. Zero trades is not profit evidence.')
    elif result == 2:
        print(f'BLOCKED by tick quality. Inspect {output / "account_report.json"}')
    else:
        print('STOPPED: no completed account estimate confirmed. Inspect runner status.')
    return result


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, EOFError):
        print('STOPPED: check Windows, pinned capture, explicit settings and new output path.', file=sys.stderr)
        raise SystemExit(1)
