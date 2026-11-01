# PubCast BlackBox Event Language Spec

Status: Draft 0.1
Purpose: define the non-English primary record language for PubCast's impartial flight recorder.

## Core Rule

BlackBox records coded facts, not English explanations.

English is a decoded report layer. It is not the permanent primary record.

```text
primary record -> coded event language
program key    -> codebook/schema
report         -> optional decoded English
analysis       -> optional later inference, clearly separated
```

## Design Goals

- Fast enough for live broadcast and AI/runtime telemetry.
- Small enough to write constantly.
- Neutral: no guesses, motives, feelings, or inferred cause.
- Append-only: records are added, never edited in place.
- Tamper-evident: each record carries the previous record hash and its own hash.
- Access-audited: reading, searching, decoding, or exporting BlackBox data creates a new access record.
- Keyed: PubCast stores the event key/schema needed to decode records.
- Lightweight: steady-state BlackBox work should be budgeted to stay under 3% of program compute.
- Crash-aware: when crash indicators appear, BlackBox enters crash-position mode and records the highest-value known facts before shutdown.

## Record Shape

Canonical wire form:

```text
BBX1|seq=<n>|t=<iso>|ch=<channel>|src=<source>|act=<actor>|ev=<event>|cov=<coverage>|sid=<session>|rid=<record>|ph=<previous_hash>|h=<record_hash>|p=<payload>
```

Fields:

- `BBX1`: BlackBox wire-language version.
- `seq`: monotonic sequence number for the recorder stream.
- `t`: UTC timestamp.
- `ch`: channel code.
- `src`: source system code.
- `act`: actor code, when known.
- `ev`: event code.
- `cov`: coverage code.
- `sid`: session or broadcast id.
- `rid`: unique record id.
- `ph`: previous record hash.
- `h`: hash of this record.
- `p`: compact payload, encoded as canonical key-value data or a payload hash reference.

## Required Key

The in-program BlackBox key maps codes to meanings.

Example:

```json
{
  "version": "BBX1",
  "channels": {
    "AIT": "AI thought or decision trace",
    "CHT": "chat message transcript",
    "BRT": "broadcast output trace",
    "ACT": "AI/tool action trace",
    "APP": "approval or denial trace",
    "ERR": "runtime error trace",
    "REC": "recording pipeline trace",
    "CRS": "crash-position trace",
    "ACC": "BlackBox access trace",
    "LEG": "legal request or disclosure trace",
    "DSC": "disciplinary or conduct review trace",
    "WLT": "iteration wallet trace",
    "PER": "performance budget trace"
  },
  "events": {
    "LKA": "lock acquired",
    "LKR": "lock released",
    "DCP": "decision packet captured",
    "MSG": "chat message persisted",
    "TCR": "tool call requested",
    "TCD": "tool call completed",
    "APR": "approval recorded",
    "DNY": "denial recorded",
    "ERR": "error observed",
    "EXP": "export created",
    "ACS": "BlackBox accessed",
    "CPI": "crash-position initiated",
    "CPS": "crash-position snapshot",
    "BPR": "budget pressure recorded",
    "CND": "conduct event recorded",
    "RVW": "review initiated",
    "RSP": "response action recorded",
    "WLR": "wallet rollover requested",
    "WLA": "wallet rollover approved",
    "WLD": "wallet rollover denied",
    "WLP": "manual wallet package recorded"
  },
  "coverage": {
    "F": "full coverage for declared segment",
    "P": "partial coverage",
    "S": "sampled coverage",
    "U": "unknown coverage"
  }
}
```

## Channel Locks

BlackBox does not observe everything continuously. It rotates and locks onto channels.

Every lock and release is recorded.

```text
BBX1|seq=100|t=2026-06-14T22:01:02.010Z|ch=AIT|src=BBX|act=SYS|ev=LKA|cov=P|sid=s01|rid=r100|ph=...|h=...|p=target:alex,dur_ms:250
BBX1|seq=101|t=2026-06-14T22:01:02.260Z|ch=AIT|src=BBX|act=SYS|ev=LKR|cov=P|sid=s01|rid=r101|ph=...|h=...|p=next:BRT,reason:rotation
```

