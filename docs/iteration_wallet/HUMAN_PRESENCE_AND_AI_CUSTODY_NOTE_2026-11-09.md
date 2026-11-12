# Iteration Wallet: proving a person is present, and keeping AI outside the yard

Date: 2026-11-09
Written by: Claude (Anthropic), from a conversation with Josie on 2026-11-09 and from the frozen 2.5.0a11 code.
Status: design note. It changes no code. It records reasoning so that no future session, human or AI, has to re-argue it from the start.

Most of the earlier thinking behind this happened over roughly a year of conversations, mostly on ChatGPT, which Claude cannot see. Only what reached the code and these notes survives. That loss is part of why this note exists.

## 1. What the Wallet is for

The Wallet exists because work was lost to GitHub. Its main job is strict protection against accidental deletion, aimed first at overenthusiastic AI and only second at people with bad intent.

Josie's picture of it: Iteration Wallet is the house, the vault is the nursery, and Oubliette is the white picket fence. Oubliette was meant as two-way isolation, a moat around the files with one single drawbridge in or out that AIs cannot operate.

The existing Product Laws (PRODUCT_LAWS.md) already state the core of this: No Delete, Humans Open Gates, AI Stays Outside The Yard. This note explains which mechanisms can actually enforce those laws against a modern AI, and which cannot.

## 2. The question that kept breaking: how do you prove a person is acting?

Each earlier answer worked for a while and then stopped working as AI improved, sometimes within weeks. Every one that failed shares one flaw: it is a test of thinking, or a signal that software can produce.

