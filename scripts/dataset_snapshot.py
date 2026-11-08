"""Seed the frozen official catalogs or verify raw TSE files against them."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

SNAPSHOT = Path(__file__).resolve().parents[1] / 'reproducibility/tse-manifests'


def seed(root, source=SNAPSHOT):
    files = sorted(Path(source).glob('*.json'))
    if not files: raise ValueError('No frozen manifests found')
    dest = Path(root) / 'manifests'; dest.mkdir(parents=True, exist_ok=True)
    # Check all collisions before writing any file.
    for file in files:
        target = dest / file.name
        if target.exists() and target.read_bytes() != file.read_bytes():
            raise ValueError(f'Existing manifest differs: {target}; seed only a new dataset directory')
    for file in files:
        target = dest / file.name
        if not target.exists(): shutil.copyfile(file, target)
    return len(files)


def verify(root, source=SNAPSHOT):
    root = Path(root).resolve(); checked = 0; failures = []; total = 0
    for file in sorted(Path(source).glob('*.json')):
        record = json.loads(file.read_text())
        if not isinstance(record, dict) or record.get('status') != 'complete' or 'path' not in record: continue
        raw = (root / record['path']).resolve()
        if not raw.is_relative_to(root): raise ValueError(f'Unsafe raw-data path in {file.name}')
        checked += 1; total += record['bytes']
        if not raw.is_file(): reason = 'missing'
        elif raw.stat().st_size != record['bytes']: reason = 'size_mismatch'
        else:
            with raw.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            reason = None if actual == record['sha256'] else 'checksum_mismatch'
        if reason: failures.append({'path': record['path'], 'reason': reason})
    return {'passed': checked > 0 and not failures, 'files': checked, 'expected_bytes': total, 'failures': failures}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['seed', 'verify'])
    parser.add_argument('--root', type=Path, default=Path('/data/tse'))
    args = parser.parse_args()
    if args.action == 'seed': print(json.dumps({'seeded_manifests': seed(args.root)}))
    else:
        result = verify(args.root); print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['passed'] else 1)
