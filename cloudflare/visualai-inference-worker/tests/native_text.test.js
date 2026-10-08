import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
import worker from '../src/index.js';
globalThis.crypto ??= webcrypto;
const request=()=>new Request('https://worker.test/v1/generate',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'application/json'},body:JSON.stringify({task:'reasoning',messages:[{role:'user',content:'Return OK'}],max_tokens:32})});
for(const [name,raw,expected] of [['native chat',{choices:[{message:{content:'OK'}}]},'OK'],['legacy text',{response:'OK'},'OK'],['legacy structured',{response:{ok:true}},{ok:true}]])test('normalize '+name,async()=>{
 const calls=[];const result=await worker.fetch(request(),{API_KEY:'test',AI:{run:async(model,input)=>{calls.push({model,input});return raw;}}});
 assert.equal(result.status,200);assert.deepEqual((await result.json()).response,expected);assert.equal(calls.length,1);assert.equal(calls[0].model,'@cf/qwen/qwen3-30b-a3b-fp8');assert.equal(calls[0].input.max_tokens,32);
});
for(const raw of [{},{choices:[]},{choices:[{message:{content:null}}]},{response:''},{response:['fake']}])test('reject invalid native envelope '+JSON.stringify(raw),async()=>{
 const result=await worker.fetch(request(),{API_KEY:'test',AI:{run:async()=>raw}});
 assert.equal(result.status,502);const body=await result.json();assert.equal(body.error,'AI_PROVIDER_ERROR');assert.equal(JSON.stringify(body).includes('Invalid provider response envelope'),false);
});
