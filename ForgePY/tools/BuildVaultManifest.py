"""Compatibility launcher. Forge package manifest is authoritative."""
from BuildForgeManifest import *  # noqa: F401,F403
from BuildForgeManifest import main
if __name__ == "__main__":
    raise SystemExit(main())
