"""Compatibility shim. ForgeConsole is authoritative."""
from ForgeConsole import *  # noqa: F401,F403
from ForgeConsole import main
if __name__ == "__main__":
    raise SystemExit(main())
