import asyncio
import json
import httpx
import pytest
from modules.openai_compatible_provider import OpenAICompatibleBotAdapter, ModelResponseError
from modules.smollm_prompt import render_chat
from modules import local_model_config as local


def mock_client(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def event(content=None, finish=None):
    return 'data:' + json.dumps({'choices':[{'delta': {'content':content} if content is not None else {}, 'finish_reason':finish}]}) + '\n\n'


def adapter(**kwargs):
    return OpenAICompatibleBotAdapter(base_url='http://127.0.0.1:8111/v1',api_key='private-key',default_model='smollm2',**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize('body',[
    event('partial'), event('partial')+'data:[DONE]\n\n',
    event('partial')+event(finish='length'),
    event('partial')+'data:{broken}\n\n',
    event('partial')+'data:{"error":{"message":"SECRET"}}\n\n',
    event('partial')+event(finish='tool_calls'),
])
async def test_partial_or_invalid_reply_never_commits(monkeypatch,body):
    mock_client(monkeypatch, lambda req: httpx.Response(200,text=body))
    with pytest.raises(ModelResponseError) as error:
        await adapter().complete('hi')
    assert 'SECRET' not in str(error.value)


@pytest.mark.asyncio
async def test_http_error_does_not_expose_body(monkeypatch):
    mock_client(monkeypatch,lambda req:httpx.Response(401,text='private-key prompt private text'))
    with pytest.raises(ModelResponseError,match='HTTP 401') as e:
        await adapter().complete('hi')
    assert 'private-key' not in str(e.value)


@pytest.mark.asyncio
async def test_exact_history_matches_hashed_wire(monkeypatch):
    t={'fcp1':{'msg':{'text':'  source\n'},'history':[{'role':'user','content':'  quoted\n'}]}}
    prompt,system,history,evidence=render_chat(t)
    seen=[]
    def handle(req):
        seen.append(json.loads(req.content))
        assert req.headers['authorization']=='Bearer private-key'
        return httpx.Response(200,text=event('answer')+event(finish='stop')+'data: [DONE]\n\n')
    mock_client(monkeypatch,handle)
    a=adapter(extra_headers={'authorization':'override'})
    assert await a.complete(prompt,system=system,history=history)=='answer'
    import hashlib
    wire=json.dumps(seen[0]['messages'],ensure_ascii=False,separators=(',',':')).encode()
    assert hashlib.sha256(wire).hexdigest()==evidence['effective_messages_sha256']
    assert seen[0]['messages'][1]['content']=='  quoted\n'
    assert a.last_usage['finish_reason']=='stop'


@pytest.mark.asyncio
async def test_token_overflow_prevents_generation(monkeypatch):
    paths=[]
    def handle(req):
        paths.append(req.url.path)
        if req.url.path=='/apply-template':return httpx.Response(200,json={'prompt':'chat'})
        if req.url.path=='/tokenize':return httpx.Response(200,json={'tokens':[1]*8000})
        raise AssertionError('Must not generate on overflow')
    mock_client(monkeypatch,handle)
    with pytest.raises(ModelResponseError,match='8000 prompt tokens'):
        await adapter(local_context_tokens=8192,max_tokens=512).complete('text')
    assert paths==['/apply-template','/tokenize']


@pytest.mark.asyncio
async def test_total_deadline_stops_stalled_transport(monkeypatch):
    async def handle(req):
        await asyncio.sleep(.1)
        return httpx.Response(200,text=event('late')+event(finish='stop'))
    mock_client(monkeypatch,handle)
    with pytest.raises(ModelResponseError,match='timed out'):
        await adapter(timeout=.01).complete('hi')


def test_local_key_never_goes_to_another_url(monkeypatch):
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_URL','http://127.0.0.1:8111/v1')
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_KEY','backend-secret')
    assert 'backend-secret' not in json.dumps(local.default_provider())
    for url in ['http://127.0.0.1:8112/v1','http://127.0.0.1:8111/v1/evil','https://example.org/v1']:
        assert local.local_api_key(url)==''
    assert local.local_api_key('http://127.0.0.1:8111/v1')=='backend-secret'


def test_missing_local_key_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_URL','http://127.0.0.1:8111/v1')
    monkeypatch.delenv('PUBCAST_LOCAL_MODEL_KEY',raising=False)
    with pytest.raises(ValueError,match='key is missing'):local.default_provider()


@pytest.mark.parametrize('url',['https://example.org/v1','http://127.0.0.1:8111/v1?key=x','http://user:pass@127.0.0.1:8111/v1'])
def test_malformed_launcher_url_rejected(monkeypatch,url):
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_URL',url)
    monkeypatch.setenv('PUBCAST_LOCAL_MODEL_KEY','secret')
    with pytest.raises(ValueError):local.default_provider()
