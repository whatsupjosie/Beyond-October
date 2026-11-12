# Current GPT work

Updated November 1, 2026, Pacific time.

PC-035 now has real Linux speech acceptance: local English dictation with editable
review and no autosend; CPU neural speech through the existing program mixer;
twenty-eight configurable voices; authenticated limits, stop/cancel and durable
owner choices. The mixer recording was decoded and transcribed back to the actual
spoken sentence. A combined run passed 124 checks plus sixteen supporting subtests;
nine Node test entries and the audio-room policy script passed. Thirteen real
speech/boundary checks passed again after a final language-case correction.

Read [speech scope, installation, evidence and limits](docs/SPEECH_SYSTEM.md).
Native Windows/PowerShell 5, physical microphones, varied/noisy human speech,
SAPI/XTTS and lip sync remain unverified. Final character voice casting is optional
configuration. The implementation is on `gpt-work`; no merge or deployment is
implied. Claude's motion/facial/actor controllers were not edited.

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
Claude owns the motion/facial/performance-capture work, as reported by the owner.
The master list retains the Windows/device gates and separate release acceptance.
