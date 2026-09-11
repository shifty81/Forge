#!/usr/bin/env python3
"""Compatibility shim. BuildForgePYManifest is authoritative."""
from BuildForgePYManifest import *  # noqa: F401,F403
from BuildForgePYManifest import main
if __name__ == "__main__": raise SystemExit(main())
