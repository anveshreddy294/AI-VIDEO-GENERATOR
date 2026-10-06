'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8');
const session = token => ({access_token: token, refresh_token: 'unit-refresh', token_type: 'bearer', expires_in: 3600});
const envelope = token => ({confirmation_required:false, session:session(token), user_id:'00000000-0000-4000-8000-000000000001'});
function environment(responses) {
    const values = new Map();
    const calls = [];
    const redirects = [];
    const window = {location:{origin:'http://localhost',assign:target=>redirects.push(target)}};
    const storage = {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
    vm.runInNewContext(code,{window, sessionStorage:storage, Date, URL, Headers,
        fetch:async(url,init={})=>{ calls.push({url,init}); const response=responses.shift(); if(!response) throw Error('Unexpected request'); return response; }});
    return {api:window.VisualAIAuth,values,calls,redirects};
}
const json = (value,status=200) => new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});

test('normal login uses backend API and Bearer protected fetch',async()=>{
    const env=environment([json(envelope('unit-access')),json({sources:[]})]);
    await env.api.login('unit@example.test','unit-password');
    await env.api.protectedFetch('/sources');
    assert.equal(env.calls[0].url,'/api/auth/login');
    assert.equal(env.calls[1].init.headers.get('Authorization'),'Bearer unit-access');
    assert.equal(env.redirects.length,0);
});
test('confirmation signup does not invent an authenticated session',async()=>{
    const env=environment([json({confirmation_required:true,session:null,user_id:null})]);
    assert.equal(await env.api.signup('unit@example.test','unit-password','Unit User'),false);
    assert.equal(env.calls[0].url,'/api/auth/signup');
    assert.equal(env.values.size,0);
});
test('401 refreshes once and retries with rotated Bearer token',async()=>{
    const env=environment([json(envelope('old')),json({},401),json(envelope('new')),json({sources:[]})]);
    await env.api.login('unit@example.test','unit-password');
    assert.equal((await env.api.protectedFetch('/sources')).status,200);
    assert.equal(env.calls[2].url,'/api/auth/refresh');
    assert.equal(env.calls[3].init.headers.get('Authorization'),'Bearer new');
});
test('invalid refresh clears session and navigates to safe login state',async()=>{
    const env=environment([json(envelope('unit-access')),json({},401),json({secret:'never render this'},401)]);
    await env.api.login('unit@example.test','unit-password');
    await assert.rejects(env.api.protectedFetch('/sources'),/session expired/);
    assert.equal(env.values.size,0);
    assert.equal(env.redirects[0],'/login?reason=expired');
});
test('persistent 401 after refresh clears the session',async()=>{
    const env=environment([json(envelope('old')),json({},401),json(envelope('new')),json({},401)]);
    await env.api.login('unit@example.test','unit-password');
    await assert.rejects(env.api.protectedFetch('/sources'),/session expired/);
    assert.equal(env.values.size,0);
});
test('missing session never sends protected request',async()=>{
    const env=environment([]);
    await assert.rejects(env.api.protectedFetch('/sources'),/Sign in/);
    assert.equal(env.calls.length,0);
    assert.equal(env.redirects[0],'/login?reason=expired');
});
test('malformed stored session is discarded',async()=>{
    const env=environment([]);
    env.values.set('visualai.auth.session','{broken');
    await assert.rejects(env.api.protectedFetch('/sources'),/Sign in/);
    assert.equal(env.values.size,0);
});
test('Bearer token cannot be sent to another origin',async()=>{
    const env=environment([json(envelope('unit-access'))]);
    await env.api.login('unit@example.test','unit-password');
    await assert.rejects(env.api.protectedFetch('https://outside.example.test/sources'),/this application/);
    assert.equal(env.calls.length,1);
});
test('raw failed auth response does not escape into error text',async()=>{
    const env=environment([json({detail:'do-not-render-unit-secret'},401)]);
    await assert.rejects(env.api.login('unit@example.test','unit-password'),error=> !error.message.includes('do-not-render-unit-secret'));
});


test('source job polling displays the safe failure stage', async()=>{
    const dashboard=fs.readFileSync(path.join(__dirname, '../app/api/dashboard.py'), 'utf8');
    const start=dashboard.indexOf('async function waitForSourceJob(');
    const end=dashboard.indexOf('async function runSourceUpload(',start);
    assert.ok(start>=0&&end>start);
    const script=dashboard.slice(start,end)+'\nwaitForSourceJob("JOB_test")';
    const element={textContent:''};
    const context={Date, Error, SOURCE_JOB_TIMEOUT_MS:1000, SOURCE_POLL_INTERVAL_MS:1,
        document:{getElementById:()=>element},
        sourceFetch:async()=>json({status:'failed',state:'FAILED',is_finished:true,
            failure:{stage:'STRUCTURING',code:'STRUCTURE_TIMEOUT',retryable:true,
                     message:'Could not extract grounded concepts from the source.'}})};
    await assert.rejects(vm.runInNewContext(script,context),
        /STRUCTURING: Could not extract grounded concepts from the source/);
});
