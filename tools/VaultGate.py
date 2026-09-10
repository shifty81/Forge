"""Compatibility launcher. ForgeGate is authoritative; Vault is a Forge workspace."""
from ForgeGate import *  # noqa: F401,F403
from ForgeGate import main
if __name__ == "__main__":
    raise SystemExit(main())
