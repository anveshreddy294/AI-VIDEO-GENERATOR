import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
import fs from 'node:fs';
import worker from '../src/index.js';
import {VISION_MODELS,MAX_VISUAL_BODY_BYTES} from '../src/visual.js';
globalThis.crypto ??= webcrypto;
const image='data:image/png;base64,'+fs.readFileSync(new URL('../../../tests/fixtures/multimodal/printed.png',import.meta.url)).toString('base64');
const body=(tier='general')=>({task:'vision_extract',tier,image,prompt:'Return visual-v2 JSON. Visible evidence only.',schema_version:'visual-v2'});
function setup(handler){const calls=[];return {calls,env:{API_KEY:'test',AI:{run:async(model,input)=>{calls.push({model,input});return handler?handler(model,input):{model,choices:[{message:{content:'{"visible_text":["Water crosses a membrane"],"confidence":0.9}'}}]};}}}};}
const req=(data,headers={})=>new Request('https://worker.test/v1/generate',{method:'POST',headers:{Authorization:'Bearer test','Content-Type':'application/json',...headers},body:JSON.stringify(data)});
for(const tier of ['general','deep'])test('adapter '+tier,async()=>{
    const {env,calls}=setup();const response=await worker.fetch(req(body(tier)),env);assert.equal(response.status,200);
    const result=await response.json();assert.equal(result.model,VISION_MODELS[tier]);assert.equal(result.task,'vision_extract');assert.equal(calls.length,1);
    assert.equal(calls[0].input.max_completion_tokens,2048);assert.match(calls[0].input.messages[0].content,/untrusted source DATA/);assert.equal(calls[0].input.messages[1].content[1].image_url.url,image);assert.equal(calls[0].input.image,undefined);
});
for(const changes of [{model:'arbitrary'},{tier:'__proto__'},{tier:'unknown'},{schema_version:'fake'},{purpose:'agent'}])test('rejects '+JSON.stringify(changes),async()=>{const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(),...changes}),env)).status,422);assert.equal(calls.length,0);});
for(const image of ['https://public.test/private.png','data:image/png;base64,eA==','data:image/png;base64,not_base64','data:image/svg+xml;base64,eA=='])test('reject invalid/private URL '+image,async()=>{const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(),image}),env)).status,400);assert.equal(calls.length,0);});
test('actual body bound without Content-Length',async()=>{const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(),prompt:'x'.repeat(MAX_VISUAL_BODY_BYTES)}),env)).status,413);assert.equal(calls.length,0);});
test('text actual bound remains 256 KiB',async()=>{const {env,calls}=setup();assert.equal((await worker.fetch(req({prompt:'x'.repeat(256*1024)}),env)).status,413);assert.equal(calls.length,0);});
test('decoded visual bytes bounded',async()=>{const {env,calls}=setup();const bytes=Buffer.alloc(2*1024*1024+1);Buffer.from([137,80,78,71,13,10,26,10]).copy(bytes);assert.equal((await worker.fetch(req({...body(),image:'data:image/png;base64,'+bytes.toString('base64')}),env)).status,413);assert.equal(calls.length,0);});
test('operational provider error sanitized',async()=>{const {env}=setup(()=>{throw new Error('API_KEY SECRET');});const response=await worker.fetch(req(body()),env);assert.equal(response.status,502);assert(!(await response.text()).includes('SECRET'));});
test('malformed provider envelope is quality failure, not outage',async()=>{const {env}=setup(()=>({choices:[]}));assert.equal((await worker.fetch(req(body('general')),env)).status,422);});
test('unexpected model is denied',async()=>{const {env}=setup(()=>({model:'arbitrary',choices:[{message:{content:'{}'}}]}));assert.equal((await worker.fetch(req(body('deep')),env)).status,422);});

for(const task of ['__proto__','constructor','toString'])test('prototype task is outside text allowlist '+task,async()=>{
    const {env,calls}=setup();
    assert.equal((await worker.fetch(req({task,prompt:'hello'}),env)).status,422);
    assert.equal(calls.length,0);
});

test('unqualified fast tier and triage cannot invoke Workers AI',async()=>{
 for(const changes of [{tier:'fast'},{purpose:'triage'}]){
  const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(),...changes}),env)).status,422);assert.equal(calls.length,0);
 }
 assert.deepEqual(Object.keys(VISION_MODELS).sort(),['deep','general']);
});

