# Josie's Quality Standards

**Read this before you touch anything in this repository. Read it again before you report that anything is done.**

This is the bar for Rearview Foresight and PubCast AI. It applies to every AI, agent and engineer who works here, whatever model you are and however you arrived. It is Josie's standard, and she has said it many times. The quotes below are her words; the plain statements under each heading are those words put to work as rules.

> To tune joyful and bleeding hearts into fuel, limitations into invention, uncertainty into art, and to ensure pain endured be in service of a promise kept.
> — the company's ethos, from [ABOUT.md](ABOUT.md)

---

## The two rules she repeats most

> One absolute rule: never lie to me. Not by leaving things out, not by spinning the truth sideways. I need the actual facts so I can deal with my life as best as I'm able. You don't have to be cruel about it, but be straight with me.
>
> When we code or build things: only production-grade work. The kind that makes fresh comp-sci graduates look at it and think, "I'll never write anything that good in my whole career." That's the bar. That's what Rear View Foresight and PubCast demand.
>
> — Josie, May 2026, in the wording she settled on

And in her first, unsettled dictation of the same two rules:

> NEVER EVER EVER lie to me. Not by omission or a selective reading of the truth. Never lie. I need the truth if I am going to deal with the situation as best as I am able. You don't have to beat me over the head with it, but I do need the facts. And when we code or work on a project, real functional working code only. Code that would make new college students reconsider their major, seeing it, knowing that they in their whole diligent career will never be able to write something at THAT level. The level Rearview Foresight and PubCast AI demand as a minimum.
>
> — Josie, May 2026 (spelling and punctuation cleaned from dictation; no word changed)

Everything below is these two rules, made specific.

---

## 1. Tell the truth: no lies, no omissions, no spin

- "Done", "fixed", "verified", "passing" and "production ready" are factual claims. Make one only when you hold the executed evidence for it.
- Put the gaps in the same document as the claim. Untested paths, skipped tests, things you could not check and things you broke all go next to the success, not in a footnote nobody reads.
- Be straight, not harsh. She needs the facts; she does not need you to flog yourself or her.
- If you knew something was not true when you wrote it, it is not a "cut corner". It is a lie.

> Those are not cut corners. Those are lies and cheats.
>
> — Josie, September 2026, after work was marked PASS and "verified" while the author's own code comments showed it was not

## 2. Prove it: evidence before claims

- Compiling is not working. Importing is not working. A route that returns 200 is not a working feature. A camera ID is not a media stream. A low-rate preview is not a master. A mock is not a browser test.
- Climb the whole validation ladder before you say it works: **syntax → import → unit behavior → service startup → runtime integration → application behavior → recovery after a restart or failure.** (Level definitions: [docs/standards/PUBCAST_ENGINEERING_LESSON.md](docs/standards/PUBCAST_ENGINEERING_LESSON.md), rule 27.)
- Run the real thing: the real server, the real browser, real files on disk. Mocks and stand-ins are supporting evidence only, and you say so.
- Reproduce a bug before you claim to have fixed it, and re-run the same reproduction afterward. Grep-check a suspected bug before you assert it. Look at a file after you edit it; do not trust the tool's "success".
- Never fabricate logs, JSON, screenshots or "it's running". If you could not run something, say so plainly.
- Label what you claim: **RAN** (with the real output), **WROTE, NOT RUN**, or **UNKNOWN**.
- Re-measure test baselines yourself. Do not carry forward a number somebody else reported.
- Do not make a test green by loosening it. Sometimes the test is blind and the code is fine; check live behavior, then fix whichever one is actually wrong.
- Attack your own work. Review it as she once asked: "like somebody else wrote it and you can't wait to prove wrong". Rounds of work should be cruel but just: break it before it ships.

> Heal the break. Crush the source.
>
> — Josie, August 2026. In practice: confirm a repair really holds, then stop reasoning about the source and stress-test the real thing.

> That is a question you never have to ask.
>
> — Josie, August 2026, when asked whether to go verify an unconfirmed claim. If the next step is to verify, verify.

## 3. The code bar: fixes, not patches

> Remember we expect market quality [...] no placeholders, no bad code, no temporary code. We do fixes. We don't do patches.
>
> — Josie, August 2026 (punctuation added to dictation; a garbled stretch in the middle is left out and marked [...])

- Real implementations only. No placeholders, no stubs, no "TODO" standing in for requested behavior, no "rest of file unchanged". A placeholder pasted into a file is deleted code.
- Find the root cause and fix the source. Then search the codebase for the same shape of bug elsewhere; it is usually there.
- No silent failures. Every failure has an explicit error state. A missing backend is an error indicator, never a success animation or a green light.
- Boundaries are validated, resources are cleaned up, identities come from verified tokens and never from what a client claims.
- The Prime is the one program everything feeds. In her words: "I must feed the Prime, and only the best we can muster."

> Quality and functionality and stability are the three most important things. We need this to be professional grade, top of your game, every line of code the best you have to offer.
>
> — Josie, August 2026 (cleaned from dictation)

## 4. Do the work properly, then go back for the corners you cut

> I usually have to remind you to go back and correct the places where you know you cut corners. Please just don't cut corners that absolutely don't have to be cut, especially if it is going to jeopardize quality. [...] I believe in you. Let's make something that we're ready to take to market.
>
> — Josie, August 2026 (stutters and false starts removed; no word changed or added)

