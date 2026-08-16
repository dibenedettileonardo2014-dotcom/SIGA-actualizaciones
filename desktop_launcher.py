"""Desktop launcher for SIGA.

It hosts the bundled static application locally and shows it in a native
Windows WebView window, so end users do not need to start a development server
or open a browser.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64
import ctypes
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import zipfile
from urllib.request import Request, urlopen
from urllib.parse import urlparse

import webview

LOCAL_PORT = 18765
APP_VERSION = "1.4.13"
APP_REVISION = "20260816-01"
UPDATE_MANIFEST_URLS = (
    "https://raw.githubusercontent.com/"
    "dibenedettileonardo2014-dotcom/SIGA-actualizaciones/main/version.json",
    "https://siga-85bdd.web.app/version.json",
)

APP_ARCH = "x64" if platform.architecture()[0] == "64bit" else "x86"
UPDATE_LOG_MAX_BYTES = 512 * 1024
UPDATE_LOG_BACKUPS = 3


class LocalAppServer(ThreadingHTTPServer):
    """Local-only server tuned for quick restarts and clean shutdowns."""

    allow_reuse_address = True
    daemon_threads = True


class QuietRequestHandler(SimpleHTTPRequestHandler):
    """Avoid a console/log bottleneck for every static asset."""

    def log_message(self, format: str, *args: object) -> None:
        pass

    def end_headers(self) -> None:
        if self.path.split("?", 1)[0].endswith((".html", ".js", ".json")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()


def bundled_path() -> Path:
    """Return the folder containing bundled web assets in both modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def webview_storage_path() -> Path:
    """Return a stable per-user folder for the authenticated WebView session."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_folder = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base_folder / "SIGA" / "WebViewProfile"


def update_state_path() -> Path:
    return webview_storage_path().parent / "Updater"


def update_log(event: str, **details: object) -> None:
    """Write bounded diagnostics without credentials, tokens or personal data."""
    try:
        folder = update_state_path()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "update.log"
        if path.exists() and path.stat().st_size >= UPDATE_LOG_MAX_BYTES:
            for index in range(UPDATE_LOG_BACKUPS, 0, -1):
                source = path if index == 1 else folder / f"update.log.{index - 1}"
                destination = folder / f"update.log.{index}"
                if source.exists():
                    if index == UPDATE_LOG_BACKUPS:
                        destination.unlink(missing_ok=True)
                    source.replace(destination)
        safe = {
            re.sub(r"[^A-Za-z0-9_.-]", "_", str(key))[:50]:
            re.sub(r"[\r\n\x00-\x1f]+", " ", str(value))[:300]
            for key, value in details.items()
        }
        record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **safe}
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


class UpdateMutex:
    """Prevent two SIGA processes from preparing the same update."""

    def __init__(self) -> None:
        self.handle = None

    def __enter__(self) -> bool:
        if os.name != "nt":
            return True
        self.handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\SIGA-Update")
        return bool(self.handle) and ctypes.windll.kernel32.GetLastError() != 183

    def __exit__(self, *_args: object) -> None:
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)


def start_server(web_root: Path) -> ThreadingHTTPServer:
    handler = partial(QuietRequestHandler, directory=str(web_root))
    # A fixed port keeps the browser origin stable, so localStorage survives
    # across launches and can be used as an offline backup.
    server = LocalAppServer(("127.0.0.1", LOCAL_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def version_key(value: str) -> tuple[int, ...]:
    """Compare dotted numeric versions without requiring an extra package."""
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", value.strip()):
        raise ValueError("Formato de versión inválido.")
    return tuple(int(part) for part in value.strip().split("."))


def update_metadata(manifest: object, architecture: str = APP_ARCH) -> dict | None:
    """Return only the update metadata matching this executable's architecture."""
    if not isinstance(manifest, dict):
        return None
    architectures = manifest.get("architectures")
    if architectures is None:
        # Every pre-1.4 desktop release was x64. An x86 executable must never
        # consume that legacy channel because its packages contain x64 DLLs.
        return manifest if architecture == "x64" else None
    if not isinstance(architectures, dict):
        return None
    metadata = architectures.get(architecture)
    if not isinstance(metadata, dict):
        return None
    merged = {
        "version": manifest.get("version"),
        "displayVersion": manifest.get("displayVersion", manifest.get("version")),
        "revision": manifest.get("revision", ""),
        **metadata,
    }
    if metadata.get("architecture") != architecture:
        return None
    return merged


