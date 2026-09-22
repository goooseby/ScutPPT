import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from core.update import UpdateClient, UpdateError, version_key
from core.update_install import InstallError, install, read_manifest, sha256_file
from tools.build_update import files_in, package


class UpdateTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'review' / 'tmp'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bundle(self, name, version, web, extra=None):
        folder = self.root / name
        (folder / '_internal' / 'web').mkdir(parents=True)
        (folder / 'Keye.exe').write_bytes(('exe-' + version).encode())
        (folder / 'KeyeUpdater.exe').write_bytes(b'updater')
        (folder / '_internal' / 'web' / 'app.js').write_bytes(web)
        for path, content in (extra or {}).items():
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        manifest = {'schema': 1, 'version': version, 'files': files_in(folder)}
        read_manifest(json.dumps(manifest))
        (folder / 'update-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return folder, manifest

    def test_delta_updates_only_owned_files_and_keeps_user_data(self):
        old, previous = self.bundle('installed', '0.2.0', b'old',
                                    {'_internal/old.dat': b'obsolete', '_internal/stable.dat': b'stable'})
        new, current = self.bundle('new', '0.2.1', b'new', {'_internal/stable.dat': b'stable'})
        (old / 'library').mkdir()
        (old / 'library' / 'sample.pdf').write_bytes(b'personal pdf')
        (old / 'app-settings.json').write_text('{"libraryDir":"test"}', encoding='utf-8')
        archive = self.root / 'delta.zip'
        package(archive, new, current, previous['version'], previous)
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn('_internal/stable.dat', z.namelist())
            self.assertNotIn('library/sample.pdf', z.namelist())
        self.assertEqual(install(old, archive, sha256_file(archive)), '0.2.1')
        self.assertEqual((old / '_internal/web/app.js').read_bytes(), b'new')
        self.assertFalse((old / '_internal/old.dat').exists())
        self.assertEqual((old / '_internal/stable.dat').read_bytes(), b'stable')
        self.assertEqual((old / 'library/sample.pdf').read_bytes(), b'personal pdf')
        self.assertEqual(json.loads((old / 'app-settings.json').read_text())['libraryDir'], 'test')

    def test_corrupt_download_and_changed_base_are_rejected(self):
        old, previous = self.bundle('installed', '0.2.0', b'old')
        new, current = self.bundle('new', '0.2.1', b'new')
        archive = self.root / 'delta.zip'
        package(archive, new, current, previous['version'], previous)
        with self.assertRaises(InstallError):
            install(old, archive, '0' * 64)
        self.assertEqual((old / '_internal/web/app.js').read_bytes(), b'old')
        (old / 'KeyeUpdater.exe').write_bytes(b'changed locally')
        # An unchanged local file is reused by the delta and must match its manifest.
        with self.assertRaises(InstallError):
            install(old, archive, sha256_file(archive))
        self.assertEqual((old / '_internal/web/app.js').read_bytes(), b'old')

    def test_rejects_archive_outside_program_paths(self):
        old, previous = self.bundle('installed', '0.2.0', b'old')
        new, current = self.bundle('new', '0.2.1', b'new')
        archive = self.root / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('update-manifest.json', json.dumps(current))
            z.writestr('package-info.json', json.dumps({'version': '0.2.1', 'base': None}))
            z.writestr('../app-settings.json', '{}')
        with self.assertRaises(InstallError):
            install(old, archive, sha256_file(archive))
        self.assertFalse((self.root / 'app-settings.json').exists())

    def test_partial_install_rolls_back_program_files(self):
        old, previous = self.bundle('installed', '0.2.0', b'old')
        new, current = self.bundle('new', '0.2.1', b'new')
        archive = self.root / 'delta.zip'
        package(archive, new, current, previous['version'], previous)
        from core import update_install
        replace = update_install.os.replace
        count = 0
        def fail_second(source, target):
            nonlocal count
            count += 1
            if count >= 2:
                raise PermissionError('simulated locked file')
            return replace(source, target)
        with patch.object(update_install.os, 'replace', side_effect=fail_second):
            with self.assertRaises(PermissionError):
                install(old, archive, sha256_file(archive))
        self.assertEqual((old / 'Keye.exe').read_bytes(), b'exe-0.2.0')
        self.assertEqual((old / '_internal/web/app.js').read_bytes(), b'old')
        self.assertEqual(json.loads((old / 'update-manifest.json').read_text())['version'], '0.2.0')

    def test_full_package_repairs_changed_program_file(self):
        old, _ = self.bundle('installed', '0.2.0', b'old')
        new, current = self.bundle('new', '0.2.1', b'new')
        (old / 'KeyeUpdater.exe').write_bytes(b'locally changed')
        archive = self.root / 'full.zip'
        package(archive, new, current)
        self.assertEqual(install(old, archive, sha256_file(archive)), '0.2.1')
        self.assertEqual((old / 'KeyeUpdater.exe').read_bytes(), b'updater')

    def test_version_order(self):
        self.assertGreater(version_key('v0.2.0'), version_key('0.1.1'))
        with self.assertRaises(UpdateError):
            version_key('0.2.0-preview')

    def test_release_selection_and_manual_fallback(self):
        installed, _ = self.bundle('installed', '0.2.0', b'old')
        asset_root = 'https://github.com/goooseby/ScutPPT/releases/download/v0.2.1/'
        index = {'schema': 1, 'version': '0.2.1',
                 'full': {'name': 'Keye-Windows-x64.zip', 'sha256': 'a' * 64, 'size': 500},
                 'deltas': {'0.2.0': {'name': 'Keye-update-from-v0.2.0.zip',
                                      'sha256': 'b' * 64, 'size': 20}}}
        assets = [{'name': name, 'browser_download_url': asset_root + name}
                  for name in ('update-index.json', 'Keye-Windows-x64.zip', 'Keye-update-from-v0.2.0.zip')]
        release = {'tag_name': 'v0.2.1', 'body': '修复更新', 'assets': assets}
        session = Mock()
        session.get.side_effect = [Mock(json=Mock(return_value=release), raise_for_status=Mock()),
                                   Mock(json=Mock(return_value=index), raise_for_status=Mock())]
        client = UpdateClient(installed, session=session)
        result = client.check()
        self.assertTrue(result['available'])
        self.assertTrue(result['incremental'])
        self.assertEqual(result['size'], 20)
        self.assertEqual(client.available['name'], 'Keye-update-from-v0.2.0.zip')

        # An older published version lacks an update index: the UI offers a manual link.
        release['assets'] = assets[1:]
        session.get.side_effect = [Mock(json=Mock(return_value=release), raise_for_status=Mock())]
        result = client.check()
        self.assertTrue(result['manual'])
        self.assertIsNone(client.available)
        (installed / 'update-manifest.json').unlink()
        release['assets'] = assets
        session.get.side_effect = [Mock(json=Mock(return_value=release), raise_for_status=Mock()),
                                   Mock(json=Mock(return_value=index), raise_for_status=Mock())]
        result = client.check()
        self.assertTrue(result['manual'])
        self.assertIn('清单缺失', result['manualReason'])

    def test_download_verifies_hash_and_cleans_partial_file(self):
        data = b'actual update bytes'
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.iter_content.return_value = [data[:7], data[7:]]
        session = Mock()
        session.get.return_value = response
        client = UpdateClient(self.root / 'installed', session=session)
        client.available = {'version': '0.2.1', 'name': 'delta.zip',
                            'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data),
                            'url': 'https://github.com/goooseby/ScutPPT/releases/download/v0.2.1/delta.zip'}
        progress = []
        self.assertEqual(client.download(lambda done, total: progress.append((done, total))).read_bytes(), data)
        self.assertEqual(progress[-1], (len(data), len(data)))
        client.available['sha256'] = '0' * 64
        with self.assertRaises(UpdateError):
            client.download(lambda *_: None)
        self.assertFalse((self.root / 'installed/.keye-update/v0.2.1/delta.zip.part').exists())


if __name__ == '__main__':
    unittest.main()
