"""Public Responses API transport. Callers commit only after normal completion."""
import asyncio
import json
import httpx
from .openai_compatible_provider import ModelResponseError, OpenAICompatibleBotAdapter


async def responses_text(key, prompt, *, system='', history=None, model='', timeout=180):
    if not key or not model:
        raise ModelResponseError('OpenAI requires a credential and model')
    messages = OpenAICompatibleBotAdapter.messages(prompt, history=history)
    body = {'model':model, 'input':messages, 'store':False, 'stream':True,
            'max_output_tokens':8192}
    if system:
        body['instructions'] = system
    completed = False
    size = 0
    lines = []
    try:
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                async with client.stream('POST','https://api.openai.com/v1/responses',
                    headers={'Authorization':f'Bearer {key}'},json=body) as response:
                    if response.status_code != 200:
                        raise ModelResponseError(f'OpenAI HTTP {response.status_code}')
                    async for line in response.aiter_lines():
                        size += len(line.encode())
                        if size > 2_000_000:
                            raise ModelResponseError('OpenAI response exceeds size limit')
                        if line.startswith('data:'):
                            lines.append(line[5:].lstrip(' '))
                        elif not line and lines:
                            event = json.loads('\n'.join(lines))
                            lines = []
                            if not isinstance(event, dict):
                                raise ModelResponseError('Invalid OpenAI event')
                            kind = event.get('type')
                            if kind in {'error','response.failed','response.incomplete'}:
                                raise ModelResponseError('OpenAI response failed or is incomplete')
                            if kind == 'response.output_text.delta':
                                if completed or not isinstance(event.get('delta'),str):
                                    raise ModelResponseError('Invalid OpenAI text event')
                                yield event['delta']
                            elif kind == 'response.completed':
                                if event.get('response',{}).get('status') != 'completed':
                                    raise ModelResponseError('Invalid OpenAI completion event')
                                completed = True
                    if not completed or lines:
                        raise ModelResponseError('OpenAI stream ended without complete confirmation')
    except (httpx.HTTPError, TimeoutError, ValueError):
        raise ModelResponseError('OpenAI transport failed or returned invalid data') from None
