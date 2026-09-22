"""Offline installer. This runs from a copied helper after Keye.exe exits."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath


class InstallError(Exception):
    pass


def owned_path(name):
    if not isinstance(name, str) or '\\' in name or ':' in name:
        raise InstallError('更新包包含无效路径。')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or name != path.as_posix():
        raise InstallError('更新包包含越界路径。')
    if name not in ('Keye.exe', 'KeyeUpdater.exe', '使用说明.md') and (
            len(path.parts) < 2 or path.parts[0] != '_internal'):
        raise InstallError('更新包包含非程序文件。')
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(raw):
    manifest = json.loads(raw)
    if manifest.get('schema') != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', str(manifest.get('version', ''))):
        raise InstallError('程序清单版本无效。')
    files = manifest.get('files')
    if not isinstance(files, dict) or 'Keye.exe' not in files or 'KeyeUpdater.exe' not in files:
        raise InstallError('程序清单不完整。')
    for name, info in files.items():
        owned_path(name)
        if not isinstance(info, dict) or not re.fullmatch(r'[a-f0-9]{64}', str(info.get('sha256', ''))):
            raise InstallError('程序文件校验信息无效。')
        if not isinstance(info.get('size'), int) or info['size'] < 0:
            raise InstallError('程序文件大小无效。')
    return manifest


def wait_for_exit(pid, seconds=120):
    if sys.platform != 'win32':
        return
    import ctypes
    handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
    if not handle:
        return
    try:
        if ctypes.windll.kernel32.WaitForSingleObject(handle, seconds * 1000) != 0:
            raise InstallError('等待课页退出超时，请关闭程序后重试。')
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def replace_with_retry(source, target, attempts=15):
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2)


def install(install_dir, package_path, expected_sha256):
    install_dir = Path(install_dir).resolve()
    package_path = Path(package_path).resolve()
    if not (install_dir / 'Keye.exe').is_file():
        raise InstallError('未找到待更新的课页程序。')
    if sha256_file(package_path) != expected_sha256:
        raise InstallError('更新包校验失败。')
    stage = package_path.parent
    unpacked = stage / 'unpacked'
    backup = stage / 'backup'
    if unpacked.exists() or backup.exists():
        raise InstallError('检测到未完成的更新，请先清理更新缓存或重新下载。')
    old_path = install_dir / 'update-manifest.json'
    if not old_path.is_file():
        raise InstallError('当前安装未包含更新清单，请手动下载完整版本。')
    old = read_manifest(old_path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(package_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or 'update-manifest.json' not in names or 'package-info.json' not in names:
            raise InstallError('更新包内容不完整或存在重复文件。')
        info = json.loads(archive.read('package-info.json'))
        new_raw = archive.read('update-manifest.json')
        new = read_manifest(new_raw)
        if info.get('version') != new['version'] or info.get('base') not in (None, old['version']):
            raise InstallError('更新包与当前版本不匹配。')
        if tuple(map(int, new['version'].split('.'))) <= tuple(map(int, old['version'].split('.'))):
            raise InstallError('目标版本没有比当前版本更新。')
        old_files, new_files = old['files'], new['files']
        changed = {name for name in new_files if name not in old_files or old_files[name] != new_files[name]}
        if info['base'] is None:
            changed = set(new_files)
        expected = changed | {'update-manifest.json', 'package-info.json'}
        if set(names) != expected:
            raise InstallError('更新包文件与清单不一致。')
        for item in archive.infolist():
            if item.is_dir() or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise InstallError('更新包不能包含目录或链接。')
            if item.filename not in ('update-manifest.json', 'package-info.json'):
                owned_path(item.filename)
                if item.file_size != new_files[item.filename]['size']:
                    raise InstallError('更新包文件大小与清单不一致。')
        # A delta is safe only if all files reused from the old installation still match.
        for name in set(new_files) - changed:
            target = install_dir.joinpath(*PurePosixPath(name).parts)
            if not target.is_file() or sha256_file(target) != new_files[name]['sha256']:
                raise InstallError('现有程序文件已变化，请改用完整安装包。')
        unpacked.mkdir()
        for name in changed:
            target = unpacked.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('wb') as destination:
                shutil.copyfileobj(source, destination)
            if sha256_file(target) != new_files[name]['sha256']:
                raise InstallError('更新包内的程序文件校验失败。')
        (unpacked / 'update-manifest.json').write_bytes(new_raw)
    # Only previously owned program files can be removed. User data is outside this set.
    removed = set(old_files) - set(new_files)
    affected = changed | removed | {'update-manifest.json'}
    backup.mkdir()
    for name in affected:
        source = install_dir.joinpath(*PurePosixPath(name).parts)
        if source.is_file():
            destination = backup.joinpath(*PurePosixPath(name).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    touched = []
    try:
        for name in sorted(affected):
            target = install_dir.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = unpacked.joinpath(*PurePosixPath(name).parts)
            if source.is_file():
                replace_with_retry(source, target)
            elif target.exists():
                target.unlink()
            touched.append(name)
        for name in new_files:
            target = install_dir.joinpath(*PurePosixPath(name).parts)
            if not target.is_file() or target.stat().st_size != new_files[name]['size']:
                raise InstallError('更新后的程序文件不完整。')
    except Exception:
        for name in reversed(touched):
            target = install_dir.joinpath(*PurePosixPath(name).parts)
            previous = backup.joinpath(*PurePosixPath(name).parts)
            if previous.is_file():
                shutil.copy2(previous, target)
            elif target.exists():
                target.unlink()
        raise
    return new['version']


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--pid', required=True, type=int)
    args = parser.parse_args()
    try:
        wait_for_exit(args.pid)
        version = install(args.install, args.package, args.sha256)
        subprocess.Popen([str(Path(args.install) / 'Keye.exe')], cwd=args.install)
        (Path(args.package).parent / 'update-success.json').write_text(
            json.dumps({'version': version}), encoding='utf-8')
        return 0
    except Exception as exc:
        log = Path(args.package).parent / 'update-error.txt'
        log.write_text(f'{type(exc).__name__}: {exc}', encoding='utf-8')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f'课页更新或重启失败：{exc}\n详情见更新缓存中的 update-error.txt。', '课页更新', 0x10)
        return 1


if __name__ == '__main__':
    sys.exit(main())
