import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {handleVisual,VISION_MODELS} from '../src/visual.js';
const image='data:image/png;base64,'+fs.readFileSync(new URL('../../../tests/fixtures/multimodal/flowchart.png',import.meta.url)).toString('base64');
const body={task:'vision_extract',tier:'general',workload:'flowchart',purpose:'extract',schema_version:'visual-v2',image,prompt:'Visible labels only'};
test('diagnostic failure logs redacted primitives and keeps caller sanitized',async()=>{
 const messages=[];const oldLog=console.log,oldError=console.error;console.log=console.error=(message)=>messages.push(JSON.parse(message));
 try{
  const error=Object.assign(new Error('provider failed Bearer super-private api_key=private-key token=private-token '+ 'x'.repeat(1200)),{code:1234,status:500,cause:new Error('secret=private-cause'),nested:{secret:'never-serialize'}});
  const response=await handleVisual(body,{AI:{run:async()=>{throw error;}}},'diagnostic-test');
  const caller=await response.text();assert.equal(response.status,502);assert.equal(JSON.parse(caller).error,'AI_PROVIDER_ERROR');assert(!caller.includes('provider failed'));assert(!caller.includes('private'));
  assert.equal(messages[0].event,'workers_ai_call_start');const logged=messages[1];assert.equal(logged.stage,'env.AI.run');assert.equal(logged.error_code,1234);assert.equal(logged.error_status,500);assert(logged.error_properties.includes('nested'));assert(!JSON.stringify(logged).includes('private'));assert(!JSON.stringify(logged).includes('never-serialize'));assert(logged.error_message.length<=1000);assert.equal(logged.error_cause_message,'secret=[REDACTED]');
 }finally{console.log=oldLog;console.error=oldError;}
});
test('diagnostic success preserves provider response and emits success boundary',async()=>{
 const messages=[];const old=console.log;console.log=(message)=>messages.push(JSON.parse(message));
 try{
  const response=await handleVisual(body,{AI:{run:async()=>({model:VISION_MODELS.general,choices:[{message:{content:'{"visible_text":["Sunlight"]}'}}]})}},'success-test');
  assert.equal(response.status,200);const result=await response.json();assert.equal(result.response,'{"visible_text":["Sunlight"]}');assert.deepEqual(messages.map(x=>x.event),['workers_ai_call_start','workers_ai_call_success']);assert(!JSON.stringify(messages).includes('Visible labels only'));assert(!JSON.stringify(messages).includes('base64'));
 }finally{console.log=old;}
});
