'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const notes = require('../app/static/notes.js');

class Element {
    constructor(tag='div') {
        this.tag=tag;this.children=[];this.events={};this.attributes={};this.style={};
        this.value='standard';this.disabled=false;this.hidden=false;this.textContent='';
        this.classList={add(){},remove(){}};
    }
    append(...nodes){this.children.push(...nodes);}
    prepend(...nodes){this.children.unshift(...nodes);}
    replaceChildren(...nodes){this.children=nodes;this.textContent='';}
    setAttribute(key,value){this.attributes[key]=value;}
    removeAttribute(key){delete this.attributes[key];if(key==='src')this.src='';}
    addEventListener(name,handler){(this.events[name] ||= []).push(handler);}
    dispatch(name){for(const handler of this.events[name] || [])handler({preventDefault(){}});}
    querySelector(selector){return {value:selector.startsWith('input')?'0':'Compare the target to the node; search the smaller or larger subtree.'};}
    reportValidity(){return true;}
    focus(){this.focused=true;}
    pause(){} load(){}
    set innerHTML(value){throw new Error('Unsafe HTML rendering');}
}
function descendants(el){return [el,...el.children.flatMap(descendants)];}
function text(el){return descendants(el).map(node=>node.textContent).join(' ');}
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
function setup(overrides={},options={}) {
    const ids=new Map();
    const document={body:{dataset:{jobPollTimeoutSeconds:'3600'}},getElementById(id){if(!ids.has(id))ids.set(id,new Element());return ids.get(id);},createElement(tag){return new Element(tag);}};
    const calls=[];const downloads=[];const intervals=new Map();let intervalId=0;
    const lesson={lesson_id:'lesson-a',topic:'Binary Search Trees',content:{explanation:'Left keys are smaller; right keys are larger.',key_concepts:[],examples:[],equations:[]},video:null};
    const replies={
        '/educational-content/lesson-a':lesson,
        '/educational-content/lesson-a/notes':{title:'Detailed BST notes',summary:'Search by comparison.',key_points:[],key_concepts:[],examples:[],equations:[]},
        '/educational-content/lesson-a/diagram':{type:'FLOWCHART',title:{text:'BST search'},nodes:[{node_id:'a',item:{text:'Compare'}},{node_id:'b',item:{text:'Found'}}],edges:[{from_node:'a',to_node:'b',item:{text:'Equal'}}]},
        '/educational-content/lesson-a/assessment':{assessment_id:'assessment-a',mcqs:[{question_id:'q1',prompt:'Which subtree contains smaller keys?',options:['Left','Right','Both','Neither']}],descriptive:{question_id:'d1',prompt:'Explain BST search.'}},
        '/educational-content/lesson-a/assessment/submit':{score:85,total_points:100,percentage:85,mcq_results:[],descriptive_feedback:'Correct comparison and branching.'},
        '/educational-content/lesson-a/video':{status:'QUEUED',stage:'QUEUED',progress:5},
        '/educational-content/lesson-a/video/status':{status:'COMPLETED',stage:'COMPLETED',progress:100},
        '/educational-content/lesson-a/ask':{answer:'Compare keys and follow the matching subtree.'},
        '/sources':{sources:[]}, '/learning-sessions':[],
        ...overrides
    };
    const fetch=async(path,options)=>{
        calls.push({path,options});
        const value=replies[path];
        if(typeof value==='function')return value();
        if(path.endsWith('/video/stream'))return {ok:true,status:200,blob:async()=>({type:'video/mp4'})};
        assert.notEqual(value,undefined,'Unexpected request: '+path);
        return {ok:true,status:200,json:async()=>value};
    };
    const TestURL=class extends URL {};
    const revoked=[];
    TestURL.createObjectURL=()=> 'blob:owned-video';TestURL.revokeObjectURL=url=>revoked.push(url);
    const window={VisualAIAuth:{protectedFetch:fetch},VisualAINotes:notes,VisualAIResources:{...require('../app/static/resource-exports.js'),download:(doc,blob,name)=>downloads.push({blob,name}),...options.resources},VisualAIAnalysis:require('../app/static/analysis-results.js'),
        VisualAILearningProfile:options.profile,
        VisualAIPractice:{createController(){return {setSession(){}};}},location:{search:'?lesson=lesson-a'},sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}}};
    vm.runInNewContext(fs.readFileSync('app/static/learning.js','utf8'),{document,window,URL:TestURL,URLSearchParams,Blob,Error,history:{replaceState(){}},setInterval(fn){const id=++intervalId;intervals.set(id,fn);return id;},clearInterval(id){intervals.delete(id);},setTimeout:options.instantTimers?(fn)=>{queueMicrotask(fn);return 0;}:setTimeout,FormData,console});
    return {ids,document,calls,downloads,intervals,revoked};
}

