# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['elatec_uid_tool', 'elatec_uid_tool.analyzer', 'elatec_uid_tool.encodings', 'elatec_uid_tool.fw_export', 'elatec_uid_tool.ports', 'elatec_uid_tool.protocol', 'elatec_uid_tool.tagtypes', 'elatec_uid_tool.firmware', 'services', 'settings_store', 'app_paths', 'serial', 'serial.tools.list_ports', 'webview']
tmp_ret = collect_all('nicegui')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('clr_loader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pythonnet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['gui/app.py'],
    pathex=['src', 'gui'],
    binaries=binaries,
    datas=datas + [('gui/assets/icon.ico', 'assets'), ('gui/assets/icon.png', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='elaUIDtool',
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
    icon=['gui\\assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='elaUIDtool',
)
