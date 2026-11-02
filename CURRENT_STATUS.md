# Current GPT work

Updated November 1, 2026, Pacific time.

The offline recovery path now passes a real application run on Linux: shut down,
back up, make the original location unavailable, restore into a new directory,
restart PubCast, sign in, open the saved manuscript and play the preserved
recording. Conversations, workspace files, PubPartner exchanges, layout, progress
and keys are checked too. The focused run passed 49 checks; 17 affected backend
checks passed separately.

A mono WebM export failure found by that run is corrected, with actual mono and
stereo encoding/decoding checks and unchanged source bytes.

**Windows/PowerShell 5 remains unverified.** Browser-only saves, external data
roots, actual devices, long-production recovery and power loss remain separate
open gates. Do not call recovery finished across those boundaries.

Read [the acceptance record](docs/RECOVERY_ACCEPTANCE_2026-11-01.md) and the
[signed master list](https://github.com/whatsupjosie/Beyond-October/issues/1).
Next assigned GPT system: speech-to-text and text-to-speech. Claude owns the
motion/facial/performance-capture work, as reported by the owner.
