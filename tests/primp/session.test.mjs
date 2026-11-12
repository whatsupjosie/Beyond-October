import test from 'node:test';
import assert from 'node:assert/strict';
import {verifiedRecoveryScope} from '../../static/primp/session.mjs';
const auth=(status,body,verified)=>({nativeFetch:async()=>({status,ok:status===200,json:async()=>body}),verify:async()=>verified});
test('recovery chooses a verified account and never uses a stored claimed username',async()=>{
 assert.equal(await verifiedRecoveryScope(auth(200,{auth_enforced:true},{valid:true,username:'one'})),'account:one');
 assert.equal(await verifiedRecoveryScope(auth(200,{auth_enforced:true},{valid:true,username:'two'})),'account:two');
 for(const user of [null,{username:'one'},{valid:false,username:'one'},{valid:true}]) await assert.rejects(verifiedRecoveryScope(auth(200,{auth_enforced:true},user)),/Sign in/);
});
test('standalone recovery is explicit; network and host errors cannot expose an anonymous fallback',async()=>{
 assert.equal(await verifiedRecoveryScope(auth(404)),'standalone');
 assert.equal(await verifiedRecoveryScope(auth(200,{auth_enforced:false})),'standalone');
 await assert.rejects(verifiedRecoveryScope(auth(200,{})),/invalid/);
 for(const status of [401,403,500,503])await assert.rejects(verifiedRecoveryScope(auth(status)),/could not be checked/);
 await assert.rejects(verifiedRecoveryScope({nativeFetch:async()=>{throw Error('offline');}}),/paused/);
 await assert.rejects(verifiedRecoveryScope(null),/adapter/);
});
