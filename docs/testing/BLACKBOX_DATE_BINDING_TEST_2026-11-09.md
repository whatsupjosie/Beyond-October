# Creation date and password binding — real hypothetical tests

Date: 2026-11-09. Work branch: `gpt/live-studio-setup-2026-11-09`.

## Result

The proposed date/password binding works as tamper detection on an existing
encrypted file: changing its embedded creation timestamp makes unlocking fail.
Clearing or removing that field is rejected. The correct password and date
restore exact original bytes and the original BBX hash chain.

**It does not make the date permanently unchangeable.** A person who knows the
password can decrypt and re-encrypt the contents with a different asserted date.
That replacement unlocked successfully in the actual test. A separately trusted
signing key blocked a replacement signed by a different key, even with the same
correct password. This is a key-management boundary, not an extra password rule.

## What actually ran

Real cryptographic library calls, with no mock encryption, keys, signatures or
KDF. Cryptography 48.0.1 and Zstandard 0.25.0 were installed in the test runtime.

- Argon2id derives a 256-bit key from a length-delimited encoding of the password,
  creation timestamp and experiment domain, with a random 16-byte salt.
- Parameters: three passes, four lanes, 65,536 KiB memory (64 MiB). These match
  RFC 9106's second recommended profile. This is a test configuration, not a
  measured phone performance guarantee.
- AES-256-GCM encrypts the Zstd-compressed fixture with a random 12-byte nonce.
  The complete header—including date, file identity and format parameters—is
  authenticated as additional data.
- The signed variant uses Ed25519 over the header and ciphertext. Its trusted
  public key is supplied independently, not accepted from the file being tested.
  Signing keys existed only in test memory and were not committed or exported.
- The generated 45,801-byte BBX fixture restored exactly, including its chain.
  The unsigned encrypted/compressed envelope was 7,372 bytes. This is one small
  generated fixture, not a representative performance or storage benchmark.

The embedded date stays readable without the password. Including a public date
in key derivation binds it to this file but does not add secret entropy to the
password. Authenticating the header already provides important date binding;
adding the date to the KDF does not prevent authorized re-encryption.

## Executed scenarios

The standalone study ran **17 scenarios**, all satisfying their assertions:

| Actual operation | Observed result |
| --- | --- |
| Unlock using `A` | Exact plaintext and valid original chain restored. |
| Unlock using `cat` | Exact plaintext and valid original chain restored. |
| Unlock using Unicode, spaces and punctuation | Exact plaintext and valid original chain restored. |
| Edit embedded creation date, retaining ciphertext | `InvalidTag`; no plaintext accepted. |
| Clear the creation date | Explicit format rejection. |
| Remove the creation field entirely | Explicit format rejection. |
| Supply wrong password | `InvalidTag`. |
| Flip ciphertext bytes | `InvalidTag`. |
| Truncate ciphertext | `InvalidTag`. |
| Copy to another filename and change filesystem timestamps | Unlock succeeds; embedded original date remains unchanged. |
| Derive using the same password/salt but two dates | Different keys produced. |
| Decrypt with known password and reseal with a newer date | Replacement unlocks successfully: unsigned date can be reasserted. |
| Verify signed date without password | Original date verified using independent trusted public key. |
| Edit date on signed archive | `InvalidSignature`. |
| Reseal/sign using a different signing key | Rejected against the original trusted public key. |
| Attempt unsigned downgrade when signature is required | Explicit rejection. |
| Sign an intentionally incorrect creation date | Signature validates that assertion: it cannot prove the clock was correct. |

Fifteen cryptographic pytest cases additionally check arbitrary nonempty
passwords, authenticated metadata edits, malformed/impossible dates, missing
creation field and the independent-signature boundary. The combined selection
with storage-format and existing BBX language tests: **42 passed**, 4.00 seconds,
one existing dependency deprecation warning. Counts overlap the scenario study;
they must not be added as independent security coverage.

Individual observed round-trip unlock calls were approximately 107–136 ms in
the final study. These are illustrative single observations on this Linux test
environment, not latency commitments or an Android benchmark.

## What the result means for the proposed retention policy

Password binding alone detects editing of an existing ciphertext, but does not
stop a password holder from manufacturing a valid replacement with a new date.
A signature can separate permission to read from permission to issue a trusted
creation stamp, provided the original signing authority remains protected.
Possession of that signing key—or control over the public-key trust store—can
defeat that distinction. Signing an inaccurate clock reading still authenticates
an inaccurate assertion; genuine time provenance needs its own trusted source.

A public-key signature lets an archive manager verify dates without prompting
for the decryption password. No six-month deletion or 5 GB quota was configured
or exercised. No data was deleted and no owner password was used or changed.

## Strict scope and limits

The prototype is under `tools/experiments/` and is not imported by PubCast.
It is an executed hypothesis, not a production encryption format or a complete
security audit. It does not establish resistance to every attack or change
current account authentication.

This prototype authenticates one entire compressed payload. One damaged byte
therefore rejects the entire envelope, as tested. A production design must use
appropriate independent block authentication and an authenticated manifest to
preserve the earlier compression study's partial-recovery properties. This
single-envelope prototype must not simply replace the segmented archive format.

No production key storage, signing authority, password-reset/recovery procedure,
archive migration, reader integration or atomic encrypted-file publication is
implemented here. No real Android hardware, physical disk failure or trusted
time service was tested. Source fixtures and encrypted example files stayed in
isolated scratch storage; only code, test assertions and measurements are saved
in the repository. No merge or deployment.

## Primary references

- [Cryptography Argon2id documentation](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/)
- [RFC 9106 parameters](https://www.rfc-editor.org/rfc/rfc9106.html)
- [Authenticated encryption and associated data](https://cryptography.io/en/latest/hazmat/primitives/aead/)
- [Ed25519 signature verification](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)

The measured cases and timings are in
`blackbox-date-binding-results-2026-11-09.json`; the optional test dependencies
are pinned in `tools/experiments/requirements-blackbox-date-binding.txt`.
