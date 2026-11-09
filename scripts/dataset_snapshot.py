"""Seed the frozen official catalogs or verify raw TSE files against them."""
import argparse
import hashlib
import json
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / 'reproducibility/tse-snapshot.json'


def manifest_texts(source):
    source = Path(source)
    if source.is_file():
        bundle = json.loads(source.read_text())
        if bundle.get('format_version') != 1 or not isinstance(bundle.get('manifests'), dict):
            raise ValueError('Invalid consolidated snapshot')
        result = {}
        for name, record in bundle['manifests'].items():
            if not isinstance(name, str) or '/' in name or '\\' in name or not name.endswith('.json') or not isinstance(record, dict):
                raise ValueError('Invalid manifest filename or record')
            result[name] = json.dumps(record, ensure_ascii=False, indent=2) + '\n'
    else:
        result = {file.name: file.read_text() for file in sorted(source.glob('*.json'))}
    if not result: raise ValueError('No frozen manifests found')
    return result


def seed(root, source=SNAPSHOT):
    files = manifest_texts(source)
    dest = Path(root) / 'manifests'; dest.mkdir(parents=True, exist_ok=True)
    # Check all collisions before writing any file.
    for name, text in files.items():
        target = dest / name
        if target.exists() and target.read_text() != text:
            raise ValueError(f'Existing manifest differs: {target}; seed only a new dataset directory')
    for name, text in files.items():
        target = dest / name
        if not target.exists(): target.write_text(text)
    return len(files)


def verify(root, source=SNAPSHOT):
    root = Path(root).resolve(); checked = 0; failures = []; total = 0
    for name, text in manifest_texts(source).items():
        record = json.loads(text)
        if not isinstance(record, dict) or record.get('status') != 'complete' or 'path' not in record: continue
        raw = (root / record['path']).resolve()
        if not raw.is_relative_to(root): raise ValueError(f'Unsafe raw-data path in {name}')
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
