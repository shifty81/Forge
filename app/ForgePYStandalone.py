#!/usr/bin/env python3
"""Canonical ForgePY standalone entrypoint."""
from ForgeStandalone import *  # noqa: F401,F403
from ForgeStandalone import main

if __name__ == "__main__":
    raise SystemExit(main())
