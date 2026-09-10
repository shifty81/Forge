"""Compatibility shim. ForgeGui is the application GUI authority; Vault is a workspace tab."""
from ForgeGui import *  # noqa: F401,F403
from ForgeGui import ForgeGui, GUI_VERSION, build_parser, main
VaultGui = ForgeGui
if __name__ == "__main__":
    raise SystemExit(main())
