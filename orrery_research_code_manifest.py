"""Snapshot trusted local source bytes; revision is caller-declared, not attested.
Keep the printed SHA256 independently. Never repair a failed pin by rebaselining.
"""
import argparse
from pathlib import Path
import re
from orrery_research_worker import digest
from lsr04_tick_archive import _encode, _write_exclusive


def prepare(root, revision, output):
    if not re.fullmatch('[0-9a-f]{40}', revision): raise ValueError('Full declared revision required')
    paths = list(Path(root).glob('*.py'))
    if not paths or any(not p.is_file() or p.is_symlink() for p in paths): raise ValueError('Regular sources required')
    manifest = dict(declared_revision=revision, files_sha256={p.name:digest(p.read_bytes()) for p in paths})
    data = _encode(manifest); _write_exclusive(Path(output), data)
    return digest(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--declared-revision', required=True); p.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        print(prepare(Path(__file__).resolve().parent, args.declared_revision, args.output))
        return 0
    except Exception:
        print('CODE_MANIFEST_NOT_CREATED'); return 1


if __name__ == '__main__': raise SystemExit(main())