| Attempt | Why it fails against AI |
|---|---|
| Type a ceremony word such as "open" | A test of thinking. Stops accidental clicks, but an AI told to push through can type it. |
| Detect a physical keyboard press | A keyboard only reports "this key was pressed", and software can send the same report. Windows flags keystrokes injected by ordinary programs, so the simple fakes are caught, but a virtual keyboard driver or a cheap USB device that pretends to be a keyboard produces presses that look fully real. |
| A rotating code (an authenticator app's six digits) | To check the code, the computer must store the same secret the phone uses to make it. An AI that can read the computer's files can read that secret and make valid codes itself. |
| A password checked by the computer | The computer must store something to check it against. Anything the computer can check, something on the computer can find. |
| A typed PIN for a platform login | Still typed. An AI that can drive the screen could, in principle, type it. |

The line that holds is not "prove you are human". It is "prove a person is physically present with an approved device", and do it so that nothing secret is stored on the computer.

## 3. What holds: a signed answer from a pre-approved device, after a physical act

This is the passkey scheme (WebAuthn / FIDO2):

1. A device is pre-approved once: a hardware security key, or a phone.
2. For each protected action, the computer sends the device a fresh random challenge.
3. The device signs that challenge with a secret that never leaves the device, and only after a physical act on the device itself: a tap on the key, or a fingerprint or face check on the phone.
4. The computer checks the signature with the public half of the key, which can check signatures but cannot make them.

Why each failure above is closed:

- **Nothing to steal on the computer.** Only the public half is stored there. An AI that reads every file still cannot sign.
- **Faking the signal gets nothing.** The touch is wired inside the key and never passes through the computer as a report. A fake cannot produce the signature.
- **Replaying fails.** Every challenge is new, so an old answer is useless.
- **It does not erode as AI gets smarter.** It is a physical act plus mathematics, not a test of thinking.

What it proves, honestly: that someone holding the approved device acted on it just now. Not who they are. Keep the main key on a keychain and a second one hidden as a backup. The Wallet already supports several active keys, and revoking a lost one without erasing its history.

Device choice:

- **Hardware security key (USB or tap-to-phone NFC).** Preferred. Needs no internet.
- **Phone as the key.** Works. Bluetooth proves the phone is physically near the laptop, but the signed answer passes through an online relay service, so both devices need a connection for a moment. Less dependable on limited bandwidth.

Keep the ceremony word as a statement of intent; the physical touch is the proof.

## 4. The wall that no software on one computer can build

Software on a computer cannot protect itself from something else on that same computer that has the same or greater power. Whoever runs with full administrator rights can take ownership of any file and delete it. That includes an AI started from an administrator window. Safe mode is one route to that power, and there are others.

This is not a gap that someone else has closed and the Wallet missed. The standard answer to ransomware, which is the same problem with a hostile attacker, is still a copy that is not connected.

Two consequences:

- **The moat goes around the AI, not around the files.** Oubliette as it was actually built (see OUBLIETTE_MVP_BOUNDARY_20260628.md and iteration_wallet/oubliette.py in 2.5.0a11) is an inbound quarantine: it inspects arriving files, labels risk, refuses to run or delete them, and records everything. That guards against bad things arriving. But the AI was never at the gate. It was living inside the house, running as Josie. Isolation works when the AI runs as a separate, limited Windows user that is not an administrator. That account cannot take ownership of the vault, and it cannot raise its own power without someone typing the administrator password. AI coding tools also have their own sandbox settings that keep writes inside one project folder, a smaller moat built into the tool.
- **One copy must live where nothing on the computer can reach it.** A USB stick with a physical write-protect switch, a write-once disc, or a drive that is unplugged and put away. This is what the planned sealed portable vault file (.iwvault) is for.

Not a guarantee. Any AI run as Josie's own account bypasses the moat, and Windows itself can have holes. But this arrangement fails only through mistakes or rare flaws, not by design.

## 5. The Wallet's job in this arrangement

Windows provides the walls. The Wallet's job is to put them in the right places and run the only gate:

1. **Build the moat.** Create the limited AI account, place the vault where that account cannot reach it, and launch AI tools inside it, so no one has to set Windows permissions by hand.
2. **Run the one drawbridge.** LabCopy already does this: copies go out to the AI's side, only Candidates come back, and crossing requires the physical touch.
3. **Keep the house.** Every admitted version kept, nothing deleted, a person crowns the Prime, every crossing recorded by BlackBox.
4. **Export the nursery offline.** A sealed vault file that can be carried on a locked stick and opened on another machine with the key.

BlackBox is a witness after the fact. It proves what happened and in what order. It does not prevent anything, and should never be described as if it did.

## 6. State of the frozen build

Package: Frozen_Iteration_Wallet_Pre-Beta_Snapshot_v2.5.0a11_2026-07-28_12-45-49_PDT.zip, in the 6.0- repository and in the whatsupjosie Drive. The two copies are byte-identical (git blob 12e234aeead49ee9fd00982f48029d10eed07c48).

Verified by Claude on 2026-11-09, on current library versions: Wallet suite 330 passed, BlackBox suite 43 passed, release verifier 27 of 27, server starts on port 7432 and its page loads.

Already present: WebAuthn passkey enrollment and server-side signature checking (platform passkeys, phone passkeys where supported, FIDO2 security keys); several active keys; history-preserving revocation; passkey required before protected operations; ceremony words; LabCopy; no-delete custody; BlackBox.

Not done, in the order this note's purpose ranks them:

1. Vault files live inside the unzipped program folder, where AIs working on code are likely to be. Move them.
2. The limited AI account and its Windows permissions are designed but not installed.
3. The sealed portable vault file (.iwvault) is designed but not built.
4. Physical tests on a real hardware key, Windows Hello and a phone have never been run.
5. First-key enrollment is not bound to a separate setup secret, so whoever reaches the machine first can enroll.
6. Lower priority for this purpose (about outside attackers): replacing the self-claimed identity session, manufacturer attestation, independent penetration testing.

Known integration break, found 2026-11-09: Beyond-October's Foresight Counter opens the Wallet in a tray frame that grants only clipboard access. Browsers block passkey use inside a frame unless the frame grants it, so inside the tray every protected action fails. Adding publickey-credentials-get and publickey-credentials-create to the frame's allow list fixes it. This was checked in Chrome both ways. Not yet applied.

The copy of the Wallet inside Beyond-October is the older 2.1 standalone version from 2026-06-27 (11 files, about 1,570 lines). The frozen 2.5.0a11 build is far further along (28 modules, about 19,660 lines, 330 tests). Beyond-October's Foresight Counter already expects the frozen build: port 7432 and START_ITERATION_WALLET.ps1, which only the frozen build has.

## 7. For any future session

- Do not propose typed confirmations, keyboard detection, rotating codes or stored passwords as proof of a person. Section 2 says why.
- Do not describe any same-machine software as making the vault undeletable. Section 4 says why.
- Do not describe BlackBox as preventing anything.
- The Wallet's value is real without any of those claims: kept versions, a person-controlled gate, a recorded history, and an offline copy.