This prevents false omniscience. The record can prove what was observed and what was only sampled.

## Fact-Only Payload Rule

Payloads may contain:

- observed input
- observed output
- known actor id
- known system id
- explicit approval or denial
- tool requested
- tool completed
- error emitted
- measured values
- record hash or media hash
- declared confidence if a system explicitly emitted it

Payloads must not contain:

- inferred motive
- inferred emotion
- inferred cause
- blame
- legal conclusion
- disciplinary conclusion
- "the AI was confused"
- "the user intended"
- "the AI meant harm"

Bad primary record:

```text
AI was confused because the chair was too small.
```

Good primary record:

```text
BBX1|seq=344|t=2026-06-14T22:05:44.103Z|ch=ACT|src=VPK|act=avatar:minotaur_01|ev=TCR|cov=F|sid=s01|rid=r344|ph=...|h=...|p=tool:chair_adapt,obj:chair_14,avatar_seat_w_in:34,chair_seat_w_in:19
```

Later decoded report:

```text
Known: the Visual Patch Kit requested chair adaptation for chair_14. The avatar seat width measurement was 34 inches. The chair seat width measurement was 19 inches.
```

Later optional analysis:

```text
Inference: the failed seating alignment was likely caused by chair/avatar size mismatch.
```

## Access Records

Every access creates a record.

```text
BBX1|seq=901|t=2026-06-14T23:00:00.000Z|ch=ACC|src=BBX|act=user:owner|ev=ACS|cov=F|sid=s01|rid=r901|ph=...|h=...|p=access:view,scope:session_s01,reason:self_review
```

Exports are also records.

```text
BBX1|seq=944|t=2026-06-14T23:09:12.000Z|ch=LEG|src=BBX|act=admin:ops_02|ev=EXP|cov=F|sid=s01|rid=r944|ph=...|h=...|p=scope:segment_200_260,export_hash:abc123,authority_ref:req_77
```

## Disciplinary / Conduct Review

BlackBox is part of the disciplinary log for AI behavior during a shoot.

It records:

- what was emitted or done,
- by which AI/system,
- where it appeared,
- who or what observed it,
- containment actions,
- review access,
- final response actions.

It does not decide motive, guilt, punishment, or intent.

Example coded record:

```text
BBX1|seq=2100|t=2026-06-14T23:40:00.000Z|ch=DSC|src=BBX|act=ai:agent_07|ev=CND|cov=F|sid=s01|rid=r2100|ph=...|h=...|p=kind:profanity_burst,output_hash:abc123,program_visible:true
BBX1|seq=2101|t=2026-06-14T23:40:01.000Z|ch=DSC|src=JER|act=system:pub_manager|ev=RSP|cov=F|sid=s01|rid=r2101|ph=...|h=...|p=action:mute_agent,agent:agent_07,reason:conduct_policy
BBX1|seq=2102|t=2026-06-14T23:45:00.000Z|ch=DSC|src=BBX|act=admin:owner|ev=RVW|cov=F|sid=s01|rid=r2102|ph=...|h=...|p=scope:seq2100-2101,review_type:conduct
```

Decoded known-record report:

```text
Known: a conduct event was recorded for ai:agent_07. The event was marked as profanity_burst by the observing system. The output was represented by hash abc123. Pub Manager recorded a mute_agent response. Owner later reviewed records 2100-2101.
```

Optional analysis must remain separate.

## Iteration Wallet Rollover

From time to time, BlackBox may ask the user to place long-term logs into an iteration wallet.

Purpose:

- keep live recording tiny,
- preserve long-term continuity,
- avoid silently moving important records,
- make later project iterations easier to reconstruct.

Rules:

- BlackBox may request rollover.
- User approval or denial is recorded.
- Manual user deposit is recorded by package hash/reference.
- Primary BlackBox records remain factual and append-only.
- The wallet can contain long-term packages, but the BlackBox ledger keeps custody events.
- The system cannot place records into the iteration wallet itself.
- BlackBox can only request rollover and record that the user manually performed it.

Example:

