import json
import httpx
import pytest
from modules.llm_framework import get_adapter_for_provider
from modules.openai_compatible_provider import ModelResponseError


def mock(monkeypatch, handler):
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))


def reply(provider, finish=True):
    if provider=='anthropic':
        return {'stop_reason':'end_turn' if finish else 'max_tokens','content':[{'type':'text','text':' answer '}]}
    return {'candidates':[{'finishReason':'STOP' if finish else 'MAX_TOKENS','content':{'parts':[{'thought':True,'text':'private reasoning'},{'text':' answer '}]}}]}


def sse(*events):
    return ''.join('data:'+json.dumps(e)+'\n\n' for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['openai','anthropic','gemini'])
async def test_wire_history_and_credentials(monkeypatch,provider):
    def handle(req):
        body=json.loads(req.content)
        assert 'credential' not in str(req.url)
        if provider=='gemini':
            assert req.headers['x-goog-api-key']=='credential'
            assert body['contents'][0]=={'role':'model','parts':[{'text':'  preserved\n'}]}
        elif provider=='anthropic':
            assert req.headers['x-api-key']=='credential'
            assert body['messages'][0]=={'role':'assistant','content':'  preserved\n'}
        else:
            assert req.url.path=='/v1/responses'
            assert body['input'][0]=={'role':'assistant','content':'  preserved\n'}
            assert body['store'] is False
            return httpx.Response(200,text=sse({'type':'response.output_text.delta','delta':' answer '},{'type':'response.completed','response':{'status':'completed'}}))
        return httpx.Response(200,json=reply(provider))
    mock(monkeypatch,handle)
    a=get_adapter_for_provider(provider,api_key='credential')
    assert await a.complete('question',model='test-model',history=[{'role':'assistant','content':'  preserved\n'}])==' answer '


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['openai','anthropic','gemini'])
@pytest.mark.parametrize('status',[401,429,500])
async def test_http_failure_safe(monkeypatch,provider,status):
    mock(monkeypatch,lambda r:httpx.Response(status,text='SECRET prompt and credential'))
    with pytest.raises(ModelResponseError) as e:
        await get_adapter_for_provider(provider,api_key='credential').complete('hi',model='test')
    assert str(status) in str(e.value) and 'SECRET' not in str(e.value)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['anthropic','gemini'])
async def test_truncated_rejected(monkeypatch,provider):
    mock(monkeypatch,lambda r:httpx.Response(200,json=reply(provider,False)))
    with pytest.raises(ModelResponseError):
        await get_adapter_for_provider(provider,api_key='key').complete('hi',model='test')


@pytest.mark.asyncio
@pytest.mark.parametrize('ending',[[],[{'type':'response.failed'}],[{'type':'response.incomplete'}]])
async def test_openai_partial_not_committed(monkeypatch,ending):
    mock(monkeypatch,lambda r:httpx.Response(200,text=sse({'type':'response.output_text.delta','delta':'partial'},*ending)))
    with pytest.raises(ModelResponseError):
        await get_adapter_for_provider('openai',api_key='key').complete('hi')


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['openai','anthropic','gemini'])
async def test_malformed_rejected(monkeypatch,provider):
    mock(monkeypatch,lambda r:httpx.Response(200,text='data:{oops}\n\n' if provider=='openai' else '{oops}'))
    with pytest.raises(ModelResponseError):
        await get_adapter_for_provider(provider,api_key='key').complete('hi',model='test')


def test_unknown_provider_cannot_silently_use_local():
    with pytest.raises(ValueError):get_adapter_for_provider('typo')


@pytest.mark.asyncio
async def test_concurrent_keys_isolated(monkeypatch):
    seen=[]
    def handle(req):
        seen.append(req.headers['x-api-key'])
        return httpx.Response(200,json=reply('anthropic'))
    mock(monkeypatch,handle)
    import asyncio
    await asyncio.gather(*(get_adapter_for_provider('anthropic',api_key=k).complete('hi') for k in ['one','two']))
    assert sorted(seen)==['one','two']


def test_invalid_selected_credential_never_uses_host_key(monkeypatch):
    from modules.pubpartner_provider import PubPartnerProviderDispatcher
    monkeypatch.setenv('OPENAI_API_KEY','host-secret')
    dispatcher=PubPartnerProviderDispatcher()
    result=dispatcher._resolve_credentials('openai',{'credential_model_id':'other-user'},user_id='me')
    assert result[1]=='' and result[3]=='selected_credential_unavailable'
    class Manager:
        def resolve_model_credentials(self,*a,**k): return None
    dispatcher.set_byok_manager(Manager())
    assert dispatcher._resolve_credentials('openai',{'credential_model_id':'other-user'},user_id='me')[1]==''
