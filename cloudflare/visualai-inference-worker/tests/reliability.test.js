import test from 'node:test';
import assert from 'node:assert/strict';
import {configuredTimeout,handleVisual,providerFailure} from '../src/visual.js';
import fs from 'node:fs';

for(const code of [5007,3042])test('missing model '+code+' has bounded-fallback classification without raw errors',()=>{
    assert.deepEqual(providerFailure(new Error(code+': unavailable private-error-body')),
        {error:'AI_MODEL_UNAVAILABLE',status:503,native_code:code});
});

test('task budgets accept long environment overrides and reject non-finite values',()=>{
    assert.equal(configuredTimeout('240000',180000),240000);
    for(const bad of ['NaN','Infinity','0','-1','600001'])assert.equal(configuredTimeout(bad,180000),180000);
});

test('visual request honors its Worker environment budget',async()=>{
    const original=globalThis.setTimeout,clear=globalThis.clearTimeout;
    let budget;
    globalThis.setTimeout=(fn,ms)=>{budget=ms;queueMicrotask(fn);return 0;};globalThis.clearTimeout=()=>{};
    try{
        const image='data:image/png;base64,'+fs.readFileSync(new URL('../../../tests/fixtures/multimodal/printed.png',import.meta.url)).toString('base64');
        const response=await handleVisual({task:'vision_extract',tier:'general',schema_version:'visual-v2',purpose:'extract',image,prompt:'Visible evidence'},
            {VISION_TIMEOUT_MS:'240000',AI:{run:()=>new Promise(()=>{})}},'budget-test');
        assert.equal(budget,240000);assert.equal(response.status,502);
        assert.equal((await response.json()).error,'AI_PROVIDER_TIMEOUT');
    }finally{globalThis.setTimeout=original;globalThis.clearTimeout=clear;}
});
