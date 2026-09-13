# Vault Patch Verification V2

## Classification

Vault separates transport trust from payload validity.

- `MODERN-BOUND`: v2 package with package-time evidence and target build/source binding.
- `MODERN-UNBOUND`: v2-shaped package missing required binding; rejected under strict policy.
- `LEGACY-BOUND`: older package with usable target preconditions.
- `LEGACY-UNBOUND`: older package without build/source binding; global discoveries go to Review by default.

## Intake sequence

1. Wait for the source file to become stable.
2. Reject temporary browser/download file extensions.
3. Validate ZIP central directory and safety budgets.
4. Reject traversal, absolute paths, symlinks and special file types.
5. Locate and parse the patch manifest.
6. Validate project and patch identity.
7. Parse package timestamp and compare it with archive-member timestamp evidence.
8. Validate file-count, single-file and aggregate uncompressed-size budgets.
9. Copy to quarantine and verify destination SHA-256 equals source SHA-256.
10. Classify modern/legacy and build-bound/unbound status.
11. Resolve the target project unambiguously.
12. Queue or route to per-project Review according to policy.

## Apply-time sequence

1. Capture current target identity: project version/build, Git commit/branch, GREEN identity/commit and available build attestation.
2. Verify manifest preconditions against the live target.
3. Stage only the validated payload.
4. Verify expected pre-image hashes before overwrites when supplied.
5. Create transaction/recovery evidence.
6. Apply atomically where possible.
7. Verify post-image hashes.
8. Build/test/gate according to package policy.
9. PASS: archive source package and receipts into Artifact Central.
10. FAIL: rollback and retain the package/evidence in failed/review history.

A package date is evidence, not authority by itself. Build/source identity plus cryptographic hashes determine applicability.
