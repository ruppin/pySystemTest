# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import certifi
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

# Get SSL DLLs
binaries = []
for dll in collect_dynamic_libs('openssl'):
    binaries.append(dll)

# Get certifi's SSL cert path
cert_path = os.path.join(certifi.__path__[0], 'cacert.pem')

block_cipher = None

a = Analysis(
    ['src\\__main__.py'],
    pathex=['src'],
    binaries=binaries,  # Add OpenSSL DLLs
    datas=[
        (cert_path, '.'),  # Include certifi's SSL certificate
        ('src/*.py', '.'),  # This now includes ssl_hook.py from src directory
        ('config/cacert.pem', 'config'),  # Include your local cacert.pem
    ],
    hiddenimports=[
        'yaml',
        'jsonpath_ng',
        'jinja2',
        'requests',
        '_ssl',
        'ssl',
        'cryptography',
        'certifi'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['src/ssl_hook.py'],  # Updated path to ssl_hook.py
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