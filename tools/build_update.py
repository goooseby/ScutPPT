"""Create full and optional file-level delta assets for a GitHub Release."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.update_install import owned_path, read_manifest, sha256_file
from core.version import VERSION


def files_in(bundle):
    result = {}
    for path in sorted(bundle.rglob('*')):
        if not path.is_file():
            continue
        name = path.relative_to(bundle).as_posix()
        if name == 'update-manifest.json':
            continue
        owned_path(name)
        result[name] = {'sha256': sha256_file(path), 'size': path.stat().st_size}
    return result


def package(path, bundle, manifest, base=None, previous=None):
    current = manifest['files']
    changed = current if base is None else {
        name: info for name, info in current.items()
        if name not in previous['files'] or previous['files'][name] != info
    }
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in changed:
            archive.write(bundle / name, name)
        archive.write(bundle / 'update-manifest.json', 'update-manifest.json')
        archive.writestr('package-info.json', json.dumps({'version': manifest['version'], 'base': base}))
    return {'name': path.name, 'sha256': sha256_file(path), 'size': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--previous', type=Path, help='Previous unpacked release directory')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 1, 'version': VERSION, 'files': files_in(bundle)}
    read_manifest(json.dumps(manifest, ensure_ascii=False))
    (bundle / 'update-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    full = package(output / 'Keye-Windows-x64.zip', bundle, manifest)
    deltas = {}
    if args.previous:
        old = read_manifest((args.previous / 'update-manifest.json').read_text(encoding='utf-8'))
        if old['version'] == VERSION:
            raise ValueError('Previous version cannot equal the new version.')
        deltas[old['version']] = package(
            output / f'Keye-update-from-v{old["version"]}.zip',
            bundle, manifest, old['version'], old)
    index = {'schema': 1, 'version': VERSION, 'full': full, 'deltas': deltas}
    (output / 'update-index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'更新资源已生成：{full["size"] / 1024**2:.1f} MiB 完整包，{len(deltas)} 个增量包')


if __name__ == '__main__':
    main()
