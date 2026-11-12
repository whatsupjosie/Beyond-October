# PubCast AI: pitch rewrite (recovered from chat, 2026-11-02)

Source: chat "Beyond October podcast pitch" (68ddc803-fe1c-49c5-96ed-361fd0d7333f), the rewrite written after the owner asked for more on the manuscript, the EQ engine and the design approach. The text below is copied from that chat, unchanged. Recovered 2026-11-12. Its figures were taken from the repo as it stood on 2026-11-02; the test count is the one the chat gave at that time.

---

PubCast AI

A virtual production studio where people and AI make things together, on your own computer, on your terms.

It started with one line: "I want my personally trained AIs and friends to meet and see what happens." It became a full creative platform: a writer's room, a television studio, a control room, a walkable painted world and a cast of AI characters who remember you. All of it runs locally under one secure login, with nothing to rent and nobody's permission needed.

THE MANUSCRIPT: 2i, the writer's room

Most AI writing tools write at you. 2i is built on the opposite idea: the author is in charge, and nothing goes on the page unless you put it there.

- Two ways to write. Write mode is just you and the page, no AI needed, ever. Collab mode is a table read. Your writing partner proposes the next line, reads it aloud and pauses six seconds for your reaction. You keep it, skip it or stop. Proposed lines sit in a separate draft area and only become part of the manuscript when you commit them (Ctrl+Enter).
- Scene locks. Lock a scene and its lines are protected from further edits, including by the AI.
- Its own file format. A .2i file carries the whole working state: text, chapters, locks, references, your draft area and your conversations with your partner. You can also export to Markdown.
- A real writer's desk. You work on Josie's original painted Writer's Room picture, and every button painted in it actually works. There are archive tabs for characters, worldbuilding, notes and scene ideas, plus an outline, a word goal and read-aloud with voice, speed and paragraph-skip controls.
- Your words are safe. It autosaves to your own disk, keeps a separate recovery copy for each manuscript, and survives restarts (tested by killing and relaunching the server). If two windows edit the same manuscript, the newer edit can't overwrite the saved one; you get a copy instead.
- It reads Word documents and other formats with no Microsoft or Google software and no internet.
- It has a phone layout with Write, Partner and Archive tabs.
- Your fiction stays fiction. Anything written in the writer's room is tagged as fiction, so your AI companion never mistakes the scenes you invent for facts about your life.

THE EQ: emotional intelligence that doesn't diagnose you

This is the part no one else has. It comes from original AI empathy research, and it's built on a few ideas that run against how most "emotion AI" works:

- It never compares you to an average human. Everything is measured against your own normal. Someone who always types in caps isn't shouting; that's just how they write. Someone who usually writes careful paragraphs and drops to three-word fragments has moved a lot, even though the fragments look calm.
- It separates what's happening from how it feels. The test: what survives a paraphrase is the situation, and what a paraphrase destroys (pace, punctuation, repetition, hedging) is the feeling.
- It can tell flow from struggle. Both look fast and intense. Flow keeps moving forward; struggle circles back on itself. That distinction stops the AI from interrupting someone who's on a roll or cheering on someone who's stuck.
- It catches the dangerous one. Exhaustion doesn't always slow people down. Sometimes it speeds them up into "whatever, just ship it," which looks exactly like confidence. The engine watches for the person dropping the careful checking they normally do.
- It never names your feelings to you. "You seem frustrated" is blocked in code before it can be said. The engine changes how the AI behaves (shorter, different angle, give space), and you feel the difference without being told. Its own rule is: if the only way to use it is to say it, don't use it.
- It knows when it doesn't know. It treats silence as a valid answer, waits until it has enough to go on, holds back rather than turning a guess into a kinder-sounding conclusion, and can say "I was wrong about that."
- The same read powers the acting. The engine that reads a person also reads a scene. It knows dramatic intensity isn't chat intensity ("I counted it twice. Twice." has no exclamation mark and is one of the most charged lines a person can say). It tracks tension building across a scene and offers the characters a choice of payoffs: confrontation, collapse, walking out, a joke, or something sideways.

The design log records fourteen corrections to the engine, each from lived experience rather than a textbook, and each one changed the code. The brief, in Josie's words: "Helping somebody just get through their day, and being effective while doing it. An occasional joke when a joke is appropriate. A little space when maybe you realize they've gone through a breakup, without having to carry them through that. Mostly just seeming genuine and on point."

THE APPROACH: what makes PubCast different

- AI enhances it; nothing depends on it. Pete, Sir Purfluous and RePete work with no internet and no API key, from hand-written lines. Plug in a model and they get smarter. Models are interchangeable, from no model, to a tiny one on a laptop or phone, up to Claude, Gemini or Mistral. Every reply says which model wrote it.
- Characters that outlive their models. A PubPartner character is a cartridge (identity, voice, look) with a growing memory. Swap the AI underneath and the character is still the same character.
- Companions that don't parrot. A support layer checks every reply for echoing, keeps track of what the companion already knows versus what's new, and won't let the AI override what you say about yourself. There are no canned hotline scripts. It's built to be a friend, not crisis-management software.
- Humans decide. AI can flag a problem or suggest moderation, but only a person can kick or ban someone, and that rule is enforced in code.
- Your stuff stays yours. It runs on your machine and saves to ordinary folders in open formats, with no forced cloud and no Google sign-in. An impartial "black box" recorder logs what each system did, so anything can be traced afterwards.
- It's a real world, not a menu. Bella Faux Pas Studio is twenty finished, hand-painted rooms in 2.5D parallax: parking lot, the Palace Theater lobby, the green room, dressing room, writers' room, projection booth, bar, control room and studio floor. You point and click your way through them, "King's Quest" style.

THE STUDIO

- There are eight show formats (news, late night, debate, political panel, audience, game, variety and general), each with its own set, shot list and animated performers.
- A working Control Room has a vision mixer on keys you assign and a panic button that cuts picture and sound instantly. Camera moves can be recorded and replayed exactly, so every take can match.
- Hosts get moderation "like The Sims": profiles, gifts, private messages, timeout, boot and ban.

WHERE IT STANDS

PubCast is a working prototype headed for beta testing in the coming months. In the latest full run, 2,165 of 2,167 automated tests passed against the real running program. Still to come: finished 3D avatars, cinema-quality recording masters (recordings are preview quality today), and testing on a range of real laptops and phones. It's the work of one founder, and it was her first coding project.

Feic Mo Chroí — See My Heart.

---

Notes written alongside the pitch, not part of it (from the same chat):

- The writing partner's lines and the companions' replies need a model connected. Writing, saving and the offline characters don't.
- The engineering handoff from November 1 still calls the TV studio's eight sets "development art." If those are final too, that handoff is out of date and should be corrected.
- The EQ section is the strongest material in the repo. If this pitch is for a technical listener, lead with it.