test('incomplete profile stops dashboard resource requests before loading a lesson',async()=>{
    const s=setup({}, {profile:{ensure:async()=>null}});await flush();
    assert.equal(s.calls.length,0);
});
test('completed profile unlocks dashboard and summarizes preferences',async()=>{
    const s=setup({}, {profile:{ensure:async()=>({preferences:{personalization_enabled:true,interested_domains:['Sports'],custom_interest:''}})}});await flush();
    assert.match(s.ids.get('profile-summary').textContent,/Sports/);
    assert.equal(s.ids.get('learning-main').hidden,false);
    assert.ok(s.calls.some(c=>c.path==='/educational-content/lesson-a'));
});
test('failed profile check gives retry and does not load private resources',async()=>{
    const s=setup({}, {profile:{ensure:async()=>{throw Error('unavailable');}}});await flush();
    assert.equal(s.calls.length,0);assert.equal(s.ids.get('profile-gate-retry').hidden,false);
});

test('topic notes detail remains enabled and reaches notes API',async()=>{
    const s=setup();await flush();
    const detail=s.ids.get('notes-detail');detail.value='detailed';detail.dispatch('change');
    assert.equal(s.ids.get('generate-notes').disabled,false);
    s.ids.get('generate-notes').dispatch('click');await flush();
    const call=s.calls.find(call=>call.path.endsWith('/notes'));
    assert.equal(JSON.parse(call.options.body).detail_level,'detailed');
    assert.match(text(s.ids.get('notes-content')),/Detailed BST notes/);
    assert.equal(s.ids.get('notes-status').textContent,'Structured educational notes ready.');
});

test('teaching notation and misconceptions render as text without HTML execution',async()=>{
    const s=setup({'/educational-content/lesson-a':{lesson_id:'lesson-a',topic:'Force',content:{
        explanation:'F = ma',mathematical_notation:[{symbol:'F',meaning:'Net force'}],
        common_misconceptions:[{misconception:'<script>unsafe</script>',correction:'Force changes velocity'}]
    }}});
    await flush();
    const rendered=text(s.ids.get('concept-cards'));
    assert.match(rendered,/Mathematical Notation.*F: Net force/);
    assert.match(rendered,/Common Misconceptions.*<script>unsafe<\/script>.*Force changes velocity/);
});

test('topic flowchart renders actual backend contract',async()=>{
    const s=setup();await flush();s.ids.get('diagram-tab').dispatch('click');
    s.ids.get('generate-diagram').dispatch('click');await flush();
    assert.equal(s.ids.get('diagram-panel').hidden,false);
    assert.match(text(s.ids.get('diagram-content')),/Compare.*→.*Found/);
    assert.equal(s.ids.get('generate-diagram').disabled,false);
});

test('descriptive assessment renders submits and displays text feedback without a learning loop',async()=>{
    const s=setup();await flush();s.ids.get('start-practice').dispatch('click');await flush();
    assert.match(text(s.ids.get('practice-content')),/Explain BST search/);
    const button=descendants(s.ids.get('practice-content')).find(el=>el.textContent==='Submit Assessment');
    button.dispatch('click');await flush();
    const call=s.calls.find(call=>call.path.endsWith('/assessment/submit'));
    assert.equal(JSON.parse(call.options.body).descriptive_answers.d1,'Compare the target to the node; search the smaller or larger subtree.');
    assert.match(text(s.ids.get('mastery-content')),/85.*Correct comparison and branching/);
    assert(!s.calls.some(call=>/mastery|remediation|reassessment/.test(call.path)));
});

