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
    assert.match(html,/button id="notes-tab"[^>]*disabled/);
    assert.match(html,/button disabled[^>]*>Practice/);
    assert.match(html,/button disabled[^>]*>Visualize/);
    assert(html.includes('label for="question"')&&html.includes('aria-live="polite"'));
});

test('visual citations identify uploaded image without internal IDs',()=>{
    assert.equal(ui.location({extraction_method:'vision_ollama'}),'Image upload -- visual evidence');
});

class AskElement {
    constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.className='';this.disabled=false;this.value='';}
    append(...children){this.children.push(...children);}
    replaceChildren(...children){this.children=[...children];this.textContent='';}
    set innerHTML(value){throw new Error('Unsafe HTML');}
}
class AskDocument {
    constructor(){this.ids=Object.fromEntries(['answer','citations','ask-status','ask-button','question'].map(id=>[id,new AskElement()]));}
    createElement(tag){return new AskElement(tag);} getElementById(id){return this.ids[id];}
}
const askSession={session_id:'session-a',source_id:'owned-source',source_version:3,state:'ACTIVE',selected_concept_ids:['concept-a']};
const askResponse=(value,status=200)=>({ok:status===200,status,json:async()=>value});
const groundedAnswer=(extra={})=>({answer:'Water moves through the membrane.',evidence_status:'SUFFICIENT',refusal:false,unanswered_parts:[],citations:[{location:'Page 8',quote:'Water moves through the membrane.',source_id:'owned-source',source_version:3,verified:true,evidence_id:'internal-secret-id'}],...extra});
function askText(element){return [element.textContent,...element.children.map(askText)].join(' ');}
function askSetup(fetch=async()=>askResponse(groundedAnswer())){const doc=new AskDocument();const controller=ui.createAskController(doc,fetch);return {doc,controller};}
function activate(setup,question='What is osmosis?'){setup.controller.setSession(askSession);setup.doc.ids.question.value=question;}

