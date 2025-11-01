# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import certifi
from PyInstaller.utils.hooks import collect_all

# Get certifi's SSL cert path
cert_path = os.path.join(certifi.__path__[0], 'cacert.pem')

# Collect all SSL-related packages
ssl_datas = []
ssl_binaries = []
ssl_hiddenimports = []
for pkg in ['certifi', 'cryptography', 'OpenSSL']:
    data, binaries, hiddenimports = collect_all(pkg)
    ssl_datas.extend(data)
    ssl_binaries.extend(binaries)
    ssl_hiddenimports.extend(hiddenimports)

block_cipher = None

a = Analysis(
    ['src\\__main__.py'],
    pathex=['src'],
    binaries=ssl_binaries,  # Add SSL binaries
    datas=[
        (cert_path, '.'),  # Include certifi's SSL certificate
        ('src/*.py', '.'),
        ('config/cacert.pem', 'config'),  # Include your local cacert.pem
        *ssl_datas,  # Add SSL package data
    ],
    hiddenimports=[
        'yaml',
        'jsonpath_ng',
        'jinja2',
        'requests',
        '_ssl',
        'ssl',
        'cryptography',
        'certifi',
        'OpenSSL',
        *ssl_hiddenimports,  # Add SSL package imports
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['ssl_hook.py'],  # Add the SSL runtime hook
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pySystemTest',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)