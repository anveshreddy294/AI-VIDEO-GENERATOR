import assert from 'node:assert/strict';
import test from 'node:test';
import {webcrypto} from 'node:crypto';
import baseline from './fixtures/deployed-worker.js';
import worker from '../src/index.js';
globalThis.crypto ??= webcrypto;
const LLAMA='@cf/meta/llama-3.3-70b-instruct-fp8-fast';
const QWEN='@cf/qwen/qwen3-30b-a3b-fp8';
function setup(handler) {
    const calls=[];
    const env={API_KEY:'test-key',AI:{run:async(model,input)=>{
        calls.push({model,input});
        if(handler)return handler(model,input);
        return {response:'answer',usage:null};
    }}};
    return {calls,env};
}
function request(body={task:'reasoning',messages:[{role:'user',content:'hello'}]},options={}){
    return new Request('https://worker.test'+(options.path??'/v1/generate'),{
        method:options.method??'POST',headers:{Authorization:'Bearer test-key','Content-Type':'application/json',...options.headers},
        ...(options.method==='GET'?{}:{body:JSON.stringify(body)})
    });
}
for(const [label,subject] of [['recovered',baseline],['current',worker]]){
    test(label+' health/route/auth/content type/size',async()=>{
        const {env,calls}=setup();
        assert.equal((await subject.fetch(request({}, {method:'GET',path:'/health'}),env)).status,200);
        assert.equal((await subject.fetch(request({}, {path:'/missing'}),env)).status,404);
        for(const Authorization of ['', 'Bearer wrong'])assert.equal((await subject.fetch(request({}, {headers:{Authorization}}),env)).status,401);
        assert.equal((await subject.fetch(request({}, {headers:{'Content-Type':'text/plain'}}),env)).status,415);
        assert.equal((await subject.fetch(request({}, {headers:{'Content-Length':String(256*1024+1)}}),env)).status,413);
        assert.equal(calls.length,0);
    });
    test(label+' task/messages validation',async()=>{
        const {env}=setup();
        assert.equal((await subject.fetch(request({task:'unknown'}),env)).status,422);
        assert.equal((await subject.fetch(request({messages:[]}),env)).status,400);
        assert.equal((await subject.fetch(request({messages:Array.from({length:65},()=>({role:'user',content:'x'}))}),env)).status,413);
        assert.equal((await subject.fetch(request({messages:Array.from({length:64},()=>({role:'user',content:'x'}))}),env)).status,200);
    });
    for(const task of ['content_understanding','structure_repair','assessment_structured','reasoning','qa','notes','roadmap']){
        test(label+' model '+task,async()=>{
            const {env,calls}=setup();
            const response=await subject.fetch(request({task,messages:[{role:'user',content:'hello'}]}),env);
            const body=await response.json();
            assert.equal(response.status,200);
            assert.equal(calls[0].model,['content_understanding','structure_repair','assessment_structured'].includes(task)?LLAMA:QWEN);
            assert.deepEqual(Object.keys(body).sort(),['ok','request_id','task','model','response','usage','latency_ms'].sort());
            assert.equal(body.ok,true);assert.equal(body.task,task);assert.equal(body.response,'answer');
        });
    }
    test(label+' clamps/schema/compatibility',async()=>{
        const {env,calls}=setup();
        const schema={type:'object'};
        await subject.fetch(request({task:'content_understanding',messages:[{role:'user',content:'x'}],max_tokens:99999,temperature:99,response_schema:schema}),env);
        assert.equal(calls[0].input.max_tokens,4096);assert.equal(calls[0].input.temperature,1);
        assert.deepEqual(calls[0].input.response_format,{type:'json_schema',json_schema:schema});
        await subject.fetch(request({task:'reasoning',prompt:'x',max_tokens:-9,temperature:-2,response_schema:schema},{path:'/'}),env);
        assert.equal(calls[1].input.max_tokens,1);assert.equal(calls[1].input.temperature,0);assert.equal(calls[1].input.response_format,undefined);
        await subject.fetch(request({task:'reasoning',prompt:'x',max_tokens:1.5,temperature:'bad'}),env);
        assert.equal(calls[2].input.max_tokens,1024);assert.equal(calls[2].input.temperature,0.2);
    });
    test(label+' sanitized error',async()=>{
        const {env}=setup(()=>{throw new Error('credential-secret');});
        const response=await subject.fetch(request(),env);
        assert.equal(response.status,502);assert(!(await response.text()).includes('credential-secret'));
    });
}