test('video polling accepts backend status and playback uses authenticated fetch',async()=>{
    const s=setup();await flush();s.ids.get('start-video-btn').dispatch('click');await flush();
    assert(s.calls.some(call=>call.path.endsWith('/video/stream')));
    assert.equal(s.ids.get('video-player').src,'blob:owned-video');
    assert.equal(s.intervals.size,0);
    s.ids.get('sources-nav').dispatch('click');await flush();
    assert.deepEqual(s.revoked,['blob:owned-video']);
});

test('Ask navigation reveals form after another tab hides it',async()=>{
    const s=setup();await flush();s.ids.get('video-tab').dispatch('click');
    assert.equal(s.ids.get('ask-status').textContent,'Ask a follow-up question about this lesson.');
    assert.equal(s.ids.get('learning-main-columns').style.display,'none');
    s.ids.get('ask-nav').dispatch('click');
    assert.equal(s.ids.get('learning-main-columns').style.display,'grid');
    assert.equal(s.ids.get('question').focused,true);
    s.ids.get('question').value='How does search work?';s.ids.get('ask-form').dispatch('submit');await flush();
    assert.match(text(s.ids.get('answer')),/Compare keys/);
});

for (const foreign of [false,true]) test('uploaded lesson Ask validates citation scope: foreign='+foreign,async()=>{
    const s=setup({
        '/educational-content/lesson-a':{lesson_id:'lesson-a',topic:'Force',source_id:'source-a',source_version:1,content:{explanation:'F = ma'}},
        '/educational-content/lesson-a/ask':{answer:'Six newtons.',citations:[{source_id:foreign?'source-b':'source-a',source_version:1,verified:true,location:'Page 1',quote:'F = ma'}]}
    });
    await flush();s.ids.get('question').value='What force?';s.ids.get('ask-form').dispatch('submit');await flush();
    if(foreign){assert.equal(text(s.ids.get('answer')),'');assert.match(s.ids.get('ask-status').textContent,/Invalid citation scope/);}
    else{assert.match(text(s.ids.get('answer')),/AI-enriched supplemental explanation.*Source observations.*Page 1.*Version 1.*F = ma/);}
});

test('non-JSON server failure gives safe error and allows video retry',async()=>{
    const s=setup({'/educational-content/lesson-a/video':()=>({ok:false,status:500,json:async()=>{throw Error('private traceback');}})});
    await flush();s.ids.get('start-video-btn').dispatch('click');await flush();
    assert.match(s.ids.get('video-status').textContent,/temporarily unavailable/);
    assert(!s.ids.get('video-status').textContent.includes('private'));
    assert.equal(s.ids.get('start-video-btn').disabled,false);
});

test('completed video restores from nested lesson status',async()=>{
    const s=setup({'/educational-content/lesson-a':{lesson_id:'lesson-a',topic:'BST',content:{explanation:'Search by comparison.'},video:{status:'COMPLETED',stage:'COMPLETED',progress:100}}});
    await flush();
    assert.equal(s.ids.get('video-player').src,'blob:owned-video');
    assert(s.calls.some(call=>call.path.endsWith('/video/stream')));
});

test('uploaded lesson is identified from its actual API source fields',async()=>{
    const s=setup({'/educational-content/lesson-a':{lesson_id:'lesson-a',topic:'BST',source_id:'owned-source',source_version:2,content:{explanation:'Search by comparison.'},video:null}});
    await flush();
    assert.equal(s.ids.get('session-source').textContent,'Uploaded learning material · version 2');
});

test('navigation discards late topic notes and does not enable controls',async()=>{
    let finish;
    const s=setup({'/educational-content/lesson-a/notes':()=>new Promise(resolve=>{finish=resolve;})});
    await flush();s.ids.get('generate-notes').dispatch('click');await flush();
    s.ids.get('sources-nav').dispatch('click');await flush();
    finish({ok:true,status:200,json:async()=>({title:'Stale notes',summary:'Must not render.'})});await flush();
    assert(!text(s.ids.get('notes-content')).includes('Stale notes'));
    assert.equal(s.ids.get('generate-notes').disabled,true);
});

