# PubCast and the Iteration Wallet: how they talk and work together (PARTIAL RECOVERY)

Status of this file: PARTIAL. It was written in the chat "Beyond October repo changes" (f575a100-8d1f-49c5-919e-e936d5a70c91) on 2026-11-09 and sent to the owner as an attachment, PUBCAST_WALLET_COMMUNICATION_DESIGN_2026-11-09.md. That file was created and then edited several times in the chat. The chat transcript does not give the complete text back, so the passages below are only the ones that could be read in full. Every place where text is missing is marked [GAP]. Do not treat this file as the complete design. The complete version is the attachment in the chat, and the owner's copy is the source of truth.

Written by Claude, for Josie to read, question and change. Nothing here is built yet.
Companion note: HUMAN_PRESENCE_AND_AI_CUSTODY_NOTE_2026-11-09.md (why a person's key, not a typed word, opens protected gates). That note is in the repo at docs/iteration_wallet/.

---

## 1. The picture

The Wallet lives next door to PubCast, not inside it. PubCast has the priority entrance: it is the one neighbour with its own door, its own key to that door, and its own drop box. But the door only opens one way on its own. PubCast can always hand things in. Only a person, with their key, can take things out or change what the Wallet holds.

## 2. Ground rules

1. Two programs, two homes. Separate processes, separate data folders. PubCast runs fine with the Wallet closed. The Wallet runs fine with PubCast closed. Neither one starts, stops or depends on the other to work.
2. PubCast can only add. PubCast may hand things to the Wallet. It can never retire, restore, promote, export or change anything already inside. Nothing PubCast says to the Wallet can reduce what the Wallet holds.
3. Decisions happen in the Wallet, by a person. Every decision (crown a Prime, send a copy out, bring something back, retire, restore) is made in the Wallet's own screen, with the person's key. PubCast never holds the Wallet's authority. It never stores a key, a ceremony token or a Wallet login.
4. The Wallet never reaches into PubCast. It does not read PubCast's live data or write into it. Things travel between them only as sealed packages through set drop points.
5. Guests never see the Wallet. PubCast hosts guests and goes online. The Wallet stays on this computer only and answers only this computer. PubCast never passes the Wallet through to guests, and guests never learn it exists.
6. Nothing waits on the Wallet. If the Wallet is closed, locked or busy, PubCast keeps working and holds its packages until the Wallet is back.

## 3. The four conversations

### A. "Are you there?" (presence)

PubCast asks the Wallet, every few seconds while Foresight is open, whether it is running and healthy. The answer is only: running or not, locked or open, healthy or not. PubCast shows it as the Wallet's light on its fan blade. No contents, names or file lists travel in this conversation.

[GAP: remainder of section 3A, if any]

### B. "Please keep this" (hand-in)

PubCast hands the Wallet one sealed package to keep.

1. PubCast seals the package: one file, with its fingerprint (a hash) and a label saying what it is, where it came from, when, and which PubCast version made it.
2. PubCast drops it in its drop box and tells the Wallet it is there.
3. The Wallet copies it in, checks the fingerprint matches, and files it as Raw Source (as-is material) or as a Candidate (a version offered for review).
4. The Wallet answers with a receipt: what it filed, under what ID, with what fingerprint.
5. PubCast keeps the receipt and can show "kept in the Wallet since [date]" beside that item.

If the Wallet is closed, the package waits in the drop box marked "not yet received". PubCast never deletes a package until it holds the Wallet's receipt for it.

### C. "I'd like that back" (hand-out)

1. The request is made in the Wallet's screen, by the person, with the key. PubCast can ask ("restore the version from Tuesday"), but asking only opens the Wallet's screen at that item. It never brings anything out by itself.
2. The Wallet puts a working copy (not the original) in PubCast's pickup box.
3. PubCast picks it up and restores it somewhere new, beside the current work, never over it. The person chooses whether to switch to it.

The Wallet's original stays where it was. Taking a copy out never moves or changes it.

### D. "Who is this?" (pairing)

Today the Wallet accepts a hand-in from any program on this computer. That's safe in one sense: a hand-in can only add, never destroy. But anything could fill the Wallet with junk, and the Wallet couldn't tell PubCast's packages from a stranger's.

Pairing fixes that. Once, the person approves PubCast in the Wallet's screen with the key. The Wallet gives PubCast a sender pass. From then on, PubCast's packages arrive labelled "from PubCast", and anything without the pass arrives labelled "unknown sender" and waits for the person.

The sender pass only proves who is knocking. It opens nothing.

[GAP: the rest of section 3, and any other part of the file between section 3 and section 4, if present]

## 4. What PubCast might hand in

These are possibilities for Josie to choose from. None is decided.

- PubCast's saved work as a whole: the offline host-data checkpoint, which already exists on GPT's branch. It produces exactly one sealed zip and a receipt with its fingerprint, which is the shape the Wallet takes in.
- Finished takes and exports from recording.
- Scripts and manuscripts from 2i.
- Avatar and object blueprints (voxel designs, Filler Cream and Dremel work, custom pieces made once and copied).
- PubPartner cartridges.
- PubCast itself: each AI delivery of the program's own code arrives as a Candidate, and the person crowns the Prime. This is the development use: GPT and Claude hand in, Josie decides.

[GAP: any items after the last bullet above]

## 5. When things get handed in

Also for Josie to decide.

- By hand: a "Keep in Wallet" action on things that can be kept.

[GAP: the rest of section 5. The options in the chat were: by hand, at key moments, on a schedule, or a mix.]

## 6. [GAP: section 6 not recovered]

## 7. [GAP: section 7 not recovered. The chat says it covers how GPT and Claude would work on copies through the Wallet without touching originals, and what happens when things go wrong: Wallet closed, a bad fingerprint, a lost receipt, a compromised PubCast.]

## 8. What already exists to support this

Checked against the frozen 2.5.0a11 code and Beyond-October on 2026-11-09:

- The Wallet runs on this computer only, on port 7432. Its launcher refuses to open it to the network.
- Its health and abilities are already readable (state and capabilities), which is enough for the presence light.
- It already takes in one file at a time as Raw Source or Candidate, copying it in and recording its fingerprint. It doesn't yet record who sent it.
- Sending a working copy out, bringing a result back as a Candidate, and crowning a Prime already require a person's ceremony and session, with the passkey gate.
- Its own screen only answers its own address, so PubCast's web pages can't operate it directly. That fits rule 3: the person works in the Wallet's screen, shown in a Foresight tray.
- PubCast's checkpoint tool (GPT's branch) already makes one sealed zip and a receipt, and it lists the Wallet as outside its scope.
- Foresight already has the Wallet on the counter as its own program on port 7432. The tray needs passkey permission added before the person can use the key inside it.

