"""Compatibility shim. ForgeSourceControl is the universal source-control authority."""
from ForgeSourceControl import *  # noqa: F401,F403

if __name__ == "__main__":
    from ForgeSourceControl import main
    raise SystemExit(main())