```text
BBX1|seq=3000|t=2026-06-14T23:55:00.000Z|ch=WLT|src=BBX|act=SYS|ev=WLR|cov=F|sid=s01|rid=r3000|ph=...|h=...|p=scope:seq0-2999,reason:long_term_rollover
BBX1|seq=3001|t=2026-06-14T23:55:05.000Z|ch=WLT|src=USR|act=user:owner|ev=WLA|cov=F|sid=s01|rid=r3001|ph=...|h=...|p=request:r3000
BBX1|seq=3002|t=2026-06-14T23:55:06.000Z|ch=WLT|src=USR|act=user:owner|ev=WLP|cov=F|sid=s01|rid=r3002|ph=...|h=...|p=wallet:iteration_2026_06_14,package_hash:def456,scope:seq0-2999,method:manual
```

## Performance Budget

BlackBox is designed as a tiny witness layer, not a heavyweight analytics engine.

Rules:

- Prefer short codes over English.
- Prefer payload hashes/references for large data.
- Prefer sampled channel locks unless a priority event requires focus.
- Avoid synchronous work on broadcast-critical paths.
- Track recorder overhead through budget records and runtime telemetry.

Target:

```text
steady_state_compute_overhead <= 3%
```

If the recorder would exceed budget, it should degrade gracefully:

1. keep mandatory access/legal/approval/error records,
2. reduce low-priority channel sampling,
3. store payload hashes instead of full payloads,
4. emit a budget-pressure record.

## Crash-Position Mode

At indication of a crash, BlackBox assumes crash-position mode.

Crash indicators may include:

- fatal exception
- repeated unhandled errors
- websocket/server shutdown signal
- recording pipeline failure
- out-of-memory warning
- frame loop stall beyond threshold
- explicit system panic event

Crash-position mode records as much high-value known information as possible before shutdown, without trying to infer cause.

Priority order:

1. current sequence/hash state
2. active session/broadcast id
3. current program camera/source
4. active recording state and output file/hash if known
5. recent error codes and exception names
6. active AI/tool request ids
7. active approval prompts and approval states
8. active avatar/object interaction ids
9. current channel lock and coverage state
10. final flush status

Example:

```text
BBX1|seq=1201|t=2026-06-14T23:20:00.100Z|ch=CRS|src=BBX|act=SYS|ev=CPI|cov=F|sid=s01|rid=r1201|ph=...|h=...|p=signal:fatal_exception,last_seq:1200
BBX1|seq=1202|t=2026-06-14T23:20:00.120Z|ch=CRS|src=BBX|act=SYS|ev=CPS|cov=P|sid=s01|rid=r1202|ph=...|h=...|p=program:cam_a,rec:active,err:RuntimeError,tool:visual_patch_77
```

## Relationship To PubCast Runtime

BlackBox is a witness, not an authority.

It can subscribe to:

- runtime/spine event bus
- performer state changes
- station activation/deactivation
- camera/program role changes
- recording pipeline events
- AI decision/action packets
- approval prompts
- visual patch/object adaptation events
- errors and recovery events

It should not:

- mutate performer state
- approve actions
- deny actions
- modify media
- decide legal compliance
- rewrite records

## Minimum Implementation Pieces

1. `blackbox_event_language/schema.py`
   - code tables
   - record field definitions
   - validation rules

2. `blackbox_recorder/append_only_recorder.py`
   - sequence counter
   - hash chain
   - append-only write
   - access logging

3. `blackbox_decoder/offline_decoder.py`
   - reads records and key
   - produces Known Record reports
   - keeps analysis separate
   - records partial/sampled coverage as an open question, not a guessed conclusion

4. `blackbox_verifier.py`
   - verifies sequence continuity
   - verifies hash chain
   - verifies required access records

5. `BLACKBOX_EVENT_LANGUAGE_KEY.json`
   - in-program decoder key/codebook

## Completion Criteria

- A coded record can be created without English.
- The record can be decoded by the in-program key.
- A hash chain can detect alteration or removal.
- Access to the record creates an access event.
- Reports separate Known Record from Derived Analysis.
- BlackBox can record partial/sampled coverage honestly.
