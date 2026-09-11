#!/usr/bin/env python3
from __future__ import annotations
MATRIX_VERSION='FORGEPY-CLEAN-PC-MATRIX-1.0'
def scenarios():
    return [
      {'id':'clean-c-no-d','description':'Fresh Windows machine, C: only, no Vault','expected':'first-run chooses local fallback'},
      {'id':'clean-d','description':'Fresh Windows machine with D:','expected':'defaults to D:\\Vault and D:\\Projects'},
      {'id':'existing-vault','description':'Existing D:\\Vault from prior machine','expected':'adopt without moving content'},
      {'id':'offline','description':'No network','expected':'core app starts; external tool installs deferred'},
      {'id':'missing-toolchains','description':'No Git/Rust/CMake/Node','expected':'Toolchain Doctor reports BLOCKED, no crash'},
      {'id':'moved-projects','description':'Registered roots moved','expected':'portable rebind workflow'},
      {'id':'upgrade','description':'Previous ForgePY data and newer executable','expected':'schema migration + startup self-test'},
      {'id':'rollback','description':'New executable self-test fails','expected':'rollback candidate restored'},
    ]
