# PubCast Character Voice References

Place 6-second (minimum) voice reference clips here.
File name = character_id used in /api/tts/synthesize.

| File                   | Character            | Notes                          |
|------------------------|----------------------|--------------------------------|
| jeremy.wav             | Jeremy Cricket       | Calm, precise, quiet authority |
| pete.wav               | Pete                 | Warm, engaging, technical      |
| sir_purfluous.wav      | Sir Purfluous        | Elderly, elegant, theatrical   |
| sheila.wav             | Sheila               | Empathetic, warm               |
| manny.wav              | Manny                | Neutral studio voice           |
| josie.wav              | Josie (you)          | Host voice                     |
| default.wav            | Fallback             | Used when no match found       |

## Recording tips
- Quiet room, minimal reverb
- Consistent microphone distance
- Natural speech — not performed
- At least 6 seconds, 10+ is better
- 16kHz or 44kHz WAV, mono or stereo both fine
- XTTS-v2 handles the rest

## No voice file yet?
XTTS-v2 falls back to pyttsx3 (CPU, no cloning).
The route still works — just sounds generic until you add the file.
