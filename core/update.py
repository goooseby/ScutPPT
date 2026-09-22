"""GitHub Release discovery and verified downloads for the desktop updater."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from core.version import REPOSITORY, VERSION
from core.update_install import InstallError, read_manifest, sha256_file


class UpdateError(Exception):
    pass


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    if not match:
        raise UpdateError('更新版本号无效。')
    return tuple(map(int, match.groups()))


def release_asset_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'github.com':
        raise UpdateError('更新文件地址不属于 GitHub Releases。')
    if not parsed.path.startswith(f'/{REPOSITORY}/releases/download/'):
        raise UpdateError('更新文件不属于课页的 GitHub 仓库。')
    return url


class UpdateClient:
    def __init__(self, install_dir, version=VERSION, session=None):
        self.install_dir = Path(install_dir).resolve()
        self.version = version
        self.session = session or requests.Session()
        self.available = None

    def check(self):
        endpoint = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
        self.available = None
        try:
            response = self.session.get(endpoint, headers={'Accept': 'application/vnd.github+json'},
                                        timeout=(8, 20))
            response.raise_for_status()
            release = response.json()
            latest = release['tag_name'].removeprefix('v')
            newer = version_key(latest) > version_key(self.version)
            result = {'current': self.version, 'latest': latest, 'available': newer,
                      'notes': str(release.get('body') or '')[:6000],
                      'releaseUrl': f'https://github.com/{REPOSITORY}/releases/tag/{release["tag_name"]}'}
            if not newer:
                self.available = None
                return result
            assets = {asset['name']: asset for asset in release.get('assets', [])}
            index_asset = assets.get('update-index.json')
            if not index_asset:
                result['manual'] = True
                result['manualReason'] = '此版本没有提供应用内更新包，请手动下载完整包。'
                return result
            index_url = release_asset_url(index_asset['browser_download_url'])
            index_response = self.session.get(index_url, timeout=(8, 20))
            index_response.raise_for_status()
            index = index_response.json()
            if index.get('schema') != 1 or index.get('version') != latest:
                raise UpdateError('发布的更新索引与版本不匹配。')
            local_manifest = self.install_dir / 'update-manifest.json'
            if local_manifest.is_file():
                try:
                    installed = read_manifest(local_manifest.read_text(encoding='utf-8'))
                    base = installed['version'] if installed['version'] == self.version else None
                except (ValueError, KeyError, OSError, InstallError):
                    base = None
            else:
                base = None
            if not base:
                result['manual'] = True
                result['manualReason'] = '本地程序的更新清单缺失或版本不匹配，请手动覆盖安装完整包。'
                return result
            package = index.get('deltas', {}).get(base) if base else None
            if package and not self.local_bundle_intact(installed):
                package = None
            package = package or index.get('full')
            if not isinstance(package, dict):
                raise UpdateError('发布缺少适用的更新包。')
            name = package.get('name')
            sha256 = package.get('sha256')
            size = package.get('size')
            if not isinstance(name, str) or name not in assets or not re.fullmatch(r'[a-f0-9]{64}', str(sha256)):
                raise UpdateError('更新包校验信息不完整。')
            if not isinstance(size, int) or not 0 < size < 2 * 1024**3:
                raise UpdateError('更新包大小无效。')
            url = release_asset_url(assets[name]['browser_download_url'])
            result.update({'manual': False, 'size': size, 'incremental': package is not index.get('full')})
            self.available = {'version': latest, 'name': name, 'sha256': sha256, 'size': size,
                              'url': url, 'incremental': result['incremental']}
            return result
        except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
            raise UpdateError(f'检查更新失败：{exc}') from exc

    def download(self, progress, cancelled=lambda: False):
        package = self.available
        if not package:
            raise UpdateError('请先检查更新。')
        stage = self.install_dir / '.keye-update' / ('v' + package['version'])
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / package['name']
        temporary = target.with_suffix(target.suffix + '.part')
        digest = hashlib.sha256()
        count = 0
        try:
            with self.session.get(package['url'], stream=True, timeout=(10, 45)) as response:
                response.raise_for_status()
                with temporary.open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024):
                        if cancelled():
                            raise UpdateError('下载已取消。')
                        if not chunk:
                            continue
                        count += len(chunk)
                        if count > package['size']:
                            raise UpdateError('下载大小超出发布记录。')
                        digest.update(chunk)
                        output.write(chunk)
                        progress(count, package['size'])
            if count != package['size'] or digest.hexdigest() != package['sha256']:
                raise UpdateError('更新包校验失败，请重新下载。')
            temporary.replace(target)
            return target
        except (requests.RequestException, OSError) as exc:
            raise UpdateError(f'下载更新失败：{exc}') from exc
        finally:
            temporary.unlink(missing_ok=True)

    def local_bundle_intact(self, manifest):
        try:
            for name, info in manifest['files'].items():
                target = self.install_dir.joinpath(*name.split('/'))
                if not target.is_file() or target.stat().st_size != info['size']:
                    return False
                if sha256_file(target) != info['sha256']:
                    return False
            return True
        except OSError:
            return False