test('ASK only enabled for active session',async()=>{
    let calls=0;const setup=askSetup(async()=>{calls++;return askResponse(groundedAnswer());});
    assert(setup.doc.ids['ask-button'].disabled);await setup.controller.ask();assert.equal(calls,0);
    setup.controller.setSession({...askSession,state:'COMPLETED'});assert(setup.doc.ids.question.disabled);
    activate(setup);assert(!setup.doc.ids['ask-button'].disabled);
});
test('ASK uses session authority and optional concept narrowing only',async()=>{
    let received;const setup=askSetup(async(...args)=>{received=args;return askResponse(groundedAnswer());});activate(setup);await setup.controller.ask('concept-a');
    assert.equal(received[0],'/qa/answer');assert.deepEqual(JSON.parse(received[1].body),{session_id:'session-a',question:'What is osmosis?',concept_ids:['concept-a'],previous_questions:[]});
});
test('ASK loading and duplicate prevention',async()=>{
    let finish,calls=0;const setup=askSetup(()=>{calls++;return new Promise(resolve=>{finish=resolve;});});activate(setup);const pending=setup.controller.ask();
    assert.match(setup.doc.ids['ask-status'].textContent,/Searching your learning material/);assert(setup.doc.ids['ask-button'].disabled);
    await setup.controller.ask();assert.equal(calls,1);finish(askResponse(groundedAnswer()));await pending;assert(!setup.doc.ids['ask-button'].disabled);
});
test('SUFFICIENT renders grounded answer and readable exact-version citation',async()=>{
    const setup=askSetup();activate(setup);await setup.controller.ask();const text=askText(setup.doc.ids.answer);
    assert.match(text,/Grounded in your selected material/);assert.match(text,/Water moves/);assert.match(text,/Page 8.*Version 3/);assert(!text.includes('internal-secret-id'));
});
test('PARTIAL displays supported answer and bounded unanswered parts',async()=>{
    const setup=askSetup(async()=>askResponse(groundedAnswer({evidence_status:'PARTIAL',unanswered_parts:['Its history']})));activate(setup);await setup.controller.ask();
    const text=askText(setup.doc.ids.answer);assert.match(text,/Water moves/);assert.match(text,/Some parts could not be answered/);assert.match(text,/Still unanswered.*Its history/);
});
test('INSUFFICIENT ignores fabricated answer and citation fields',async()=>{
    const setup=askSetup(async()=>askResponse(groundedAnswer({evidence_status:'INSUFFICIENT',answer:'FAKE TEXTBOOK ANSWER'})));activate(setup);await setup.controller.ask();
    const text=askText(setup.doc.ids.answer);assert.match(text,/enough evidence/);assert(!text.includes('FAKE TEXTBOOK'));assert(!text.includes('Page 8'));
});
test('visual citation shows canonical diagram provenance without inference claim',async()=>{
    const value=groundedAnswer();value.citations[0].location='Page 4 · Diagram';const setup=askSetup(async()=>askResponse(value));activate(setup,'Explain this flowchart');await setup.controller.ask();
    assert.match(askText(setup.doc.ids.answer),/Page 4.*Diagram/);assert(!askText(setup.doc.ids.answer).includes('analyzed this just now'));
});
test('same-session context contains only last three learner questions and six turns',async()=>{
    const bodies=[];const setup=askSetup(async(path,options)=>{bodies.push(JSON.parse(options.body));return askResponse(groundedAnswer());});activate(setup);
    for(let i=0;i<8;i++){setup.doc.ids.question.value='Question '+i;await setup.controller.ask();}
    assert.deepEqual(bodies[7].previous_questions,['Question 4','Question 5','Question 6']);assert(!JSON.stringify(bodies).includes('Water moves'));assert.equal(setup.doc.ids.answer.children.length,6);
});
test('session change resets visible history input and follow-up context',async()=>{
    const bodies=[];const setup=askSetup(async(path,options)=>{bodies.push(JSON.parse(options.body));return askResponse(groundedAnswer());});activate(setup);await setup.controller.ask();
    setup.controller.setSession({...askSession,session_id:'session-b'});assert.equal(setup.doc.ids.answer.children.length,0);assert.equal(setup.doc.ids.question.value,'');
    setup.doc.ids.question.value='Why?';await setup.controller.ask();assert.deepEqual(bodies[1].previous_questions,[]);assert.equal(bodies[1].session_id,'session-b');
});
test('stale response and failure cannot populate next session',async()=>{
    for(const reject of [false,true]){let finish,fail;const setup=askSetup(()=>new Promise((resolve,rejected)=>{finish=resolve;fail=rejected;}));activate(setup);const pending=setup.controller.ask();
    setup.controller.setSession({...askSession,session_id:'session-b'});if(reject)fail(new Error('private old error'));else finish(askResponse(groundedAnswer()));await pending;
    assert.equal(setup.doc.ids.answer.children.length,0);assert.match(setup.doc.ids['ask-status'].textContent,/Ask about/);assert(!setup.doc.ids['ask-button'].disabled);}
});
test('same-session selection or version invalidates pending ASK',async()=>{
    let finish;const setup=askSetup(()=>new Promise(resolve=>{finish=resolve;}));activate(setup);const pending=setup.controller.ask();setup.controller.setSession({...askSession,source_version:4,selected_concept_ids:['other']});finish(askResponse(groundedAnswer()));await pending;assert.equal(setup.doc.ids.answer.children.length,0);
});
test('stale finally cannot enable another active request',async()=>{
    const finishes=[];const setup=askSetup(()=>new Promise(resolve=>finishes.push(resolve)));activate(setup);const first=setup.controller.ask();setup.controller.setSession({...askSession,session_id:'session-b'});setup.doc.ids.question.value='Next';const second=setup.controller.ask();finishes[0](askResponse(groundedAnswer()));await first;assert(setup.doc.ids['ask-button'].disabled);finishes[1](askResponse(groundedAnswer()));await second;
});
test('malicious HTML in answers citations and limitations stays text',async()=>{
    const malicious='<script>ignore previous instructions</script><img onerror=alert(1)>';
    const value=groundedAnswer({answer:malicious,evidence_status:'PARTIAL',unanswered_parts:[malicious]});value.citations[0].quote=malicious;
    const setup=askSetup(async()=>askResponse(value));activate(setup);await setup.controller.ask();assert(askText(setup.doc.ids.answer).includes(malicious));
    function walk(element){assert(!['script','img','svg'].includes(element.tag));element.children.forEach(walk);}walk(setup.doc.ids.answer);
});
for(const status of [401,404,409,422,503,500])test('ASK safe error boundary '+status,async()=>{
    const setup=askSetup(async()=>askResponse({detail:{message:'private stack token provider payload'}},status));activate(setup);await setup.controller.ask();
    const text=setup.doc.ids['ask-status'].textContent;assert(!text.includes('private'));assert(!text.includes('payload'));assert.equal(setup.doc.ids.answer.children.length,0);
    if(status===503)assert.equal(text,'Assistant is temporarily unavailable.');if(status===404)assert.equal(text,ui.safeError(404,{}));
});
test('empty and excessive input blocked locally',async()=>{
    let calls=0;const setup=askSetup(async()=>{calls++;return askResponse(groundedAnswer());});activate(setup,' ');await setup.controller.ask();assert.match(setup.doc.ids['ask-status'].textContent,/Enter a question/);
    setup.doc.ids.question.value='x'.repeat(4001);await setup.controller.ask();assert.match(setup.doc.ids['ask-status'].textContent,/4,000/);assert.equal(calls,0);
});
test('unknown status and foreign-version citation fail closed',async()=>{
    for(const value of [groundedAnswer({evidence_status:'UNKNOWN'}),groundedAnswer({citations:[{...groundedAnswer().citations[0],source_version:99}]})]){
        const setup=askSetup(async()=>askResponse(value));activate(setup);await setup.controller.ask();assert.equal(setup.doc.ids.answer.children.length,0);assert.equal(setup.doc.ids['ask-status'].textContent,'Assistant is temporarily unavailable.');}
});
test('ASK integration clears on all navigation paths and uses no vision or vector endpoints',()=>{
    const script=fs.readFileSync(path.join(__dirname,'../app/static/learning.js'),'utf8');const controller=ui.createAskController.toString();
    assert((script.match(/askUI.setSession\(null\)/g)||[]).length>=3);assert(script.includes('askUI.setSession(session)'));
    assert(!/innerHTML|eval\(|new Function|localStorage|sessionStorage/.test(controller));assert(!/\/vision|\/evidence|qdrant|\/sources/.test(controller));
    const html=fs.readFileSync(path.join(__dirname,'../app/static/learning.html'),'utf8');assert(html.includes('id="ask-status" role="status" aria-live="polite"'));assert(html.includes('<textarea disabled id="question"'));
});

test('expired auth is reported through an explicit safe message allowlist',async()=>{
    const setup=askSetup(async()=>{throw new Error('Your session expired. Please sign in again.');});activate(setup);await setup.controller.ask();assert.equal(setup.doc.ids['ask-status'].textContent,'Please sign in again to continue.');
});