What doesn't exist yet: the drop box and pickup box, the sender pass and pairing, receipts kept on PubCast's side, the presence light, and PubCast actions such as "Keep in Wallet". (A later version of the chat's text also lists the "Keep this date" feature and the Blackbox archive catalog here.)

PubCast's own work is unaffected.

## 9. Decisions for Josie

1. Which of the section 4 items should PubCast be able to hand in?
2. By hand, at moments, on a schedule, or a mix?
3. Should the Wallet accept hand-ins from unknown senders (labelled and held), or refuse them outright?
4. May PubCast ask for things back (opening the Wallet's screen at that item), or should every hand-out start in the Wallet?
5. Should PubCast show the Wallet's size and warn at a limit you set?
6. Where GPT and this design differ: does each hand-in need a person's approval in the Wallet before it is filed?
   - GPT's review calls for a "human-approved Wallet intake adapter".
   - This design lets a paired PubCast file packages without approval, because filing can only add, and saves the key for anything that takes out or changes.
   - Requiring approval per hand-in is stricter, but nothing automatic can finish without you present, so a "Keep this date" made while you're away would sit at "preservation pending" until you approve it.
   - A middle path: paired PubCast packages file automatically into a holding area marked "unreviewed", and nothing in it can become a Candidate or a Prime without your key.

[GAP: any decisions after item 6]

---

Stated in the chat, not in this file: the owner's earlier design note was still waiting to be committed to claude-work. Claude said it would commit both notes once the owner had answered the decisions. This partial file is not that commit.
