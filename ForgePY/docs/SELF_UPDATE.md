# Vault self-update contract

Vault-targeted patch transports use the same `vault.patch.v1` transaction engine used for arbitrary projects. The running Python/Tk process never assumes that replacing files means the new code is loaded: a successful self-update writes `<Vault Library>/updates/restart-required.json`, and the GUI offers an explicit restart.

Supported intake surfaces are configured Downloads folders, the active project root and the Vault application root. The root copy is only removed after a hash-identical Vault copy has been written successfully.

The universal engine validates safe relative paths, payload SHA-256/byte count, optional preimage SHA-256, and delete existence policy. Recovery preimages and transaction evidence are stored outside the source tree under the Vault Library. A failed operation rolls written targets back before returning failure.

The legacy 0.10.2 PCC cannot perform this update because it predates the updater. Use the F11-F20 bootstrap overlay once; subsequent updates can use normal Vault transports.