def valid_update_manifest(manifest: object, architecture: str = APP_ARCH) -> bool:
    """Reject incomplete or unsafe update metadata before downloading files."""
    manifest = update_metadata(manifest, architecture)
    if not isinstance(manifest, dict):
        return False
    if not isinstance(manifest.get("version"), str):
        return False
    try:
        version_key(manifest["version"])
    except (KeyError, TypeError, ValueError):
        return False
    display_version = manifest.get("displayVersion", manifest["version"])
    if not isinstance(display_version, str):
        return False
    try:
        version_key(display_version)
    except ValueError:
        return False
    if manifest.get("revision", "") and (not isinstance(manifest["revision"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", manifest["revision"])):
        return False
    for url_key, hash_key in (("url", "sha256"), ("packageUrl", "packageSha256"), ("installerUrl", "installerSha256")):
        url = manifest.get(url_key)
        digest = manifest.get(hash_key)
        if url is None and digest is None and url_key in {"packageUrl", "installerUrl"}:
            continue
        if not isinstance(url, str) or not url.startswith("https://"):
            return False
        if not isinstance(digest, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
            return False
    for list_key in ("urls", "packageUrls", "installerUrls"):
        urls = manifest.get(list_key, [])
        if not isinstance(urls, list) or any(not isinstance(url, str) or not url.startswith("https://") for url in urls):
            return False
    for size_key in ("size", "packageSize", "installerSize"):
        size = manifest.get(size_key)
        if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size <= 0):
            return False
    return True


def file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest().upper()
    except OSError:
        return None


def update_required(manifest: dict, executable: Path | None = None) -> bool:
    """Detect newer versions and repaired builds of the same visible version."""
    executable = executable or Path(sys.executable)
    remote_version = manifest.get("displayVersion", manifest.get("version", ""))
    try:
        remote_key = version_key(remote_version)
        local_key = version_key(APP_VERSION)
    except (TypeError, ValueError):
        return False
    if remote_key < local_key:
        return False
    remote_revision = str(manifest.get("revision", ""))
    if remote_key == local_key and (not remote_revision or remote_revision < APP_REVISION):
        return False
    expected_hash = str(manifest.get("sha256", "")).upper()
    local_hash = file_sha256(executable)
    required = remote_key > local_key or not local_hash or local_hash != expected_hash
    update_log("comparison", localRevision=APP_REVISION, remoteRevision=remote_revision, localHash=local_hash or "missing", expectedHash=expected_hash, required=required)
    return required


def fetch_update_manifest() -> dict | None:
    update_log("manifest-check-start", revision=APP_REVISION, architecture=APP_ARCH)
    candidates = []
    for manifest_url in UPDATE_MANIFEST_URLS:
        for attempt in range(1):
            try:
                request = Request(
                    f"{manifest_url}?installed={APP_VERSION}&revision={APP_REVISION}&nonce={time.time_ns()}&attempt={attempt}",
                    headers={"User-Agent": f"SIGA/{APP_VERSION} ({APP_ARCH})", "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"},
                )
                with urlopen(request, timeout=4) as response:
                    manifest = json.load(response)
                if valid_update_manifest(manifest):
                    metadata = update_metadata(manifest)
                    update_log("manifest-valid", source=manifest_url, remoteRevision=metadata.get("revision", ""))
                    candidates.append(metadata)
                    break
            except (OSError, ValueError, json.JSONDecodeError) as error:
                update_log("manifest-error", source=manifest_url, attempt=attempt + 1, error=type(error).__name__)
                time.sleep(2 ** attempt)
    if not candidates:
        return None
    # Los espejos pueden actualizarse con algunos minutos de diferencia.
    return max(
        candidates,
        key=lambda item: (
            version_key(item.get("displayVersion", item.get("version", "0.0.0"))),
            str(item.get("revision", "")),
        ),
    )


def install_update(manifest: dict) -> bool:
    """Download a verified package and schedule its installation after exit."""
    if manifest.get("architecture", APP_ARCH) != APP_ARCH:
        return False
    executable = Path(sys.executable)
    temp_folder = update_state_path()
    temp_folder.mkdir(parents=True, exist_ok=True)
    update_package = temp_folder / f"{executable.stem}.update.zip"
    legacy_replacement = temp_folder / f"{executable.stem}.update.exe"
    update_installer = temp_folder / f"{executable.stem}.update-installer.exe"
    try:
        installer_url = manifest.get("installerUrl")
        installer_hash = manifest.get("installerSha256")
        package_url = manifest.get("packageUrl")
        package_hash = manifest.get("packageSha256")
        is_installer_update = isinstance(installer_url, str) and isinstance(installer_hash, str)
        is_package_update = not is_installer_update and isinstance(package_url, str) and isinstance(package_hash, str)
        configured_urls = manifest.get("installerUrls") if is_installer_update else manifest.get("packageUrls") if is_package_update else manifest.get("urls")
        download_urls = [url for url in (configured_urls or []) if isinstance(url, str)]
        primary_url = installer_url if is_installer_update else package_url if is_package_update else manifest["url"]
        if primary_url not in download_urls:
            download_urls.insert(0, primary_url)
        expected_hash = installer_hash if is_installer_update else package_hash if is_package_update else manifest["sha256"]
        destination = update_installer if is_installer_update else update_package if is_package_update else legacy_replacement
        partial = destination.with_suffix(destination.suffix + ".part")
        last_error = None
        update_log("download-start", revision=manifest.get("revision", ""), architecture=APP_ARCH)
        for download_url in download_urls:
            for attempt in range(3):
                try:
                    digest = hashlib.sha256()
                    separator = "&" if "?" in download_url else "?"
                    cache_safe_url = f"{download_url}{separator}version={manifest.get('version', '')}&sha256={expected_hash[:16]}&attempt={attempt}"
                    request = Request(cache_safe_url + f"&nonce={time.time_ns()}", headers={"User-Agent": f"SIGA/{APP_VERSION} ({APP_ARCH})", "Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
                    with urlopen(request, timeout=120) as response, partial.open("wb") as output:
                        if getattr(response, "status", 200) != 200:
                            raise OSError(f"HTTP {response.status}")
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
                    if digest.hexdigest().lower() != expected_hash.lower():
                        raise ValueError("La verificacion de integridad fallo.")
                    expected_size = manifest.get("installerSize" if is_installer_update else "packageSize" if is_package_update else "size")
                    if isinstance(expected_size, int) and expected_size > 0 and partial.stat().st_size != expected_size:
                        raise ValueError("El tamano descargado no coincide con el manifiesto.")
                    if is_package_update:
                        validate_update_package(partial, APP_ARCH)
                    partial.replace(destination)
                    update_log("download-verified", sha256=expected_hash, size=destination.stat().st_size, attempt=attempt + 1)
                    last_error = None
                    break
                except (OSError, ValueError, zipfile.BadZipFile) as error:
                    last_error = error
                    update_log("download-retry", attempt=attempt + 1, error=type(error).__name__)
                    partial.unlink(missing_ok=True)
                    time.sleep(2 * (attempt + 1))
            if last_error is None:
                break
        if last_error is not None:
            raise last_error
        prepared = {
            "kind": "installer" if is_installer_update else "package" if is_package_update else "executable",
            "path": str(destination), "sha256": expected_hash, "architecture": APP_ARCH,
            "version": manifest.get("displayVersion", manifest.get("version", "")),
            "revision": manifest.get("revision", ""),
        }
        (temp_folder / "prepared-update.json").write_text(json.dumps(prepared), encoding="utf-8")
        update_log("update-prepared", revision=prepared["revision"], kind=prepared["kind"])
        return True
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        update_log("update-failed", error=type(error).__name__)
        update_package.unlink(missing_ok=True)
        legacy_replacement.unlink(missing_ok=True)
        update_installer.unlink(missing_ok=True)
        return False


def apply_prepared_update() -> bool:
    """Apply a verified staged update and relaunch only the canonical installation."""
    state = update_state_path() / "prepared-update.json"
    try:
        prepared = json.loads(state.read_text(encoding="utf-8"))
        source = Path(prepared["path"])
        if prepared.get("architecture") != APP_ARCH or file_sha256(source) != str(prepared.get("sha256", "")).upper():
            raise ValueError("Actualizacion preparada invalida.")
        target = webview_storage_path().parent / "SIGA.exe"
        script = update_state_path() / "SIGA.apply-update.cmd"
        log = update_state_path() / "SIGA.update-installer.log"
        if prepared["kind"] == "installer":
            action = f'start "" /wait "{source}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /CURRENTUSER /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /LOG="{log}"\n'
        elif prepared["kind"] == "package":
            action = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath \'{source}\' -DestinationPath \'{target.parent}\' -Force; if (-not $?) {{ exit 1 }}"\n'
        else:
            action = f'copy /Y "{source}" "{target}" >nul\n'
        script.write_text("@echo off\nsetlocal\n" + f'powershell -NoProfile -ExecutionPolicy Bypass -Command "Wait-Process -Id {os.getpid()} -Timeout 120 -ErrorAction SilentlyContinue"\n' + action + "if errorlevel 1 exit /b 1\n" + f'start "" "{target}"\ndel /q "{source}"\ndel /q "{state}"\ndel "%~f0"\n', encoding="utf-8")
        subprocess.Popen(["cmd.exe", "/d", "/c", str(script)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        update_log("update-apply-start", revision=prepared.get("revision", ""))
        return True
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        update_log("update-apply-failed", error=type(error).__name__)
        return False


def validate_update_package(path: Path, architecture: str) -> None:
    """Reject corrupt, unsafe or cross-architecture packages before installation."""
    expected_machine = {"x86": 0x014C, "x64": 0x8664}[architecture]
    with zipfile.ZipFile(path) as package:
        names = package.namelist()
        if "SIGA.exe" not in names or "_internal/index.html" not in names:
            raise ValueError("El paquete no contiene los archivos criticos.")
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise ValueError("El paquete contiene rutas inseguras.")
        executable = package.read("SIGA.exe")
        if len(executable) < 64:
            raise ValueError("El ejecutable del paquete esta incompleto.")
        pe_offset = int.from_bytes(executable[60:64], "little")
        if executable[pe_offset:pe_offset + 4] != b"PE\0\0" or int.from_bytes(executable[pe_offset + 4:pe_offset + 6], "little") != expected_machine:
            raise ValueError("La arquitectura del paquete no coincide.")


def automatic_update_on_startup() -> bool:
    """Apply an already verified update before opening the old application again."""
    state = update_state_path() / "prepared-update.json"
    if not state.exists():
        return False
    update_log("prepared-update-found-on-startup", revision=APP_REVISION)
    return apply_prepared_update()


class DesktopApi:
    """Native operations explicitly requested from the desktop interface."""

    def get_installed_version(self) -> dict:
        """Return the version embedded in the running executable."""
        return {"version": APP_VERSION, "revision": APP_REVISION, "architecture": APP_ARCH}

    def open_affiliate_app(self, dni: str = "") -> dict:
        """Open the public affiliate portal in the user's default browser."""
        normalized_dni = re.sub(r"\D", "", str(dni or ""))[:9]
        url = "https://siga-85bdd.web.app/"
        if normalized_dni:
            url += f"?dni={normalized_dni}"
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "siga-85bdd.web.app":
            return {"ok": False, "error": "Destino externo no permitido."}
        result = ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
        return {"ok": result > 32, "error": "No se pudo abrir el navegador." if result <= 32 else ""}

    def report_sync_error(self, code: str, message: str) -> dict:
        """Persist a sanitized Firestore diagnostic without record contents."""
        try:
            safe_code = re.sub(r"[^A-Za-z0-9._/-]", "_", str(code or "unknown"))[:100]
            safe_message = re.sub(r"[\r\n\x00-\x1f]+", " ", str(message or "Sin detalle"))[:500]
            log_path = webview_storage_path().parent / "sync-error.log"
            previous = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
            lines = (previous + f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {safe_code} | {safe_message}\n").splitlines()[-200:]
            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return {"ok": True}
        except OSError:
            return {"ok": False}

    def check_update_status(self) -> dict:
        """Check updates through the native channel, avoiding WebView CORS failures."""
        manifest = fetch_update_manifest()
        if not manifest:
            return {"ok": False, "error": "No se pudo conectar con el servidor de actualizaciones."}
        return {
            "ok": True,
            "available": update_required(manifest),
            "manifest": {
                "version": manifest.get("version", ""),
                "displayVersion": manifest.get("displayVersion", manifest.get("version", "")),
                "revision": manifest.get("revision", ""),
                "notes": manifest.get("notes", ""),
            },
        }

    def install_available_update(self) -> dict:
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "La instalación solo está disponible en SIGA compilado."}
        manifest = fetch_update_manifest()
        if not manifest:
            return {"ok": False, "error": "No se pudo consultar el servidor de actualizaciones."}
        if not update_required(manifest):
            return {"ok": False, "error": "SIGA ya tiene la última versión."}
        if not install_update(manifest):
            return {"ok": False, "error": "No se pudo preparar la actualización."}
        return {"ok": True, "ready": True, "version": manifest["version"]}

    def apply_prepared_update(self) -> dict:
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "La instalación solo está disponible en SIGA compilado."}
        if not apply_prepared_update():
            return {"ok": False, "error": "No se pudo iniciar la actualización preparada."}
        threading.Timer(0.6, self._close_window).start()
        return {"ok": True}

    def save_and_open_file(self, filename: str, content_base64: str) -> dict:
        """Save an exported document in Documents and open its default Windows app."""
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name).strip(" .")
        extension = Path(safe_name).suffix.lower()
        if not safe_name or extension not in {".xlsx", ".pdf", ".csv", ".json"}:
            return {"ok": False, "error": "Nombre o tipo de archivo no permitido."}
        try:
            content = base64.b64decode(content_base64, validate=True)
            if len(content) > 64 * 1024 * 1024:
                raise ValueError("El archivo supera el límite seguro de 64 MB.")
            documents_buffer = ctypes.create_unicode_buffer(260)
            result = ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, documents_buffer)
            documents = Path(documents_buffer.value) if result == 0 and documents_buffer.value else Path.home() / "Documents"
            local_documents = (Path(sys.executable).parent if getattr(sys, "frozen", False) else bundled_path()) / "Documentos"
            destination = None
            export_folder = None
            last_error = None
            for candidate in (documents / "SIGA", local_documents):
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    candidate_destination = candidate / safe_name
                    temporary = candidate / f".{safe_name}.tmp"
                    temporary.write_bytes(content)
                    temporary.replace(candidate_destination)
                    destination = candidate_destination
                    export_folder = candidate
                    break
                except OSError as error:
                    last_error = error
            if destination is None or export_folder is None:
                raise last_error or OSError("No hay una carpeta local disponible para la exportación.")
            open_result = ctypes.windll.shell32.ShellExecuteW(None, "open", str(destination), None, str(export_folder), 1)
            if open_result <= 32:
                return {"ok": True, "opened": False, "path": str(destination), "error": "Windows no tiene una aplicación asociada para abrir este archivo."}
            return {"ok": True, "opened": True, "path": str(destination)}
        except (OSError, ValueError) as error:
            return {"ok": False, "error": f"No se pudo guardar o abrir el archivo: {error}"}

    @staticmethod
    def _close_window() -> None:
        if webview.windows:
            webview.windows[0].destroy()


def main() -> None:
    if automatic_update_on_startup():
        return
    try:
        server = start_server(bundled_path())
    except OSError:
        ctypes.windll.user32.MessageBoxW(
            None,
            "SIGA ya está abierta o el puerto local está ocupado. Cerrá la otra instancia y volvé a intentar.",
            "SIGA",
            0x30,
        )
        return
    host, port = server.server_address
    window = webview.create_window(
        "SIGA - Sistema de Gestión Sindical",
        f"http://{host}:{port}/index.html?revision={APP_REVISION}",
        js_api=DesktopApi(),
        width=1440,
        height=900,
        min_size=(1024, 700),
        maximized=True,
    )
    try:
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(webview_storage_path()),
        )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