test('upload polls beyond the old four-minute ceiling and stops on completion without repeating upload',async()=>{
    let polls=0;
    const s=setup({
        '/pipeline/upload-and-assess':{job_id:'long-job'},
        '/pipeline/jobs/long-job':()=>({ok:true,status:200,json:async()=>++polls<123?
            {status:'running',is_finished:false,current_stage:'UNDERSTANDING_IMAGE'}:
            {status:'completed',is_finished:true,result:{source_id:'source',content_ready:true,warnings:['PARTIAL_VISUAL_VERIFICATION']}}})
    },{instantTimers:true});
    await flush();
    s.document.getElementById('upload-file').files=[new File(['synthetic'],'diagram.png',{type:'image/png'})];
    s.ids.get('upload-form').dispatch('submit');await flush();
    assert.equal(polls,123);
    assert.equal(s.calls.filter(c=>c.path==='/pipeline/upload-and-assess').length,1);
    assert.match(s.ids.get('upload-status').textContent,/Some optional visual evidence/);
    assert.equal(s.ids.get('upload-button').disabled,false);
    await flush();assert.equal(polls,123);
});

test('completed upload remains successful if refreshing the source list fails',async()=>{
    const s=setup({
        '/pipeline/upload-and-assess':{job_id:'saved-job'},
        '/pipeline/jobs/saved-job':{status:'completed',is_finished:true,result:{source_id:'saved-source',content_ready:true}},
        '/sources':async()=>{throw new Error('private upstream error');}
    },{instantTimers:true});
    await flush();
    s.ids.get('sources-panel').hidden=false;
    s.document.getElementById('upload-file').files=[new File(['synthetic'],'notes.txt',{type:'text/plain'})];
    s.ids.get('upload-form').dispatch('submit');await flush();
    assert.equal(s.ids.get('upload-status').textContent,'Extracted content is available.');
    assert.match(s.ids.get('status').textContent,/Your material was saved/);
    assert.equal(s.ids.get('upload-button').disabled,false);
});

test('notes downloads reuse actual generated content with UTF-8 MIME and safe filenames',async()=>{
    const s=setup();await flush();s.ids.get('generate-notes').dispatch('click');await flush();
    const count=s.calls.length;
    for(const format of ['md','txt'])s.ids.get('download-notes-'+format).dispatch('click');await flush();
    assert.equal(s.calls.length,count);assert.equal(s.downloads.length,2);
    assert.equal(s.downloads[0].name,'Binary Search Trees-notes.md');assert.equal(s.downloads[1].name,'Binary Search Trees-notes.txt');
    assert.equal(s.downloads[0].blob.type,'text/markdown;charset=utf-8');assert.equal(s.downloads[1].blob.type,'text/plain;charset=utf-8');
    assert.match(await s.downloads[0].blob.text(),/Detailed BST notes.*\n[\s\S]*Search by comparison/);
});
test('empty notes and unavailable resources cannot download; navigation invalidates old content',async()=>{
    const s=setup();await flush();s.ids.get('download-notes-md').dispatch('click');assert.equal(s.downloads.length,0);
    assert.match(s.ids.get('notes-export-status').textContent,/Generate/);
    s.ids.get('download-lesson-md').dispatch('click');assert.equal(s.downloads.length,1);
    s.ids.get('sources-nav').dispatch('click');await flush();s.ids.get('download-lesson-md').dispatch('click');
    assert.equal(s.downloads.length,1);assert.match(s.ids.get('lesson-export-status').textContent,/Open/);
});
test('diagram SVG is the same image displayed and exports no new provider request',async()=>{
    const s=setup();await flush();s.ids.get('generate-diagram').dispatch('click');await flush();
    const image=descendants(s.ids.get('diagram-content')).find(el=>el.tag==='img');assert(image);
    const count=s.calls.length;s.ids.get('download-diagram-svg').dispatch('click');await flush();assert.equal(s.calls.length,count);
    const svg=await s.downloads[0].blob.text();assert.equal(image.src,'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg));assert.match(svg,/Compare.*Found/);
    assert.equal(s.downloads[0].blob.type,'image/svg+xml;charset=utf-8');
});
test('late PNG conversion cannot export the previous user scope after navigation',async()=>{
    let finish;const s=setup({}, {resources:{png:()=>new Promise(resolve=>{finish=resolve;})}});
    await flush();s.ids.get('generate-diagram').dispatch('click');await flush();s.ids.get('download-diagram-png').dispatch('click');await flush();
    s.ids.get('sources-nav').dispatch('click');await flush();finish(new Blob(['test'],{type:'image/png'}));await flush();assert.equal(s.downloads.length,0);
});
