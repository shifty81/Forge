"""Legacy Cortex PCC GUI compatibility shim. VaultGui is authoritative."""
from VaultGui import *  # noqa: F401,F403
from VaultGui import VaultGui, GUI_VERSION, build_parser, main
CortexPCCGui = VaultGui
if __name__ == "__main__":
    raise SystemExit(main())
