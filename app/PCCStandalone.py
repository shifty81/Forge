"""Legacy PCC compatibility entrypoint. VaultStandalone is authoritative."""
from VaultStandalone import *  # noqa: F401,F403
from VaultStandalone import main
if __name__ == "__main__":
    raise SystemExit(main())
