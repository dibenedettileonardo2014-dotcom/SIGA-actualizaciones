import json
import hashlib
import re
import subprocess
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import desktop_launcher


ROOT = Path(__file__).resolve().parents[1]


class IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, _tag, attrs):
        self.ids.extend(value for key, value in attrs if key == "id")


class LauncherTests(unittest.TestCase):
    def test_version_validation(self):
        self.assertEqual(desktop_launcher.version_key("1.2.49"), (1, 2, 49))
        for invalid in ("", "1", "1.2.beta", "1.2.3.4.5"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                desktop_launcher.version_key(invalid)

    def test_update_manifest_requires_https_and_sha256(self):
        valid = {
            "version": "1.2.49",
            "url": "https://example.test/SIGA.exe",
            "sha256": "A" * 64,
            "packageUrl": "https://example.test/SIGA.zip",
            "packageSha256": "b" * 64,
        }
        self.assertTrue(desktop_launcher.valid_update_manifest(valid))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "url": "http://example.test/SIGA.exe"}))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "sha256": "bad"}))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "urls": ["http://example.test/SIGA.exe"]}))


class ApplicationSourceTests(unittest.TestCase):
    def test_mobile_shell_assets_exist(self):
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        shell_match = re.search(r"const APP_SHELL = \[([\s\S]*?)\];", service_worker)
        self.assertIsNotNone(shell_match)
        paths = re.findall(r"'\./([^']*)'", shell_match.group(1))
        for relative in paths:
            target = ROOT / "hosting" / (relative or "index.html")
            self.assertTrue(target.exists(), str(target))

    def test_module_javascript_parses(self):
        for filename in ("index.html", "afiliado.html"):
            html = (ROOT / filename).read_text(encoding="utf-8")
            match = re.search(r'<script type="module">([\s\S]*?)</script>', html)
            self.assertIsNotNone(match, filename)
            javascript = re.sub(r"^\s*import .*;\s*$", "", match.group(1), flags=re.MULTILINE)
            result = subprocess.run(
                ["node", "--check"], input=javascript, text=True,
                encoding="utf-8", capture_output=True, check=False, timeout=15,
            )
            self.assertEqual(result.returncode, 0, f"{filename}: {result.stderr}")

    def test_html_ids_are_unique(self):
        for filename in ("index.html", "afiliado.html"):
            parser = IdCollector()
            parser.feed((ROOT / filename).read_text(encoding="utf-8"))
            duplicates = [key for key, count in Counter(parser.ids).items() if count > 1]
            self.assertEqual(duplicates, [], filename)

    def test_required_security_and_integrity_guards_exist(self):
        desktop_html = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile_html = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        for marker in (
            "findDuplicateAffiliate",
            "normalizedDni",
            "local-attachment-link",
            "button.dataset.busy",
            "runTransaction",
            "uniqueAffiliateKey",
            "unique_affiliates",
            "revision-conflict",
            "clientMutationId",
            "mobileAccess: existing?.mobileAccess",
        ):
            self.assertIn(marker, desktop_html)
        self.assertIn("handleCredentialWatchError", mobile_html)
        self.assertIn("validAffiliate", rules)
        self.assertIn("validPayment", rules)
        self.assertIn("request.resource.data.revision == resource.data.revision + 1", rules)

    def test_lgdb_signature_is_consistent(self):
        for filename in ("index.html", "afiliado.html"):
            html = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn('class="lgdb-signature', html)
            self.assertIn(">LGDB</span>", html)
        desktop_html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Desarrollado por <span", desktop_html)
        self.assertIn("Creado en 2026", desktop_html)

    def test_notice_formatting_and_locality_contract(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in ("form-locality", "locality: affiliate.locality", "toLocaleUpperCase('es-AR')", "uppercaseNoticeInput", "notice-title').addEventListener('input'", "optimizeNoticeImage", "object-contain"):
            self.assertIn(marker, desktop)
        self.assertIn("['Localidad',data.locality]", mobile)
        self.assertIn("object-fit:contain", mobile)
        self.assertNotIn("object-fit:cover", mobile)

    def test_manifest_is_well_formed_and_hashes_are_sha256(self):
        manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(manifest["sha256"], r"^[A-F0-9]{64}$")
        self.assertRegex(manifest["packageSha256"], r"^[A-F0-9]{64}$")
        self.assertRegex(manifest["installerSha256"], r"^[A-F0-9]{64}$")
        artifacts = {
            "sha256": ROOT / "SIGA.exe",
            "packageSha256": ROOT / "SIGA-update.zip",
            "installerSha256": ROOT / "installer" / f"SIGA-Setup-{manifest['version']}.exe",
        }
        for key, path in artifacts.items():
            with self.subTest(artifact=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                self.assertEqual(manifest[key], digest)


if __name__ == "__main__":
    unittest.main()
