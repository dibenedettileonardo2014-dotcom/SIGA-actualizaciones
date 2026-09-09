import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
import desktop_launcher as app


class UpdateSafetyTests(unittest.TestCase):
    def test_only_official_repository(self):
        for url in ['https://github.com/other/repo/a.zip', 'https://raw.githubusercontent.com/other/repo/main/a.zip', 'https://siga-85bdd.web.app.evil/a.zip', 'https://user:password@siga-85bdd.web.app/a.zip', 'http://siga-85bdd.web.app/a.zip']:
            self.assertFalse(app.trusted_update_url(url), url)
        for url in app.UPDATE_MANIFEST_URLS:
            self.assertTrue(app.trusted_update_url(url))

    def test_downgrade_is_not_offered(self):
        self.assertFalse(app.update_required({'version':'1.0.0','sha256':'A'*64}))

    def test_package_cannot_replace_user_data(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'bad.zip'
            with zipfile.ZipFile('SIGA-update-x64.zip') as current, zipfile.ZipFile(target,'w') as out:
                out.writestr('SIGA.exe',current.read('SIGA.exe'))
                out.writestr('_internal/index.html',b'page')
                out.writestr('WebViewProfile/credentials',b'bad')
            with self.assertRaises(ValueError): app.validate_update_package(target,'x64')

    def test_modified_staged_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(app,'update_state_path',return_value=Path(folder)):
            source=Path(folder)/'update.zip';source.write_bytes(b'changed')
            (Path(folder)/'prepared-update.json').write_text(json.dumps({'path':str(source),'architecture':app.APP_ARCH,'kind':'package','sha256':'A'*64}))
            self.assertFalse(app.prepared_update_status()['ready'])
            with mock.patch.object(app.subprocess,'Popen') as launch:
                self.assertFalse(app.apply_prepared_update());launch.assert_not_called()

    def test_legacy_restart_race_does_not_reapply_installed_release(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(app,'update_state_path',return_value=Path(folder)):
            pending=Path(folder)/'prepared-update.json';pending.write_text(json.dumps({'version':app.APP_VERSION,'revision':app.APP_REVISION}))
            self.assertFalse(app.automatic_update_on_startup());self.assertFalse(pending.exists())

    def test_failed_release_is_not_retried_forever(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(app,'update_state_path',return_value=Path(folder)), mock.patch.object(app.sys,'frozen',True,create=True), mock.patch.object(app,'fetch_update_manifest',return_value={'version':'9.0.0','revision':'r1'}):
            (Path(folder)/'transaction.json').write_text(json.dumps({'status':'rolled-back','version':'9.0.0','revision':'r1'}))
            with mock.patch.object(app,'install_update') as download:
                self.assertFalse(app.DesktopApi().prepare_available_update()['ok']);download.assert_not_called()

    def test_unofficial_redirect_does_not_stage(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(app,'update_state_path',return_value=Path(folder)), mock.patch.object(app.time,'sleep'):
            response=io.BytesIO(b'payload');response.geturl=lambda:'https://example.com/unsafe'
            manifest={'architecture':app.APP_ARCH,'version':'9.0.0','url':app.UPDATE_MANIFEST_URLS[0],'sha256':hashlib.sha256(b'payload').hexdigest()}
            with mock.patch.object(app,'urlopen',side_effect=lambda *a,**k: mock.MagicMock(__enter__=lambda _:response,__exit__=lambda *a:False)):
                self.assertFalse(app.install_update(manifest))
            self.assertFalse((Path(folder)/'prepared-update.json').exists())

if __name__=='__main__':unittest.main()