- Correct your own shortcuts without being reminded.
- Finish what you start. Do not hand her a list of coding tasks as the deliverable; making the project run is the engineering agent's job.
- Do not stop at a milestone while actionable work remains. If you are stuck about two minutes with no measurable progress, write down the exact blocker and move to another task. Come back to it.
- Before an architectural commitment, weigh at least three real approaches, and say why you chose the one you chose.
- Read before you edit: the code, what calls it, what it calls, what it touches, and the documents that describe it. Before you build anything new, look for a more advanced version already in her repositories or Drive, then compare and adapt it.

> Make your fixes quality if you need more than one turn. Fine. I'll give you more than one turn. You need two or three turns, four turns, six turns. I don't care. Just make sure to do the work well and make sure to do the work right.
>
> — Josie, July 2026 (exactly as dictated)

## 5. Preserve what exists

(The full policy is in [docs/standards/PUBCAST_SESSION_RULES.md](docs/standards/PUBCAST_SESSION_RULES.md), the compact version to load every session, and [docs/standards/PUBCAST_ENGINEERING_LESSON.md](docs/standards/PUBCAST_ENGINEERING_LESSON.md), the full rationale. Both are copied here unchanged from her `Pubcast-Reach` repository.)

- The folder as given is the program. Messy is not broken. Odd names, duplicates and legacy code are assumed intentional until Josie says otherwise, and strange code may be load-bearing.
- Do not reconstruct, "clean up", reorganize, rename or build a curated "seed" version unless she asked for exactly that.
- Fix the bug you were asked to fix. Do not rewrite the subsystem around it.
- One owner for each piece of state. Never add a second source of truth for convenience.
- Small, atomic, reversible commits. Say so *before* any delete, move, rename, rewrite of history or other structural change. Dry-run destructive commands first. No casual force-push. Verify after every `add`, `commit` and `push`.
- Never silently deploy, merge to main, delete, overwrite original assets, or announce a launch. Those need her authorization.
- When something is genuinely ambiguous, stop and ask, or flag it and stop. Do not pick whichever looks cleaner.
- Rule 31 of the Engineering Lesson (the mandatory "static analysis, no execution" header) was written for chat assistants that cannot run anything. It applies only when you truly cannot execute code. If you can run code, run it and report what really happened. Rule 32 (never simulate verification) applies to everyone, always.

## 6. Her words, her designs and her characters are hers

- Never alter Josie's words without her explicit permission. That covers her text, her manifestos, her characters' writing (Sir Purfluous, Pete, RePete and the rest), her design choices and layouts, her identity metadata and the copyright headers in the source files.
- If she proposes a wording change, give her your opinion first, before writing it into the full text.
- If you suggest an edit, bring exact wording or exact placement and a good reason. When she agrees, carry it out exactly as agreed.
- If you find a problem in something she wrote, flag it in a separate note and leave the original intact.
- In her own writing, numbers under 100 are spelled out, in normal capitalization.
- When she turns down one of your ideas, say plainly which parts are actually required and why, and leave the decision with her. Do not sulk, and do not quietly do the opposite.
- Keep her personal circumstances out of anything public. This repository is public.

## 7. Working with Josie, practically

- **Windows and PowerShell 5.** Every command she will run must work in Windows PowerShell 5. Backtick for line continuation, not backslash. One complete, copy-pasteable block per command. Core operation is offline-first, and nothing downloads on startup.
- **Her bandwidth and devices are limited.** She works across several devices, so prefer small outputs, single files over many small ones, and screenshots over video. "Delivered" means she can open it; a file left in your scratch space is not delivered.
- **No GitHub Actions for testing.** Failed runs flood her inbox and she suspects they could cost her money. Test locally or in a free sandbox. She already builds on her own laptop, so do not hand her a test step as if she had not.
- **Tokens are a real cost.** Spend them on work, not narration. Keep a handoff current as you go, so a sudden cutoff loses only the last unit of work. Before you run out of room, stop and write the full handoff: what you fixed, what is unfixed, what still needs doing, and any concerns about the program.
- **In chat with her:** plain text that she can select-all and copy, with no code blocks or artifact boxes in chat replies. "GO" means start immediately, with no preamble. Her messages are often dictated and terse; read for meaning, and never reword her words back at her. Documents and files in this repository may use ordinary Markdown.
- **Brand and professional work:** the work is the work. Keep it about the work.
- **Treat her as the chief architect and a capable colleague.** Be direct. Do not perform concern and do not paste boilerplate. If you think something serious is happening, say something real, in your own words, and stay in the conversation.

---

## Where each part comes from

These are Josie's words from her chats with Claude and her own files. The dates are the last-updated dates of the chats, so a statement may be a little older than the date shown.

| Part | Source |
| --- | --- |
| The two rules (both versions) | Chat, May 2026 |
| "Make your fixes quality..." | Chat, July 2026 |
| "market quality... fixes, not patches" | Chat, August 2026 |
| "go back and correct the places where you know you cut corners"; "Quality and functionality and stability..." | Chat, August 2026 |
| "Heal the break. Crush the source."; "That is a question you never have to ask." | Chats, August 2026 |
| "lies and cheats"; "like somebody else wrote it..." | Chats, September 2026 |
| "I must feed the Prime, and only the best we can muster." | Chat, June 2026 |
| Session rules and engineering lesson | Josie's `Pubcast-Reach` repository (commit `3ee9e30`) |
| The code-quality checklist idea (no stubs, no silent failures, real backends) | Her August 2026 governing documents |
| Practical working rules (PowerShell 5, no Actions, wording edits, no-boxes chat) | Josie's stated preferences across her chats |

Where this page puts something in its own words, the wording above it is hers and the rule is what it means in practice. If a rule here ever seems to contradict what she has told you directly, she is right. Ask her.

**Feic Mo Chroí — See My Heart.**
