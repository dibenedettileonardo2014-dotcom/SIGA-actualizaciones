"""Desktop launcher for SIGA.

It hosts the bundled static application locally and shows it in a native
Windows WebView window, so end users do not need to start a development server
or open a browser.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ctypes
import hashlib
import json
import subprocess
import sys
import threading
from urllib.request import Request, urlopen

import webview

LOCAL_PORT = 18765
APP_VERSION = "1.2.22"
UPDATE_MANIFEST_URL = (
    "https://raw.githubusercontent.com/"
    "dibenedettileonardo2014-dotcom/SIGA-actualizaciones/main/version.json"
)


def bundled_path() -> Path:
    """Return the folder containing bundled web assets in both modes."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def start_server(web_root: Path) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(web_root))
    # A fixed port keeps the browser origin stable, so localStorage survives
    # across launches and can be used as an offline backup.
    server = ThreadingHTTPServer(("127.0.0.1", LOCAL_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def version_key(value: str) -> tuple[int, ...]:
    """Compare dotted numeric versions without requiring an extra package."""
    return tuple(int(part) for part in value.strip().split("."))


def fetch_update_manifest() -> dict | None:
    try:
        request = Request(
            f"{UPDATE_MANIFEST_URL}?installed={APP_VERSION}",
            headers={"User-Agent": f"SIGA/{APP_VERSION}"},
        )
        with urlopen(request, timeout=5) as response:
            manifest = json.load(response)
        required = {"version", "url", "sha256"}
        if not required.issubset(manifest) or not isinstance(manifest["version"], str):
            return None
        return manifest
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def install_update(manifest: dict) -> bool:
    """Download a verified package and schedule its installation after exit."""
    executable = Path(sys.executable)
    update_package = executable.with_name(f"{executable.stem}.update.zip")
    legacy_replacement = executable.with_name(f"{executable.stem}.update.exe")
    try:
        package_url = manifest.get("packageUrl")
        package_hash = manifest.get("packageSha256")
        is_package_update = isinstance(package_url, str) and isinstance(package_hash, str)
        download_url = package_url if is_package_update else manifest["url"]
        expected_hash = package_hash if is_package_update else manifest["sha256"]
        request = Request(download_url, headers={"User-Agent": f"SIGA/{APP_VERSION}"})
        with urlopen(request, timeout=30) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest().lower() != expected_hash.lower():
            raise ValueError("La verificacion de integridad fallo.")
        (update_package if is_package_update else legacy_replacement).write_bytes(payload)
        script = executable.with_name(f"{executable.stem}.update.cmd")
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

    @staticmethod
    def _close_window() -> None:
        if webview.windows:
            webview.windows[0].destroy()


def main() -> None:
    server = start_server(bundled_path())
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
        webview.start(gui="edgechromium")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
