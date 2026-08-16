# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html', '.'),
        ('assets/logo-sindicato.png', 'assets'),
        ('assets/logo-spiqyp-rosario.png', 'assets'),
        ('assets/mantenimiento.png', 'assets'),
        ('assets/convenio-77-89.pdf', 'assets'),
        ('assets/convenio-77-89.txt', 'assets'),
        ('assets/vendor', 'assets/vendor'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'webview.platforms.android',
        'webview.platforms.cef',
        'webview.platforms.cocoa',
        'webview.platforms.gtk',
        'webview.platforms.qt',
    ],
    noarchive=False,
    optimize=2,
)

# Pywebview 6.2 resolves all three WebView2 runtime folders while importing its
# Windows backend. Keep x86, x64 and ARM64 loaders in every desktop package.
import struct
build_arch = 'x64' if struct.calcsize('P') == 8 else 'x86'
other_clr_arch = 'x86' if build_arch == 'x64' else 'amd64'
unused_runtime_files = {
    'pythonnet\\runtime\\Python.Runtime.xml',
    'setuptools\\_vendor\\jaraco\\text\\Lorem ipsum.txt',
    'webview\\lib\\pywebview-android.jar',
    'webview\\lib\\WebBrowserInterop.x64.dll',
    'webview\\lib\\WebBrowserInterop.x86.dll',
    f'clr_loader\\ffi\\dlls\\{other_clr_arch}\\ClrLoader.dll',
}
a.datas = [entry for entry in a.datas if entry[0] not in unused_runtime_files]
a.binaries = [entry for entry in a.binaries if entry[0] not in unused_runtime_files]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SIGA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\siga-app-icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SIGA',
)
