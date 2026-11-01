# 2i editor engine acquisition and qualification

The selected candidate is EigenPal DOCX Editor core 2.32.0, Apache-2.0. Tiptap and Lexical are flexible editor frameworks, but require additional Word-format handling. ONLYOFFICE and SuperDoc have different licensing/integration requirements. The selected engine has a framework-independent core, custom control APIs and a local font-loading path. No account or remote conversion is required for browser editing. Pro review/automation components are not installed.

## What was done

Downloaded the upstream source at fc28dba928b073c2beddc5672cdc7b42ea3af0f9 and pinned npm packages. Built a local browser engine with its font-shaping WASM, stylesheet and open-licensed fonts. Downloaded CMU pronunciations and WordNet 3.1 data. The build contains third-party notices. Compressed dictionary files preserve the downloaded bytes after decompression.

A real Chromium qualification opened a DOCX, replaced text with the engine command API, saved and reopened it. An independent python-docx readback confirmed the test document retained bold, font family, size, paragraph indentation, header, table cells and margin. All external requests were blocked; none were attempted. This is a bounded fixture test, not proof that every Word feature renders identically.

Local data checks passed for 135,155 pronunciation entries, a 5/7/5 English haiku, an unknown word, and a phonetic rhyme. These are component checks; no poetry sidebar or dictionary interface has been added to production 2i yet.

## Integration requirements

- 2i owns document parsing, editing, formatting, file identity, saving, speech controls and writing tools. Counter trays own hosting, placement and appearance only.
- Ordinary TXT, Markdown, XML and scripts retain exact source text. Merely opening a file does not convert it.
- Native manuscript copies use recognisable .2i names. Preserve original bytes and reject filename/revision collisions. A filename alone never substitutes for stable document identity.
- Rich documents need full document state inside native saves, not just extracted paragraph text. Keep unknown OOXML parts and disclose unsupported features and font substitution.
- Add script element styles, optional poetry forms, word/selection counts, adjustable reading-time estimates, actual page numbers, exact phrase/quotation find and undoable replacement.
- Poetry assistance must be optional. Haiku can show 5/7/5 targets without changing the writing. English syllable counts are pronunciation-dependent estimates. Offer alternate pronunciations and manual overrides, identify unknown names/words, and do not claim Japanese mora counting from English syllables.
- Definitions/thesaurus and rhyme lookup should use local data. WordNet is a lexical resource, not a complete modern dictionary. Provide expandable language packs.
- Inspect and reuse modules/stt_engine.py and modules/tts_engine.py. Require locally installed models/voices for offline speech; do not count browser SpeechRecognition as guaranteed offline. Existing runtime dependencies and device tests remain required.
- No paid package, telemetry exporter, Google Fonts resolver or automatic model download belongs in the essential path.

## Reproduce acquisition checks

Install build dependencies with npm ci --ignore-scripts in this folder. Run node build.mjs and node check-language.mjs. Build dependencies are development tools; the bundled browser assets run offline. Use ACQUISITION.json and package-lock.json for pinned provenance. The full upstream source checkout was left unchanged.

The production rich-document integration remains pending. Downloading and qualifying this engine does not convert the existing text-copy importer into a formatting-preserving editor.
