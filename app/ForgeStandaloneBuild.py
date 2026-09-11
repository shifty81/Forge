#!/usr/bin/env python3
from __future__ import annotations
import shutil,sys
from pathlib import Path
from typing import Any
from ForgeVaultBootstrap import layout

BUILD_VERSION='FORGEPY-STANDALONE-BUILD-2.0'
def preflight(root:Path)->dict[str,Any]:
    icon=root/'assets'/'branding'/'ForgePY.ico'; nuitka=shutil.which('nuitka')
    cache=layout()['state']/'nuitka-cache'
    return {'root':str(root),'python':sys.executable,'nuitka':nuitka or '','nuitkaAvailable':bool(nuitka),
            'icon':str(icon),'iconExists':icon.is_file(),'cache':str(cache),
            'readyForWindowsBuild':sys.platform.startswith('win') and bool(nuitka) and icon.is_file()}
def command(root:Path)->list[str]:
    info=preflight(root); entry=root/'app'/'ForgePYStandalone.py'; icon=root/'assets'/'branding'/'ForgePY.ico'
    return [sys.executable,'-m','nuitka','--onefile','--standalone','--enable-plugin=tk-inter',
            '--windows-console-mode=disable',f'--windows-icon-from-ico={icon}',
            '--company-name=ForgePY','--product-name=ForgePY','--file-description=ForgePY Universal Project Operations',
            '--output-filename=ForgePY.exe',f'--output-dir={root/"dist"}',str(entry)]
