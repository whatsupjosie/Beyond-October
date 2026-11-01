MODEL SWAP — how PubCast changes AI models

The AI is interchangeable. Which model runs is data in the model registry, not code.

Tiers, smallest first
- offline: no model. Pete, Sir Purfluous and RePete answer from their scripted lines, labelled offline_character.
- tiny_local: phone or laptop model with no internet. SmolLM2 1.7B is the built-in baseline.
- local: a larger model on the same machine (for example a Gemma or Mistral build).
- hosted: a provider over the network (Claude, Gemini, OpenAI, Mistral, Groq). These are chosen in the provider settings, not the launcher.

Prompt profiles
- full: everything in the conversation packet. This is the setting SmolLM2 was validated with.
- compact: for small models. Identity, boundaries, safety, source-custody and Alex guidance are always kept. Memories are cut to 3, history to the last 6 messages, and reference material over 1,500 characters is left out with a note telling the model it did not read it. Every cut is reported with the reply.

Every reply from a local model carries model_alias, model_display_name, model_tier and prompt_profile, so you can always see which model answered.

Adding a local model (run by the launcher)
1. Put the .gguf file in the models folder.
2. Get its checksum in PowerShell:
   Get-FileHash -Algorithm SHA256 .\models\YOUR-FILE.gguf
3. Add an entry to data\model_registry.json under "models". Fields:
   alias (the key; lowercase letters, digits, . _ : -), display_name, runtime "launcher", tier "tiny_local" or "local",
   context_tokens, reply_tokens (16 to 4096, smaller than context), prompt_profile "full" or "compact",
   file (the .gguf file name only), sha256 (from step 2, lowercase), optional temperature (0 to 2) and notes.
4. Start it:
   python run_smollm.py --model YOUR-ALIAS

The launcher refuses a model that is not in the registry, has no checksum, is missing, or whose checksum does not match. The registry file cannot change the built-in SmolLM2 file or checksum; use a new alias instead. Set PUBCAST_MODEL_REGISTRY to use a registry file somewhere else.

What has and has not been verified
- Verified here with stand-in models (tests/test_model_registry.py): registry validation, swapping the launched model, refusing wrong or unverified models, compact trimming, reply labelling.
- Not verified: how well any real model answers. No real model runs in the build sandbox. Use tools/smollm_live_check.py on your own machine for a live check of SmolLM2.
