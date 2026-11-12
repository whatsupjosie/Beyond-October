# Blackbox storage: researched three-solution test

Date: 2026-11-09. Work branch: `gpt/live-studio-setup-2026-11-09`.

## Recommendation after challenging the initial suggestion

Use lossless Zstandard level 3 in independently recoverable blocks targeting
64 KiB, applied to closed event-log segments. Retain the live append-only BBX1
path, original record hashes, exact message text and offline English decoder.
Keep gzip as a dependency-light fallback. Do not adopt a trained dictionary or
the experimental binary representation as the default yet.

The initial suggestion—compress closed logs—survived, but the test qualified it:
whole-file compression can be denser, smaller independent blocks cost space,
binary representation can beat ordinary compression, and dictionaries are not
automatically a win. Disk space and working RAM are different measurements.

**This is an executed offline experiment and recommendation. No live log was
compressed, pruned, migrated or deleted; no automatic archiver was enabled.**
Keeping both originals and compressed copies does not save net disk space.

## Research: free methods and alternatives

Primary sources consulted on this date:

- [Zstandard format and implementation](https://github.com/meta/zstd) and its
  [BSD license](https://github.com/facebook/zstd/blob/dev/LICENSE): freely usable
  lossless compression. Tested Python binding 0.25.0, Zstd engine 1.5.7.
- [Official seekable-format rationale](https://github.com/meta/zstd/blob/dev/contrib/seekable_format/README.md):
  independent frames allow partial access; smaller frames sacrifice compression
  and increase indexing cost. This motivated testing four block sizes.
- [Dictionary training API](https://python-zstandard.readthedocs.io/en/latest/dictionaries.html):
  training on examples, dictionary identifiers, and persisting dictionary bytes.
  Tested a dictionary trained on a separate generated workload.
- [Shared Brotli, RFC 9841, September 2025](https://www.rfc-editor.org/rfc/rfc9841.html):
  a newer standardized shared-dictionary format. Researched, not benchmarked.
  It does not remove the need to preserve the matching dictionary. Our tested
  dictionary variant uses Zstd, not Brotli.
- [MessagePack format](https://msgpack.org/) and
  [Python implementation license](https://github.com/msgpack/msgpack-python/blob/main/COPYING):
  binary serialization. Tested an original reversible field/column transform
  combined with MessagePack 1.2.4 and Zstd, rather than dropping record details.
- [Open-source SQLite Zstd VFS](https://github.com/mlin/sqlite_zstd_vfs): a creative
  page-compression alternative, Apache-2.0 licensed. Its maintainer cautions that
  it changes fundamental storage behavior and is not associated with SQLite's
  developers. Not selected for this append-only witness experiment.
- [Official SQLite ZIPVFS](https://sqlite.org/com/zipvfs.html): commercial license;
  excluded from the free-only shortlist. Free SQLite is not the same as free
  ZIPVFS. A recently indexed random-access compression paper was also surfaced,
  but its primary source could not be retrieved; no claims from it were used.

No claim is made to have invented a new compression algorithm. The creative
third approach combines established tools with a reversible BBX-specific layout.

## Three solutions actually executed

1. **Gzip level 6:** ordinary exact BBX bytes, independent gzip members.
2. **Zstd:** ordinary exact BBX bytes. Level 3, level 9, and level 9 with a trained
   8,192-byte dictionary were tested as variants of this family.
3. **Reversible columns + MessagePack + Zstd level 9:** group like fields,
   encode repeated constant columns once, store hashes as binary bytes, and
   reconstruct each within-block previous-hash value from the preceding record.
   Each block stores its first previous hash, so recovery does not depend on
   decoding an earlier block. Preserve original payload wire text. Noncanonical
   but valid historical field order falls back to storing exact original bytes.

All use the same experimental indexed wrapper, record-aligned blocks, checksums,
embedded decoding key and metadata. Dictionary archives include their dictionary
inside the wrapper, encoded in base64, so its storage is charged to the result.
This wrapper is not claimed to implement the official Zstd seekable file format.
Its members are ordinary gzip/Zstd frames; it is not a production archive API.

The 8 KiB dictionary was trained on 2,000 generated events with seed 99. Test
workloads used different seeds, avoiding training on test messages. Training took
115.35 ms in the final run; that cost is reported separately from encoding time.

## Corpora and fairness

- Mixed generated chat/system/bot event fixture: 4,096 records, 2,957,460 bytes.
- Entropy-heavy fixture: 1,024 records, 2,687,480 bytes. Random payloads and
  identifiers challenge repetition-dependent gains; the BBX envelope still has
  compressible structure and duplicated scalar/JSON data.
- Small session: 32 generated records, 22,831 bytes.
- Actual program paths with generated content: 80,191 BBX bytes from Hub chat,
  system broadcasts, BotManager turn requests, durable outbox delivery and
  shutdown. The provider reply was deterministic; no live model is claimed.

Generated fixtures use the real adapter, BBX1 encoder and valid hash chains.
No owner conversations, credentials or runtime recordings were used. No raw
ledger fixtures or dictionaries were added to the repository.

Four block targets—16, 64, 256 and 8,192 KiB—times five codec configurations
times four corpora give **80 benchmark cases**. The largest target fits each
fixture in one frame. Every case used three encode/decode repetitions; the
reported time is the median. Full encoding includes the binary transform where
applicable. Timings exclude dictionary training, process startup and fsync.

Archive sizes include the index, checksums, dictionary and code key. They are
not merely codec payload sizes. Compression tests do not remove duplicate JSON
fields from the canonical runtime record or change its hash contract.

## Main result: mixed events, 64 KiB blocks

All values below describe the same 2,957,460-byte source:

| Approach | Archive bytes | Disk reduction | Encode ms | Decode ms | Whole-process peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gzip 6 | 496,889 | 83.199% | 59.346 | 19.972 | 31.45 |
| Zstd 3 | 440,203 | 85.116% | 19.389 | 17.077 | 35.84 |
| Zstd 9 | 440,520 | 85.105% | 56.667 | 14.579 | 35.13 |
| Zstd 9 + trained dictionary | 420,499 | 85.782% | 142.007 | 27.125 | 35.40 |
| Reversible columns + Zstd 9 | 424,541 | 85.645% | 111.521 | 45.811 | 35.10 |

Plain Zstd 3 was about three times as fast to encode as gzip here and produced
a smaller archive, at higher measured process RSS. Level 9 did not improve size
on this particular blocked fixture. Compression levels are not a promise of
monotonically smaller results for every workload.

The dictionary saved about 20 KB beyond plain level 3, but took over seven times
its encoding time. On the 22,831-byte small session, the dictionary archive was
15,898 bytes versus 5,636 with ordinary Zstd 3. Including a dictionary can hurt
small archives substantially. A binary dictionary header could remove its
base64 overhead; it would not erase this small-session disadvantage.

The binary layout saved about 16 KB beyond level 3 at this block size, with
roughly six times the encoding time and a more specialized decoder.

## Challenge: let the smallest archive win

Whole-file binary packing reduced the mixed fixture to **336,569 bytes: 88.620%
smaller**, beating whole-file Zstd 3 at 425,427 bytes (85.615%). This is a real
storage advantage, not dismissed because it lost the default recommendation.

Its measured encoding time was 138.617 ms and peak process RSS 59.08 MiB, versus
19.389 ms and 35.84 MiB for blocked Zstd 3. Full decode was 39.076 ms. The sole
frame also means one damaged compressed frame leaves no other verified frame
to recover from that archive. It is worth retaining as a cold-storage candidate
when density outweighs write cost and independent recovery.

The 64 KiB choice is a starting point, not a universal optimum. On entropy-heavy
data, 256 KiB Zstd 3 blocks were slightly denser; on the mixed fixture they were
larger. A production workload study should revisit the target size.

## Runtime-path check and total storage accounting

The 80,191-byte generated runtime trace became:

| Family at 64 KiB | Archive bytes | Reduction |
| --- | ---: | ---: |
| Gzip | 14,008 | 82.532% |
| Zstd 3 | 13,069 | 83.703% |
| Reversible columns + Zstd 9 | 12,211 | 84.773% |

These percentages apply to BBX event bytes, not the entire program. The isolated
fixture directory also had canonical chat, SQLite delivery receipts, turn-request
storage and small configuration files: 153,100 logical bytes total. Replacing
only its BBX with the 13,069-byte archive would project 85,978 logical bytes,
about 43.8% total reduction. No replacement actually occurred. This is not a
projection of a real user's daily storage, and filesystem allocation differs.

An incompressible control confirms the limit: 1,048,576 seeded pseudorandom bytes
grew to 1,048,914 with gzip and 1,048,613 with Zstd. Event-log results cannot be
assumed for already-compressed audio/video or arbitrary data.

## Accuracy, damage and measurement checks

All 80 benchmark cases restored **byte-identical original BBX** with matching
SHA-256 and valid full event chains. Flipping a middle compressed frame caused
exactly one frame to fail while other independent frames remained decodable.
Truncating the final frame preserved every preceding complete frame. One-frame
archives correctly had zero other frames to salvage. Header loss and power-loss
atomic publication were not tested by this experiment.

Seventeen new codec-contract tests passed, covering exact bytes, unchanged
human-readable report output, corruption isolation, truncation, dictionary
validation and unusual historical field order. The selected combined suite:
**63 passed**, 9.52 seconds, five existing dependency warnings. This includes
replay and five-round regression checks; it is not the entire repository suite.

Initial RAM measurements were rejected: getrusage inherited a pre-exec floor,
and numeric-PID psutil calls did not reliably identify the child in this sandbox.
Final results use `/proc/self` VmHWM plus 1 ms VmRSS samples in fresh child
processes, verified with a separate 64 MiB allocation check. RSS includes Python,
libraries, full inputs/outputs and damage checks, not just codec workspace.
The measured implementation loads whole fixtures; these are not promised memory
budgets for a future streaming archiver. RSS profiling is Linux-specific; other
platforms return unavailable RSS fields rather than guessed values.

## Safe implementation boundary

Before actual disk savings are enabled, implement archive-aware offline review
and chat-replay readers. They currently expect `.bbx` files and recorded ledger
references; merely renaming/compressing those files could break recovery.
Publication must use temporary output, durable flush, exact restoration/hash
verification and atomic metadata publication. Keep the original until that
transaction is verified, then apply an explicitly chosen retention policy.
No source deletion, queue migration or runtime format replacement is part of
this experiment. No merge or deployment was performed.

The tested harness and pinned optional dependencies live under
`tools/experiments/`; they are never imported or installed by PubCast startup.
The machine-readable result file preserves all 80 cases, versions, source hashes,
training cost, memory caveats and the incompressible control for review.
