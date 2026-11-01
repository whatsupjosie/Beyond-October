# Hosted models: connection and test

Use START_HOSTED_WINDOWS.bat on Windows x64, or `bash start_hosted.sh` on Linux.
Python 3.11+ and a first-time internet dependency install are required. This
starts the authenticated Reach host without loading or requiring the GGUF.
Open PubPartner at http://127.0.0.1:8000/pubpartner and create/sign into your
local owner account. Existing work belongs to its data directory; use
`--data-dir PATH` to select your existing installation deliberately.

In Friend Setup, select OpenAI API, Gemini API or Claude API. Enter an exact
model ID available to your provider account. Save the provider API key in the
password field; it is stored encrypted by the existing per-user credential
store. Select that saved credential. Keep fallback unchecked, then click
Provider Test. Only a successful real provider reply proves that account,
model, billing and network combination works. Never paste keys into a chat.
Gemini requires an explicit model ID; it no longer silently selects Gemini 2.0.
A saved credential uses its saved model; save a new configuration to change it.

## What is implemented

OpenAI uses the public Responses API with storage disabled and validated stream
completion. Claude uses Messages and Gemini uses generateContent; both buffer
the complete response before yielding text. Standard and legacy text history
are preserved. Failed, blocked, malformed, incomplete and token-limited replies
fail instead of becoming successful partial answers. Google credentials are
sent in a header, not a URL. Unknown providers fail explicitly. A missing or
foreign selected credential cannot silently switch to the host credential.

No real hosted account has been connected or tested in this environment.
The tests use simulated provider HTTP responses. Existing source and memory
orchestration still constructs the FCP1 packet sent to hosted providers.

## Chat subscriptions are a separate connection

This build does not implement subscription OAuth sign-in for ChatGPT, Gemini
or Claude. Its API credential boxes must not be described as subscription login.
OpenAI now documents eligible ChatGPT-plan inference via Sign in with ChatGPT;
it requires its own authorized registration, token lifecycle and account model
picker. Open-source partners and selected private clients have distinct
eligibility. This repository carries proprietary copyright notices; this audit
does not change its license or establish eligibility for that flow.

Claude documents separate Console access; qualifying Max/Team plans may include
API credits. Renewing a chat plan alone does not configure this app. The current
Gemini integration uses a Gemini API credential, not Google AI subscription login.
PubCast supplies its own context and memory; none of these API connections
imports your ChatGPT, Gemini or Claude chat history automatically.

Official references checked October 10, 2026:
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-is-claude-api-usage-billed-separately-from-my-paid-claude-plan
- https://ai.google.dev/api/generate-content
