"""Compatibility shim. ForgeStandalone is the application authority."""
from ForgeStandalone import *  # noqa: F401,F403
from ForgeStandalone import main
if __name__ == "__main__":
    raise SystemExit(main())
