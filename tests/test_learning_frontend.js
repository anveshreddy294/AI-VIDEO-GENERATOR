'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const ui=require('../app/static/learning.js');
test('all non-ready states are honest and unknown states fail closed',()=>{
    assert.match(ui.readiness('LEGACY_UNMAPPED'),/not yet available/);
    assert.match(ui.readiness('PENDING'),/processing/);
    assert.match(ui.readiness('FAILED'),/retry/);
    assert.match(ui.readiness('READY'),/Choose/);
    assert.throws(()=>ui.readiness('fake'));
});
test('foreign and absent sessions share the same safe message',()=>{
    assert.equal(ui.safeError(404,{detail:'foreign secret'}),ui.safeError(404,{detail:'missing'}));
    assert(!ui.safeError(500,{detail:'secret'}).includes('secret'));
});
test('QA browser payload carries session authority only with optional narrowing',()=>{
    assert.deepEqual(ui.qaPayload('owned-session','Question'),{session_id:'owned-session',question:'Question'});
    assert.deepEqual(ui.qaPayload('owned-session','Question','concept'),{session_id:'owned-session',question:'Question',concept_ids:['concept']});
});
test('citations use canonical locations',()=>{
    assert.equal(ui.location({page_number:3}),'Page 3');
    assert.equal(ui.location({slide_number:4}),'Slide 4');
    assert.equal(ui.location({sequence_index:1}),'Content 2');
});
test('private calls use protectedFetch and safe text rendering',()=>{
    const script=fs.readFileSync(path.join(__dirname,'../app/static/learning.js'),'utf8');
    assert(script.includes('auth.protectedFetch'));
    assert(!script.includes('innerHTML'));
    for(const forbidden of ['/assessment/','/video/generate','service_role','cloudflare_worker_secret'])assert(!script.includes(forbidden));
});
test('future actions disabled and learner controls have labels',()=>{
    const html=fs.readFileSync(path.join(__dirname,'../app/static/learning.html'),'utf8');
    assert.match(html,/button disabled[^>]*>Notes/);
    assert.match(html,/button disabled[^>]*>Practice/);
    assert.match(html,/button disabled[^>]*>Visualize/);
    assert(html.includes('label for="question"')&&html.includes('aria-live="polite"'));
});
