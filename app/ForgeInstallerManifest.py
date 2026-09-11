#!/usr/bin/env python3
from __future__ import annotations
from typing import Any
INSTALLER_VERSION='FORGEPY-INSTALLER-MANIFEST-1.0'
def manifest(version:str,exe_name:str='ForgePY.exe')->dict[str,Any]:
    return {'schema':'forgepy.installer.v1','version':INSTALLER_VERSION,'product':'ForgePY','productVersion':version,'executable':exe_name,'scope':'per-user','shortcuts':['Start Menu','Desktop optional'],'repair':True,'uninstall':True,'preserveMachineData':True,'vaultExternal':True}
