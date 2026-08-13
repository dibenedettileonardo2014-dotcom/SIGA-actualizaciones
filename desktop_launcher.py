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
import re
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen

import webview

LOCAL_PORT = 18765
APP_VERSION = "1.3.5"
UPDATE_MANIFEST_URLS = (
    "https://raw.githubusercontent.com/"
    "dibenedettileonardo2014-dotcom/SIGA-actualizaciones/main/version.json",
    "https://siga-85bdd.web.app/version.json",
)


class LocalAppServer(ThreadingHTTPServer):
    """Local-only server tuned for quick restarts and clean shutdowns."""

    allow_reuse_address = True
    daemon_threads = True


class QuietRequestHandler(SimpleHTTPRequestHandler):
    """Avoid a console/log bottleneck for every static asset."""

    def log_message(self, format: str, *args: object) -> None:
        pass


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


def valid_update_manifest(manifest: object) -> bool:
    """Reject incomplete or unsafe update metadata before downloading files."""
    if not isinstance(manifest, dict):
        return False
    if not isinstance(manifest.get("version"), str):
        return False
    try:
        version_key(manifest["version"])
    except (KeyError, TypeError, ValueError):
        return False
    for url_key, hash_key in (("url", "sha256"), ("packageUrl", "packageSha256")):
        url = manifest.get(url_key)
        digest = manifest.get(hash_key)
        if url is None and digest is None and url_key == "packageUrl":
            continue
        if not isinstance(url, str) or not url.startswith("https://"):
            return False
        if not isinstance(digest, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
            return False
    for list_key in ("urls", "packageUrls"):
        urls = manifest.get(list_key, [])
        if not isinstance(urls, list) or any(not isinstance(url, str) or not url.startswith("https://") for url in urls):
            return False
    return True


def fetch_update_manifest() -> dict | None:
    for manifest_url in UPDATE_MANIFEST_URLS:
        for attempt in range(2):
            try:
                request = Request(
                    f"{manifest_url}?installed={APP_VERSION}&attempt={attempt}",
                    headers={"User-Agent": f"SIGA/{APP_VERSION}"},
                )
                with urlopen(request, timeout=20) as response:
                    manifest = json.load(response)
                if valid_update_manifest(manifest):
                    return manifest
            except (OSError, ValueError, json.JSONDecodeError):
                time.sleep(1)
    return None


def install_update(manifest: dict) -> bool:
    """Download a verified package and schedule its installation after exit."""
    executable = Path(sys.executable)
    temp_folder = Path(tempfile.gettempdir()) / "SIGA-updater"
    temp_folder.mkdir(parents=True, exist_ok=True)
    update_package = temp_folder / f"{executable.stem}.update.zip"
    legacy_replacement = temp_folder / f"{executable.stem}.update.exe"
    try:
        package_url = manifest.get("packageUrl")
        package_hash = manifest.get("packageSha256")
        is_package_update = isinstance(package_url, str) and isinstance(package_hash, str)
        configured_urls = manifest.get("packageUrls") if is_package_update else manifest.get("urls")
        download_urls = [url for url in (configured_urls or []) if isinstance(url, str)]
        primary_url = package_url if is_package_update else manifest["url"]
        if primary_url not in download_urls:
            download_urls.insert(0, primary_url)
        expected_hash = package_hash if is_package_update else manifest["sha256"]
        destination = update_package if is_package_update else legacy_replacement
        partial = destination.with_suffix(destination.suffix + ".part")
        last_error = None
        for download_url in download_urls:
            for attempt in range(3):
                try:
                    digest = hashlib.sha256()
                    request = Request(download_url, headers={"User-Agent": f"SIGA/{APP_VERSION}"})
                    with urlopen(request, timeout=120) as response, partial.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
                    if digest.hexdigest().lower() != expected_hash.lower():
                        raise ValueError("La verificacion de integridad fallo.")
                    partial.replace(destination)
                    last_error = None
                    break
                except (OSError, ValueError) as error:
                    last_error = error
                    partial.unlink(missing_ok=True)
                    time.sleep(2 * (attempt + 1))
            if last_error is None:
                break
        if last_error is not None:
            raise last_error
        script = temp_folder / f"{executable.stem}.update.cmd"
        if is_package_update:
            script_contents = (
                "@echo off\nsetlocal\n"
                f"set \"PACKAGE={update_package}\"\n"
                f"set \"TARGETDIR={executable.parent}\"\n"
                f"set \"TARGET={executable}\"\n"
                "timeout /t 2 /nobreak >nul\n"
                "powershell -NoProfile -ExecutionPolicy Bypass -Command \"Expand-Archive -LiteralPath $env:PACKAGE -DestinationPath $env:TARGETDIR -Force\"\n"
                "if exist \"%PACKAGE%\" del /q \"%PACKAGE%\"\n"
                "start \"\" \"%TARGET%\"\n"
                "del \"%~f0\"\n"
            )
        else:
            script_contents = (
                "@echo off\nsetlocal\n"
                f"set \"SOURCE={legacy_replacement}\"\n"
                f"set \"TARGET={executable}\"\n"
                "for /L %%i in (1,1,30) do (\n"
                "  move /Y \"%SOURCE%\" \"%TARGET%\" >nul 2>&1\n"
                "  if not exist \"%SOURCE%\" goto launch\n"
                "  timeout /t 1 /nobreak >nul\n)\nexit /b 1\n:launch\n"
                "start \"\" \"%TARGET%\"\ndel \"%~f0\"\n"
            )
        script.write_text(script_contents, encoding="utf-8")
        permission_probe = executable.parent / ".siga-update-permission"
        requires_elevation = False
        try:
            permission_probe.write_text("ok", encoding="ascii")
            permission_probe.unlink(missing_ok=True)
        except OSError:
            requires_elevation = True
        if requires_elevation:
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f'/d /c "{script}"', None, 0
            )
            if result <= 32:
                raise OSError("Windows no autorizo la instalacion de la actualizacion.")
        else:
            subprocess.Popen(
                ["cmd.exe", "/d", "/c", str(script)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return True
    except (OSError, ValueError):
        update_package.unlink(missing_ok=True)
        legacy_replacement.unlink(missing_ok=True)
        ctypes.windll.user32.MessageBoxW(
            None,
            "No se pudo descargar la actualizacion. Intenta nuevamente mas tarde.",
            "SIGA",
            0x10,
        )
        return False


class DesktopApi:
    """Native operations explicitly requested from the desktop interface."""

    def report_sync_error(self, code: str, message: str) -> dict:
        """Persist a sanitized Firestore diagnostic without record contents."""
        try:
            safe_code = re.sub(r"[^A-Za-z0-9._/-]", "_", str(code or "unknown"))[:100]
            safe_message = re.sub(r"[\r\n\x00-\x1f]+", " ", str(message or "Sin detalle"))[:500]
            log_path = webview_storage_path().parent / "sync-error.log"
            log_path.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {safe_code} | {safe_message}\n", encoding="utf-8")
            return {"ok": True}
        except OSError:
            return {"ok": False}

    def install_available_update(self) -> dict:
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "La instalación solo está disponible en SIGA compilado."}
        manifest = fetch_update_manifest()
        if not manifest:
            return {"ok": False, "error": "No se pudo consultar el servidor de actualizaciones."}
        try:
            if version_key(manifest["version"]) <= version_key(APP_VERSION):
                return {"ok": False, "error": "SIGA ya tiene la última versión."}
        except (KeyError, ValueError):
            return {"ok": False, "error": "El manifiesto de actualización no es válido."}
        if not install_update(manifest):
            return {"ok": False, "error": "No se pudo preparar la actualización."}
        threading.Timer(0.6, self._close_window).start()
        return {"ok": True, "version": manifest["version"]}

    def save_and_open_file(self, filename: str, content_base64: str) -> dict:
        """Save an exported document in Documents and open its default Windows app."""
        safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(filename).name).strip(" .")
        extension = Path(safe_name).suffix.lower()
        if not safe_name or extension not in {".xlsx", ".pdf"}:
            return {"ok": False, "error": "Nombre o tipo de archivo no permitido."}
        try:
            content = base64.b64decode(content_base64, validate=True)
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
        f"http://{host}:{port}/index.html",
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
