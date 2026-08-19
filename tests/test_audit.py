import json
import hashlib
import io
import re
import subprocess
import tempfile
import unittest
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

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
            "url": "https://raw.githubusercontent.com/test/SIGA.exe",
            "sha256": "A" * 64,
            "packageUrl": "https://siga-85bdd.web.app/SIGA.zip",
            "packageSha256": "b" * 64,
        }
        self.assertTrue(desktop_launcher.valid_update_manifest(valid, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest(valid, "x86"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "url": "http://example.test/SIGA.exe"}, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "sha256": "bad"}, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**valid, "urls": ["http://example.test/SIGA.exe"]}, "x64"))
        installer = {**valid, "installerUrl": "https://github.com/test/SIGA-Setup.exe", "installerSha256": "C" * 64}
        self.assertTrue(desktop_launcher.valid_update_manifest(installer, "x64"))
        self.assertFalse(desktop_launcher.valid_update_manifest({**installer, "installerSha256": "bad"}, "x64"))

    def test_update_manifest_selects_only_matching_architecture(self):
        artifact = {
            "architecture": "x86", "url": "https://raw.githubusercontent.com/test/SIGA-x86.exe",
            "sha256": "A" * 64, "packageUrl": "https://siga-85bdd.web.app/SIGA-x86.zip",
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
        self.assertIn('start "" /wait "{source}"', source)
        self.assertIn('/CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS', source)
        self.assertIn('if errorlevel 1 exit /b 1', source)
        self.assertNotIn('timeout /t 2 /nobreak', source)
        self.assertIn('cache_safe_url', source)
        self.assertIn('"Cache-Control": "no-cache, no-store"', source)
        self.assertIn('automatic_update_on_startup()', source)
        self.assertIn('Local\\\\SIGA-Update', source)
        self.assertIn('UPDATE_LOG_MAX_BYTES', source)
        self.assertIn('Cache-Control", "no-store, no-cache, must-revalidate, max-age=0', source)
        self.assertIn('index.html?revision={APP_REVISION}', source)

    def test_silent_update_preserves_and_repairs_desktop_shortcut(self):
        launcher = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        installer = (ROOT / "siga-installer.iss").read_text(encoding="utf-8")
        self.assertNotIn('Name: "{userdesktop}\\SIGA.lnk"', installer.split("[InstallDelete]", 1)[1].split("[Icons]", 1)[0])
        self.assertNotIn('Name: "{commondesktop}\\SIGA.lnk"', installer)
        self.assertNotIn('Filename: "{sys}\\explorer.exe"', installer)
        self.assertIn('Filename: "{app}\\{#MyAppExeName}"', installer)
        self.assertIn("CreateShortcut", launcher)
        self.assertIn("SpecialFolders.Item(\\'Desktop\\')", launcher)
        self.assertIn("$s.Arguments=\\'\\'", launcher)

    def test_same_visible_version_is_repaired_by_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "SIGA.exe"
            executable.write_bytes(b"old build")
            digest = hashlib.sha256(b"corrected build").hexdigest().upper()
            manifest = {"displayVersion": desktop_launcher.APP_VERSION, "sha256": digest, "revision": desktop_launcher.APP_REVISION}
            self.assertTrue(desktop_launcher.update_required(manifest, executable))
            executable.write_bytes(b"corrected build")
            self.assertFalse(desktop_launcher.update_required(manifest, executable))
            self.assertFalse(desktop_launcher.update_required({"displayVersion": desktop_launcher.APP_VERSION, "sha256": "0" * 64, "revision": "20260814-99"}, executable))

    def test_interrupted_download_retries_without_leaving_partial_file(self):
        payload = b"corrected executable"
        response = io.BytesIO(payload)
        response.status = 200
        manifest = {
            "version": "1.4.13", "displayVersion": "1.4.13", "revision": desktop_launcher.APP_REVISION,
            "architecture": desktop_launcher.APP_ARCH,
            "url": "https://raw.githubusercontent.com/test/SIGA.exe", "urls": ["https://raw.githubusercontent.com/test/SIGA.exe"],
            "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload),
        }
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(desktop_launcher, "update_state_path", return_value=Path(folder)), \
                mock.patch.object(desktop_launcher, "urlopen", side_effect=[OSError("connection lost"), response]), \
                mock.patch.object(desktop_launcher.time, "sleep"):
            self.assertTrue(desktop_launcher.install_update(manifest))
            self.assertTrue((Path(folder) / "prepared-update.json").exists())
            self.assertFalse(any(Path(folder).glob("*.part")))

    def test_sync_diagnostics_preserve_recent_history(self):
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(desktop_launcher, "webview_storage_path", return_value=Path(folder) / "webview"):
            api = desktop_launcher.DesktopApi()
            self.assertTrue(api.report_sync_error("offline", "primer error")["ok"])
            self.assertTrue(api.report_sync_error("retry", "segundo error")["ok"])
            log = (Path(folder) / "sync-error.log").read_text(encoding="utf-8")
            self.assertIn("primer error", log)
            self.assertIn("segundo error", log)

    def test_packages_are_validated_for_their_own_architecture(self):
        desktop_launcher.validate_update_package(ROOT / "SIGA-update-x86.zip", "x86")
        desktop_launcher.validate_update_package(ROOT / "SIGA-update-x64.zip", "x64")
        with self.assertRaises(ValueError):
            desktop_launcher.validate_update_package(ROOT / "SIGA-update-x86.zip", "x64")


class ApplicationSourceTests(unittest.TestCase):
    def test_mobile_entrypoint_is_not_cached_by_hosting(self):
        firebase_config = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
        headers = {
            item["source"]: {header["key"]: header["value"] for header in item["headers"]}
            for item in firebase_config["hosting"]["headers"]
        }
        self.assertEqual(headers["/"]["Cache-Control"], "no-cache")
        self.assertEqual(headers["/sw.js"]["Cache-Control"], "no-cache")

    def test_mobile_navigation_falls_back_to_cached_shell_after_timeout(self):
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn("NAVIGATION_NETWORK_TIMEOUT_MS", service_worker)
        self.assertIn("Promise.race([network, timeout])", service_worker)
        self.assertIn("await caches.match('./index.html')", service_worker)

    def test_legacy_desktop_can_fetch_update_manifest_cross_origin(self):
        firebase_config = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
        version_headers = next(item["headers"] for item in firebase_config["hosting"]["headers"] if item["source"] == "/version.json")
        values = {item["key"]: item["value"] for item in version_headers}
        self.assertEqual(values["Access-Control-Allow-Origin"], "*")
        self.assertEqual(values["Cache-Control"], "no-cache")

    def test_cache_revision_matches_current_internal_revision(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        revision = re.search(r'const APP_REVISION = "([^"]+)"', desktop).group(1)
        self.assertIn(f"r{revision}", service_worker)
        self.assertEqual(service_worker, (ROOT / "hosting" / "sw.js").read_text(encoding="utf-8"))

    def test_last_verified_maintenance_state_supports_offline_recovery(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in ("maintenanceCacheKey", "readVerifiedMaintenance", "cacheVerifiedMaintenance"):
            self.assertIn(marker, desktop)
        for marker in ("MAINTENANCE_CACHE_KEY", "readVerifiedMaintenance", "cacheVerifiedMaintenance", "applyMaintenanceState"):
            self.assertIn(marker, mobile)

    def test_corrupt_pending_queue_is_preserved_for_recovery(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("_corrupt_${Date.now()}", desktop)
        self.assertIn("se conserva un respaldo para recuperación", desktop)

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
        self.assertIn("validMobileCredential", rules)
        self.assertIn("allow create: if isStaffOperational(appId) && validMobileCredential(appId)", rules)
        self.assertIn("validPayment", rules)
        self.assertIn("request.resource.data.revision == resource.data.revision + 1", rules)

    def test_payments_confirm_before_marking_affiliate_paid(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        payment_save = desktop.index("await commitPaymentToDatabase(payment);")
        affiliate_update = desktop.index("if (!affiliate.hasPaid)", payment_save)
        self.assertLess(payment_save, affiliate_update)
        self.assertIn("await removePaymentFromDatabase(payment.id)", desktop)

    def test_runtime_dependencies_are_local_and_mobile_offline_shell_includes_firebase(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        for source in (desktop, mobile):
            self.assertIn("./assets/vendor/firebase.js", source)
            self.assertNotIn("gstatic.com/firebasejs", source)
            self.assertIn("Content-Security-Policy", source)
        self.assertIn("'./assets/vendor/firebase.js'", service_worker)
        for filename in ("firebase.js", "tailwind.css", "chart.js", "xlsx.js", "jspdf.js", "jspdf-autotable.js"):
            self.assertTrue((ROOT / "assets" / "vendor" / filename).is_file(), filename)

    def test_fontawesome_fonts_resolve_beside_the_local_stylesheet(self):
        stylesheet = (ROOT / "assets" / "vendor" / "fontawesome.css").read_text(encoding="utf-8")
        declared_fonts = re.findall(r"url\((?:['\"]?)(webfonts/[^)'\"]+)", stylesheet)
        self.assertTrue(declared_fonts)
        for relative_path in declared_fonts:
            self.assertTrue((ROOT / "assets" / "vendor" / relative_path).is_file(), relative_path)

    def test_mobile_convention_uses_native_images_with_navigation_and_pdf_fallback(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertNotIn('<iframe class="convention"', mobile)
        self.assertNotIn("pdfjs/", mobile)
        for marker in ("convention-image", "CONVENTION_PAGE_COUNT=29", "renderConventionPage", "convention-prev", "convention-next", "download>Abrir PDF"):
            self.assertIn(marker, mobile)
        pages = sorted((ROOT / "assets" / "convenio-77-89-pages").glob("page-*.jpg"))
        self.assertEqual(len(pages), 29)
        self.assertIn("'./assets/convenio-77-89-pages/page-01.jpg'", service_worker)
        self.assertNotIn("pdfjs/", service_worker)

    def test_affiliate_register_shows_calculated_age_and_mobile_has_direct_convention_access(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn('>Edad</th>', desktop)
        self.assertIn("formatAffiliateAge(a.birthdate)", desktop)
        self.assertIn('id="open-convention-button"', mobile)
        self.assertIn("[data-view=\"convention-view\"]", mobile)

    def test_notice_updates_and_staff_mobile_access_creation_are_validated(self):
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        self.assertIn("allow create, update: if isStaffOperational(appId) && validNotice(noticeId)", rules)
        self.assertIn("allow create, update: if isStaffOperational(appId) && validNoticeChunk()", rules)
        self.assertIn("allow create: if isStaffOperational(appId) && validMobileCredential(appId)", rules)

    def test_notice_replacements_are_committed_atomically(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("async function saveNoticeAtomically", desktop)
        self.assertIn("obsoleteDocs.forEach(item=>batch.delete(item.ref))", desktop)
        self.assertIn("batch.set(doc(noticeCollection(),noticeId),data);await batch.commit()", desktop)

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
        self.assertIn(".notice-thumb{display:block;width:100%;height:auto;max-height:70vh;object-fit:contain", mobile)

    def test_admin_and_operator_can_manage_existing_notices(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        self.assertNotIn('body[data-role="operador"] #btn-tab-comunicados', desktop)
        self.assertIn("['admin','operador'].includes(window.appState.currentUserRole)", desktop)
        for action in ("notice-edit", "notice-toggle", "notice-delete"):
            self.assertNotIn(f'body[data-role="operador"] #notice-table .{action}', desktop)
        notice_rules = rules[rules.index("match /artifacts/{appId}/public/data/comunicados/{noticeId}"):]
        self.assertIn("allow create, update: if isStaffOperational(appId) && validNotice(noticeId)", notice_rules)
        self.assertIn("allow create, update: if isStaffOperational(appId) && validNoticeChunk()", notice_rules)
        self.assertGreaterEqual(notice_rules.count("allow delete: if isStaffOperational(appId);"), 2)
        for marker in ("notice-edit-id", "saveNoticeAtomically(id,data,replacements)", "deleteNoticeAtomically(item.id)", "if(!confirm(`¿Eliminar definitivamente", "onSnapshot(noticeCollection()"):
            self.assertIn(marker, desktop)

    def test_affiliate_form_layout_contract(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('class="grid grid-cols-1 sm:grid-cols-3 gap-4"', desktop)
        self.assertIn('>Trabaja por consultora</span>', desktop)
        self.assertIn('class="grid grid-cols-1 sm:grid-cols-6 gap-3"', desktop)
        self.assertIn('class="sm:col-span-2"><label class="block text-xs font-semibold text-slate-500 mb-1">Fecha de nacimiento</label><input type="date" id="form-partner-birthdate"', desktop)

    def test_affiliate_company_filter_and_print_contract(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        for marker in (
            'id="filter-company"',
            'id="company-filter-options"',
            "normalizeSearch(a.company).includes(companyVal)",
            "clearAffiliateFilters",
            'id="affiliate-result-count"',
            "affiliateRegisterHtml",
            "previewAffiliateRegister",
            'id="affiliate-print-modal"',
            'id="affiliate-print-frame"',
            "frame.contentWindow.print()",
            "@page{size:A4 portrait",
            "thead{display:table-header-group}",
            "Página <span class=\"page-number\"",
            "assets/siga-desktop-icon-128.png",
        ):
            self.assertIn(marker, desktop)
        self.assertNotIn('id="filter-sector"', desktop)
        self.assertNotIn("window.open('', '_blank')", desktop)
        self.assertIn("return matchQuery && matchCompany && matchPayment && matchStatus", desktop)
        self.assertIn("String(a.company || '').localeCompare", desktop)

    def test_payments_support_company_scope_and_unique_period_concept(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        for marker in (
            'id="payment-company-filter"',
            'id="payment-company-summary"',
            'id="btn-submit-company-payment"',
            'id="payment-concept"',
            "paymentCompanyAffiliates",
            "selectedPaymentCompany",
            "paymentAlreadyExists",
            "paymentDocumentId",
            "sendPaymentTransaction",
            "payment-duplicate",
            "registerCompanyPayments",
            "affiliateNumber: String(affiliate.number || '')",
            "company: String(affiliate.company || '')",
        ):
            self.assertIn(marker, desktop)
        for marker in ("affiliateNumber", "uniquenessKey", "clientMutationId", ".data.company == request.resource.data.company"):
            self.assertIn(marker, rules)

    def test_connectivity_recovery_rechecks_native_update(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("checkUpdateAfterConnectivityRecovery", desktop)
        self.assertIn("await flushPendingChanges();", desktop)
        self.assertIn("await checkUpdateAfterConnectivityRecovery();", desktop)
        self.assertLess(desktop.rindex("await flushPendingChanges();"), desktop.rindex("await checkUpdateAfterConnectivityRecovery();"))
        self.assertIn("if (!window.appState.firebaseEnabled) await setupFirebase();", desktop)
        self.assertIn("window.addEventListener('pagehide'", desktop)
        self.assertIn("manifest.revision > APP_REVISION", desktop)
        self.assertNotIn("manifest.revision !== APP_REVISION", desktop)
        self.assertIn("verifica, descarga y aplica automáticamente", desktop)
        self.assertIn("window.pywebview?.api?.check_update_status", desktop)
        self.assertIn("def check_update_status(self)", (ROOT / "desktop_launcher.py").read_text(encoding="utf-8"))
        self.assertNotIn("document.getElementById('error-message').textContent = error.message ||", desktop)

    def test_manifest_selection_compares_all_update_mirrors(self):
        source = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn("candidates.append(metadata)", source)
        self.assertIn("return max(", source)
        self.assertIn('str(item.get("revision", ""))', source)

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

    def test_mobile_credential_exports_high_quality_jpeg(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in (
            "Guardar credencial en galería",
            "canvas.width=1712;canvas.height=1080",
            "'image/jpeg',.96",
            "navigator.canShare?.({files:[file]})",
            "Elegí “Guardar imagen”",
            "URL.revokeObjectURL(url)",
        ):
            self.assertIn(marker, mobile)
        self.assertNotIn('id="print-button"', mobile)
        self.assertNotIn("window.print()", mobile)

    def test_digital_credential_includes_spiqyp_logo(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        for source in (desktop, mobile, service_worker):
            self.assertIn("assets/logo-spiqyp-rosario.png", source)
        self.assertIn("context.drawImage(logo", desktop)
        self.assertIn("context.drawImage(logo", mobile)
        self.assertTrue((ROOT / "assets" / "logo-spiqyp-rosario.png").exists())

    def test_mobile_notice_watchers_are_reused_and_stopped(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn("watchedNoticesUid===user.uid&&stopNoticesWatch&&stopReadsWatch", mobile)
        self.assertGreaterEqual(mobile.count("stopNoticeWatches()"), 4)

    def test_mobile_thumbnail_fragments_are_cached_per_notice_revision(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in ("noticeThumbnailCache", "noticeThumbnailUrl(item)", "activeKeys", "clearNoticeThumbnailCache"):
            self.assertIn(marker, mobile)

    def test_mobile_offline_credential_cache_is_scoped_to_authenticated_uid(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn("function readCachedCredential(user)", mobile)
        self.assertIn("cached?.uid===user?.uid", mobile)
        self.assertIn("JSON.stringify({uid:user.uid,data})", mobile)
        self.assertIn("copia sin conexión", mobile)
        self.assertIn("snapshot.metadata.fromCache&&cached", mobile)

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
        self.assertIn("const initialMaintenanceCheck=watchMaintenance();", mobile)
        self.assertIn("initialMaintenanceCheck.then", mobile)
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

    def test_automatic_mobile_access_and_staff_credential_creation(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const savedAffiliate = await commitToDatabase(affiliate)", desktop)
        self.assertIn("provisionMobileAccess(savedAffiliate, 'sindicatoquimico')", desktop)
        self.assertIn('body[data-role="operador"] #btn-tab-credenciales', desktop)
        self.assertIn('<body data-role="operador"', desktop)
        self.assertIn("const VERIFIED_ROLE_KEY = 'siga_last_verified_role'", desktop)
        self.assertIn("if (cachedRole === 'admin' || cachedRole === 'operador')", desktop)
        self.assertIn("if (!window.__sigaRoleVisualReady) document.body.style.visibility = 'hidden'", desktop)
        self.assertIn("document.body.style.visibility = ''", desktop)
        self.assertIn("window.appState.auth?.currentUser?.email !== roleAuthEmails[role]", desktop)
        self.assertIn("localStorage.removeItem(VERIFIED_ROLE_KEY)", desktop)
        self.assertIn("window.appState.currentUserRole === 'admin'", desktop)
        self.assertIn("'errores', 'usuarios', 'configuracion', 'mantenimiento'", desktop)

    def test_admin_can_review_local_sync_conflicts(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        for marker in ('id="btn-tab-errores"', 'id="tab-errores"', "function renderConflictsTab()", "window.retryPendingConflicts"):
            self.assertIn(marker, desktop)
        self.assertIn("conflictCode: error.code", desktop)
        self.assertIn("conflictReason: error.message", desktop)
        self.assertIn("clearAcknowledgedPendingChanges('afiliados'", desktop)
        self.assertIn("acknowledgedAffiliates.forEach(syncMobileCredential)", desktop)
        self.assertIn("function waitForPendingChange(change", desktop)
        self.assertNotIn("siga_mobile_credential_repaired_35463065", desktop)

    def test_cross_device_diagnostics_are_private_sanitized_and_admin_only(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        for marker in ("flushDiagnosticQueue", "sanitizeDiagnostic", "reporterUid", "DIAGNOSTIC_QUEUE_LIMIT"):
            self.assertIn(marker, desktop)
            self.assertIn(marker, mobile)
        for marker in ("setupDiagnosticsWatch", "renderDiagnostics", "clearResolvedDiagnostics"):
            self.assertIn(marker, desktop)
        for secret_marker in ("[correo]", "[dni]", "[token]", "[clave]"):
            self.assertIn(secret_marker, desktop)
            self.assertIn(secret_marker, mobile)
        self.assertIn("match /artifacts/{appId}/diagnostics/{eventId}", rules)
        self.assertIn("allow read: if isAdmin()", rules)
        self.assertIn("allow create: if (isStaff() || isEnabledAffiliate(appId))", rules)
        self.assertIn("validDiagnostic()", rules)

    def test_mobile_login_distinguishes_network_and_credentials(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        for marker in ("authenticateMobile", "loginErrorMessage", "auth/network-request-failed", "auth/too-many-requests", "auth/user-disabled", "mobile/post-login"):
            self.assertIn(marker, mobile)

    def test_mixed_health_safety_committee_is_saved_and_shown_on_mobile_credential(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn('id="form-is-mixed-health-safety-committee"', desktop)
        self.assertIn("isMixedHealthSafetyCommittee: document.getElementById('form-is-mixed-health-safety-committee').checked", desktop)
        self.assertIn("isMixedHealthSafetyCommittee: Boolean(affiliate.isMixedHealthSafetyCommittee)", desktop)
        for source in (desktop, mobile):
            self.assertIn("Comité Mixto de Higiene y Seguridad", source)

    def test_about_reads_the_version_from_the_running_executable(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        launcher = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn('id="about-installed-version"', desktop)
        self.assertIn("window.pywebview.api.get_installed_version()", desktop)

    def test_affiliate_portal_opens_in_external_browser(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        launcher = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn("openAffiliateAppInBrowser()", desktop)
        self.assertIn("window.pywebview.api.open_affiliate_app(dni)", desktop)
        self.assertIn("def open_affiliate_app(self, dni", launcher)
        self.assertIn('parsed.netloc != "siga-85bdd.web.app"', launcher)
        self.assertIn("new URLSearchParams(location.search).get('dni')", mobile)
        self.assertIn("def get_installed_version(self)", launcher)

    def test_update_is_staged_and_relaunched_from_canonical_install(self):
        desktop = (ROOT / "index.html").read_text(encoding="utf-8")
        launcher = (ROOT / "desktop_launcher.py").read_text(encoding="utf-8")
        self.assertIn('id="update-ready-banner"', desktop)
        self.assertIn('id="restart-update-button"', desktop)
        self.assertIn("void window.downloadAndInstallUpdate()", desktop)
        self.assertIn("def apply_prepared_update()", launcher)
        self.assertIn('state = update_state_path() / "prepared-update.json"', launcher)
        self.assertIn('return apply_prepared_update()', launcher)
        self.assertIn('webview_storage_path().parent / "SIGA.exe"', launcher)
        self.assertNotIn('f"set \\"TARGET={executable}\\"', launcher)

    def test_mobile_uses_device_screen_lock(self):
        mobile = (ROOT / "afiliado.html").read_text(encoding="utf-8")
        self.assertIn('Usar bloqueo del dispositivo', mobile)
        self.assertIn('patrón, PIN, contraseña, huella o rostro', mobile)
        self.assertIn('platformAuthenticatorPromise', mobile)

    def test_manifest_is_well_formed_and_hashes_are_sha256(self):
        manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+(?:\.\d+)?$")
        self.assertEqual(manifest["displayVersion"], "1.4.32")
        self.assertRegex(manifest["revision"], r"^\d{8}-\d{2}$")
        self.assertRegex(manifest["sha256"], r"^[A-F0-9]{64}$")
        self.assertRegex(manifest["packageSha256"], r"^[A-F0-9]{64}$")
        self.assertNotIn("installerUrl", manifest)
        self.assertNotIn("installerSha256", manifest)
        artifacts = {
            "sha256": ROOT / "SIGA.exe",
            "packageSha256": ROOT / "SIGA-update.zip",
        }
        for key, path in artifacts.items():
            with self.subTest(artifact=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                self.assertEqual(manifest[key], digest)
                self.assertEqual(manifest[{"sha256": "size", "packageSha256": "packageSize", "installerSha256": "installerSize"}[key]], path.stat().st_size)
        self.assertEqual(set(manifest["architectures"]), {"x86", "x64"})
        self.assertIn(manifest["displayVersion"], manifest["packageUrl"])
        for architecture, metadata in manifest["architectures"].items():
            self.assertEqual(metadata["architecture"], architecture)
            self.assertIn(manifest["displayVersion"], metadata["packageUrl"])
            self.assertNotIn("installerUrl", metadata)
            self.assertNotIn("installerSha256", metadata)
            architecture_artifacts = {
                "sha256": ROOT / f"SIGA-{architecture}.exe",
                "packageSha256": ROOT / f"SIGA-update-{architecture}.zip",
            }
            for key, path in architecture_artifacts.items():
                with self.subTest(architecture=architecture, artifact=path.name):
                    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                    self.assertEqual(metadata[key], digest)
                    self.assertEqual(metadata[{"sha256": "size", "packageSha256": "packageSize", "installerSha256": "installerSize"}[key]], path.stat().st_size)

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
