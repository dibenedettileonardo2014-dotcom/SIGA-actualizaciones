import json
import hashlib
import re
import subprocess
import unittest
import zipfile
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
        self.assertTrue(desktop_launcher.valid_update_manifest(valid, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest(valid, "x86"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "url": "http://example.test/SIGA.exe"}, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "sha256": "bad"}, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "urls": ["http://example.test/SIGA.exe"]}, "x64"))
        installer = {**valid, "installerUrl": "https://example.test/SIGA-Setup.exe", "installerSha256": "C" * 64}
        self.assertTrue(desktop_launcher.valid_update_manifest(installer, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**installer, "installerSha256": "bad"}, "x64"))

    def test_update_manifest_selects_only_matching_architecture(self):
        artifact = {
            "architecture": "x86", "url": "https://example.test/SIGA-x86.exe",
            "sha256": "A" * 64, "packageUrl": "https://example.test/SIGA-x86.zip",
            "packageSha256": "B" * 64,
        }
        manifest = {"version": "1.4.0", "architectures": {"x86": artifact}}
        self.assertTrue(desktop_launcher.valid_update_manifest(manifest, "x86"))
        self.assertFalse(desktop_launcher.valid_update_manifest(manifest, "x64"))
        self.assertEqual(desktop_launcher.update_metadata(manifest, "x86")["architecture"], "x86")

    def test_native_export_types_are_explicitly_limited(self):
        source = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn('{".xlsx", ".pdf", ".csv", ".json"}', source)
        self.assertIn("64 * 1024 * 1024", source)

    def test_cross_architecture_update_is_rejected_before_download(self):
        other_architecture = "x86" if desktop_launcher.APP_ARCH == "x64" else "x64"
        self.assertFalse(desktop_launcher.install_update({"architecture": other_architecture}))

    def test_updater_waits_for_exit_and_uses_verified_installer(self):
        source = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn('installerSha256', source)
        self.assertIn('start "" /wait "%INSTALLER%"', source)
        self.assertIn('/CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS', source)
        self.assertIn('if errorlevel 1 exit /b 1', source)
        self.assertNotIn('timeout /t 2 /nobreak', source)


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

    def test_admin_and_operator_can_manage_existing_notices(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        self.assertNotIn('body[data-role="operador"] #btn-tab-comunicados', desktop)
        self.assertIn("['admin','operador'].includes(window.appState.currentUserRole)", desktop)
        for action in ("notice-edit", "notice-toggle", "notice-delete"):
            self.assertNotIn(f'body[data-role="operador"] #notice-table .{action}', desktop)
        notice_rules = rules[rules.index("match /artifacts/{appId}/public/data/comunicados/{noticeId}"):]
        self.assertIn("allow create: if isStaffOperational(appId)", notice_rules)
        self.assertGreaterEqual(notice_rules.count("allow update, delete: if isStaffOperational(appId);"), 2)
        for marker in ("notice-edit-id", "setDoc(doc(noticeCollection(),id),data)", "deleteNoticeAtomically(item.id)", "if(!confirm(`¿Eliminar definitivamente", "onSnapshot(noticeCollection()"):
            self.assertIn(marker, desktop)

    def test_affiliate_form_layout_contract(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="grid grid-cols-1 sm:grid-cols-3 gap-4"', desktop)
        self.assertIn('>Trabaja por consultora</span>', desktop)
        self.assertIn('class="grid grid-cols-1 sm:grid-cols-6 gap-3"', desktop)
        self.assertIn('class="sm:col-span-2"><label class="block text-xs font-semibold text-slate-500 mb-1">Fecha de nacimiento</label><input type="date" id="form-partner-birthdate"', desktop)

    def test_automatic_biometric_lifecycle_contract(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in ("BIOMETRIC_RELOCK_MS=5*60*1000", "biometricPromptActive", "isInitialAuthenticatedSession", "Confirmá tu identidad para continuar", "localStorage.removeItem(BIOMETRIC_KEY)"):
            self.assertIn(marker, mobile)
        self.assertIn("const MOBILE_READ_ONLY=false", mobile)
        self.assertIn("authUiReadyUid===result.user.uid&&!maintenanceBlocked", mobile)
        self.assertIn("pendingBiometricOfferUid===user.uid&&!maintenanceBlocked", mobile)

    def test_mobile_password_change_ui_is_removed(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for removed_marker in ("Cambiar contraseña", "password-toggle", "password-form", "new-password", "updatePassword"):
            self.assertNotIn(removed_marker, mobile)
        self.assertIn("signInWithEmailAndPassword", mobile)
        self.assertIn('type="password"', mobile)
        for marker in ('id="password-eye"', "input.type=show?'text':'password'", "aria-label", "aria-pressed"):
            self.assertIn(marker, mobile)

    def test_mobile_notice_watchers_are_reused_and_stopped(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn("watchedNoticesUid===user.uid&&stopNoticesWatch&&stopReadsWatch", mobile)
        self.assertGreaterEqual(mobile.count("stopNoticeWatches()"), 4)

    def test_exports_and_notice_files_handle_large_or_partial_operations(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        for marker in ("textToBase64", "downloadTextFile", "new Blob([text]", "deleteNoticeAtomically", "No se aplicaron cambios parciales"):
            self.assertIn(marker, desktop)
        self.assertNotIn('data:text/csv', desktop)
        self.assertNotIn('data:text/json', desktop)
        self.assertIn("expectedTotal!==chunks.length", mobile)
        self.assertIn("request.resource.data.total <= 64", rules)
        self.assertIn("request.resource.data.index < request.resource.data.total", rules)

    def test_global_maintenance_contract(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        for marker in ("MANTENIMIENTO DEL SISTEMA", "toggleGlobalMaintenance", "maintenance-admin-banner", "serverTimestamp()", "maintenance_audit"):
            self.assertIn(marker, desktop)
        for marker in ("maintenance-screen", "watchMaintenance", "includeMetadataChanges:true", "stopNoticeWatches()"):
            self.assertIn(marker, mobile)
        for marker in ("maintenanceEnabled", "isStaffOperational", "maintenance_audit", "allow create, update: if isAdmin()"):
            self.assertIn(marker, rules)
        self.assertIn("assets/mantenimiento.png", service_worker)
        self.assertTrue((ROOT / "assets" / "mantenimiento.png").exists())

    def test_mobile_maintenance_starts_before_authentication(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        self.assertIn("void watchMaintenance();", mobile)
        self.assertIn("onAuthStateChanged(auth,user=>{if(!maintenanceBlocked)void handleAuthState(user)})", mobile)
        self.assertNotIn("stopMaintenanceWatch?.();stopMaintenanceWatch=null;hideMaintenance()", mobile)
        self.assertRegex(rules, r"match /artifacts/\{appId\}/public/config/maintenance/state \{\s*(?://[^\n]*\n\s*)*allow read: if true;")

    def test_maintenance_priority_path_has_no_artificial_delay(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn("if (snapshot.metadata.hasPendingWrites) return", desktop)
        self.assertIn("$('maintenance-screen').classList.remove('hidden');appView.classList.add('hidden')", mobile)
        self.assertIn("yieldForPrioritySignal", mobile)
        self.assertIn("maintenanceEpoch", mobile)
        self.assertIn("notice-dialog-backdrop", mobile)
        maintenance_function = re.search(r"function showMaintenance\(data=\{\}\)\{([^\n]+)", mobile)
        self.assertIsNotNone(maintenance_function)
        body = maintenance_function.group(1)
        self.assertLess(body.index("classList.remove('hidden')"), body.index("stopNoticeWatches()"))

    def test_manifest_is_well_formed_and_hashes_are_sha256(self):
        manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(manifest["sha256"], r"^[A-F0-9]{64}$")
        self.assertRegex(manifest["packageSha256"], r"^[A-F0-9]{64}$")
        self.assertRegex(manifest["installerSha256"], r"^[A-F0-9]{64}$")
        artifacts = {
            "sha256": ROOT / "SIGA.exe",
            "packageSha256": ROOT / "SIGA-update.zip",
            "installerSha256": ROOT / "installer" / f"SIGA-Setup-{manifest['version']}-x64.exe",
        }
        for key, path in artifacts.items():
            with self.subTest(artifact=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                self.assertEqual(manifest[key], digest)
        self.assertEqual(set(manifest["architectures"]), {"x86", "x64"})
        for architecture, metadata in manifest["architectures"].items():
            self.assertEqual(metadata["architecture"], architecture)
            architecture_artifacts = {
                "sha256": ROOT / f"SIGA-{architecture}.exe",
                "packageSha256": ROOT / f"SIGA-update-{architecture}.zip",
                "installerSha256": ROOT / "installer" / f"SIGA-Setup-{manifest['version']}-{architecture}.exe",
            }
            for key, path in architecture_artifacts.items():
                with self.subTest(architecture=architecture, artifact=path.name):
                    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                    self.assertEqual(metadata[key], digest)

    def test_x86_x64_packages_share_the_current_source(self):
        source = (ROOT / "index.html").read_bytes()
        expected_machine = {"x86": 0x014C, "x64": 0x8664}
        for architecture, machine in expected_machine.items():
            executable = (ROOT / f"SIGA-{architecture}.exe").read_bytes()
            pe_offset = int.from_bytes(executable[60:64], "little")
            self.assertEqual(int.from_bytes(executable[pe_offset + 4:pe_offset + 6], "little"), machine)
            with zipfile.ZipFile(ROOT / f"SIGA-update-{architecture}.zip") as package:
                self.assertEqual(package.read("_internal/index.html"), source)
                names = set(package.namelist())
                for runtime_architecture in ("x86", "x64", "arm64"):
                    self.assertIn(
                        f"_internal/webview/lib/runtimes/win-{runtime_architecture}/native/WebView2Loader.dll",
                        names,
                    )


if __name__ == "__main__":
    unittest.main()