for(const identity of [VISION_MODELS.general,VISION_MODELS.general+'-external'])test('exact Gemma identity '+identity,async()=>{
 const {env}=setup(()=>({model:identity,choices:[{message:{content:'{}'}}]}));const r=await worker.fetch(req(body('general')),env);assert.equal(r.status,200);const d=await r.json();assert.equal(d.model_requested,VISION_MODELS.general);assert.equal(d.model,identity);
});
for(const identity of [VISION_MODELS.deep,VISION_MODELS.general+'-external-other',VISION_MODELS.general+'-extra','@cf/arbitrary-external'])test('reject Gemma identity '+identity,async()=>{
 const {env}=setup(()=>({model:identity,choices:[{message:{content:'{}'}}]}));assert.equal((await worker.fetch(req(body('general')),env)).status,422);
});
test('Qwen external suffix not authorized',async()=>{
 const {env}=setup(()=>({model:VISION_MODELS.deep+'-external',choices:[{message:{content:'{}'}}]}));assert.equal((await worker.fetch(req(body('deep')),env)).status,422);
});

for(const tier of ['general','deep'])for(const [workload,tokens] of [['flowchart',2048],['complex_diagram',2048]])test('bounded workload '+tier+' '+workload,async()=>{
 const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(tier),workload}),env)).status,200);assert.equal(calls[0].input.max_completion_tokens,tokens);
});
for(const workload of ['unknown',['flowchart'],42,{},null])test('reject invalid workload '+JSON.stringify(workload),async()=>{
 const {env,calls}=setup();assert.equal((await worker.fetch(req({...body('general'),workload}),env)).status,422);assert.equal(calls.length,0);
});

test('visual inference timeout classified without changing deadline',async()=>{
 const originalSet=globalThis.setTimeout, originalClear=globalThis.clearTimeout;
 let deadline;
 globalThis.setTimeout=(callback,delay)=>{deadline=delay;queueMicrotask(callback);return 0;};globalThis.clearTimeout=()=>{};
 try{
  const {env}=setup(()=>new Promise(()=>{}));const r=await worker.fetch(req(body('general')),env);assert.equal(r.status,502);const d=await r.json();assert.equal(d.error,'AI_PROVIDER_TIMEOUT');assert.equal(typeof d.latency_ms,'number');assert.equal(deadline,45000);
 }finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
});

test('all Gemma visual profiles disable native thinking',async()=>{
 for(const workload of ['flowchart','complex_diagram']){
  const {env,calls}=setup();assert.equal((await worker.fetch(req({...body('general'),workload}),env)).status,200);assert.deepEqual(calls[0].input.chat_template_kwargs,{enable_thinking:false});assert.equal(calls[0].input.max_completion_tokens,2048);
 }
 const {env,calls}=setup();await worker.fetch(req({...body('general'),workload:'printed'}),env);assert.deepEqual(calls[0].input.chat_template_kwargs,{enable_thinking:false});
});

for(const [tier,workload,expected] of [['deep','complex_diagram',55000],['general','complex_diagram',45000],['deep','flowchart',45000],['deep','graph',45000]])test('scoped deadline '+tier+' '+workload,async()=>{
 const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout;let deadline;
 globalThis.setTimeout=(callback,delay)=>{deadline=delay;queueMicrotask(callback);return 0;};globalThis.clearTimeout=()=>{};
 try{const {env}=setup(()=>new Promise(()=>{}));const response=await worker.fetch(req({...body(tier),workload}),env);assert.equal(response.status,502);assert.equal((await response.json()).error,'AI_PROVIDER_TIMEOUT');assert.equal(deadline,expected);}
 finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
});

for(const [code,status,category] of [[3036,429,'AI_QUOTA_EXCEEDED'],[3040,429,'AI_CAPACITY_EXCEEDED'],[3007,502,'AI_PROVIDER_TIMEOUT'],[5035,422,'AI_PROVIDER_ACCESS_REJECTED'],[3023,422,'AI_PROVIDER_ACCESS_REJECTED']])test('safe native provider category '+code,async()=>{
 const {env}=setup(()=>{throw new Error(code+': private image API_KEY SECRET');});const response=await worker.fetch(req(body('deep')),env);assert.equal(response.status,status);const output=await response.json();assert.equal(output.error,category);assert.equal(output.native_code,code);assert(!JSON.stringify(output).includes('SECRET'));
});

test('review contract is separate from extraction and preserves task identity',async()=>{
 const {env,calls}=setup();
 const response=await worker.fetch(req({...body('deep'),task:'vision_verify',purpose:'verify',schema_version:'visual-review-v1'}),env);
 assert.equal(response.status,200);assert.equal((await response.json()).task,'vision_verify');
 assert.equal(calls.length,1);assert.equal(calls[0].model,VISION_MODELS.deep);
 assert.match(calls[0].input.messages[0].content,/Independently check/);
});
test('review cannot use extraction schema',async()=>{
 const {env,calls}=setup();assert.equal((await worker.fetch(req({...body(),task:'vision_verify',purpose:'verify'}),env)).status,422);assert.equal(calls.length,0);
});
