# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('index.html', '.'),
        ('assets/logo-sindicato.png', 'assets'),
        ('assets/convenio-77-89.pdf', 'assets'),
        ('assets/convenio-77-89.txt', 'assets'),
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

# The desktop build is x64/WebView2-only. PyWebView's generic hook also adds
# Android, x86, ARM64, legacy-MSHTML and documentation files that SIGA cannot
# load on this target.
unused_runtime_files = {
    'pythonnet\\runtime\\Python.Runtime.xml',
    'setuptools\\_vendor\\jaraco\\text\\Lorem ipsum.txt',
    'webview\\lib\\pywebview-android.jar',
    'webview\\lib\\WebBrowserInterop.x64.dll',
    'webview\\lib\\WebBrowserInterop.x86.dll',
    'webview\\lib\\runtimes\\win-arm64\\native\\WebView2Loader.dll',
    'webview\\lib\\runtimes\\win-x86\\native\\WebView2Loader.dll',
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
