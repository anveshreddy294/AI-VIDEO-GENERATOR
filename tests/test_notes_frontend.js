'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const ui=require('../app/static/notes.js');
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.textContent='';this.className='';this.hidden=false;this.disabled=false;this.value='standard';this.events={};this.attributes={};}
 append(...children){this.children.push(...children);} prepend(...children){this.children.unshift(...children);} replaceChildren(...children){this.children=[...children];this.textContent='';}
 setAttribute(name,value){this.attributes[name]=value;} addEventListener(name,handler){this.events[name]=handler;} set innerHTML(value){throw new Error('Unsafe markup');}
}
class Document {
 constructor(){this.ids=Object.fromEntries(['notes-tab','generate-notes','notes-detail','notes-panel','notes-status','notes-content'].map(id=>[id,new Element()]));}
 createElement(tag){return new Element(tag);} getElementById(id){return this.ids[id];}
}
function all(element){return [element,...element.children.flatMap(all)];}
function content(element){return all(element).map(el=>el.textContent).join(' ');}
const scope={session_id:'owned',source_id:'source',source_version:7,selected_concept_ids:['c1']};
const session={...scope,state:'ACTIVE'};
const citations=[{location:'Notes.pdf — page 4',quote:'Grounded evidence'}];
const item=text=>({text,evidence_ids:['e1'],citations});
function notes(){return {...scope,title:item('Grounded Notes'),summary:item('A supported summary'),key_points:[item('A supported key point')],concepts:[],definitions:[],relationships:[],examples:[],important_equations:[],diagram_specs:[],citations};}
function diagram(type='FLOWCHART'){return {type,title:item('Visible map'),nodes:[{node_id:'a',item:item('Water')},{node_id:'b',item:item('Membrane')}],edges:[{from_node:'a',to_node:'b',item:item('Water -> Membrane')}],evidence_ids:['e1']};}
const safeError=status=>status===404?'This source or learning session is unavailable.':'Learning temporarily unavailable.';
const response=(value,status=200)=>({ok:status===200,status,json:async()=>value});

test('Notes requires active session and controlled tab toggles panel',()=>{
 const doc=new Document();const controller=ui.createController(doc,async()=>response(notes()),safeError);
 assert(doc.ids['notes-tab'].disabled);controller.setSession({...session,state:'COMPLETED'});assert(doc.ids['notes-tab'].disabled);
 controller.setSession(session);assert(!doc.ids['notes-tab'].disabled);doc.ids['notes-tab'].events.click();assert(!doc.ids['notes-panel'].hidden);
});
test('generate uses only session endpoint and presentation preference',async()=>{
 const doc=new Document();let received;const controller=ui.createController(doc,async(...args)=>{received=args;return response(notes());},safeError);
 controller.setSession(session);doc.ids['notes-detail'].value='detailed';await controller.generateNotes();
 assert.equal(received[0],'/learning-sessions/owned/notes');assert.deepEqual(JSON.parse(received[1].body),{detail_level:'detailed'});
 assert.match(content(doc.ids['notes-content']),/supported summary/);assert(!doc.ids['generate-notes'].disabled);
});
test('loading is truthful and duplicate generation is blocked',async()=>{
 const doc=new Document();let finish;let calls=0;const controller=ui.createController(doc,()=>{calls++;return new Promise(resolve=>{finish=resolve;});},safeError);
 controller.setSession(session);const pending=controller.generateNotes();assert.match(doc.ids['notes-status'].textContent,/Generating notes/);assert(doc.ids['generate-notes'].disabled);
 await controller.generateNotes();assert.equal(calls,1);finish(response(notes()));await pending;
});
test('empty sections omitted; equations and item citations remain readable',()=>{
 const doc=new Document();const value=notes();let result=ui.renderNotes(doc,value,scope);
 assert(!content(result).includes('Important Equations'));assert(!content(result).includes('Examples'));assert.match(content(result),/Notes.pdf — page 4/);
 value.important_equations=[item('F = m * a')];result=ui.renderNotes(doc,value,scope);assert.match(content(result),/Important Equations/);assert.match(content(result),/F = m \* a/);
});
for(const type of ['FLOWCHART','CONCEPT_MAP','RELATIONSHIP_MAP'])test('deterministic '+type+' nodes and actual arrows',()=>{
 const doc=new Document();const map=ui.renderDiagram(doc,diagram(type));assert(map);assert.match(content(map),/Water.*→.*Membrane/);assert.equal(all(map).filter(el=>el.className==='notes-diagram-edge').length,1);
});
test('unknown diagram type ignored without interpreting labels',()=>{assert.equal(ui.renderDiagram(new Document(),{type:'javascript',title:'bad'}),null);});
test('provider strings stay text; no script or image elements created',()=>{
 const spec=diagram();spec.title=item('<script>throw 1</script>');spec.nodes[0].item=item('<img src=x onerror=alert(1)>');spec.edges[0].item=item('eval("malicious")');
 const rendered=ui.renderDiagram(new Document(),spec);assert.match(content(rendered),/<script>/);assert(!all(rendered).some(el=>['script','img','svg'].includes(el.tag)));
 const source=fs.readFileSync(require.resolve('../app/static/notes.js'),'utf8');assert(!/innerHTML|eval\(|new Function|createElement\(['"]script/.test(source));
});
test('unrecognized edge endpoint fails safely',()=>{const map=diagram();map.edges[0].to_node='foreign';assert.throws(()=>ui.renderDiagram(new Document(),map));});
test('grounding failure uses allowlisted message without backend details',async()=>{
 const doc=new Document();const controller=ui.createController(doc,async()=>response({detail:{code:'INVALID_NOTES',message:'private stack'}},422),safeError);controller.setSession(session);await controller.generateNotes();
 assert.equal(doc.ids['notes-status'].textContent,'Notes could not be safely generated from the available evidence.');assert(!content(doc.ids['notes-content']).includes('private'));
});
test('foreign session uses existing safe UI boundary',async()=>{
 const doc=new Document();const controller=ui.createController(doc,async()=>response({detail:{message:'foreign private'}},404),safeError);controller.setSession(session);await controller.generateNotes();assert.equal(doc.ids['notes-status'].textContent,safeError(404));
});
test('changing session clears completed Notes and rejects late response',async()=>{
 const doc=new Document();let finish;const controller=ui.createController(doc,()=>new Promise(resolve=>{finish=resolve;}),safeError);controller.setSession(session);
 const pending=controller.generateNotes();controller.setSession({...session,session_id:'next',source_version:8});finish(response(notes()));await pending;assert.equal(doc.ids['notes-content'].children.length,0);
 assert.match(doc.ids['notes-status'].textContent,/Generate grounded notes/);assert(!doc.ids['generate-notes'].disabled);
});
test('selection and same-session version changes invalidate generated content',async()=>{
 const doc=new Document();const controller=ui.createController(doc,async()=>response(notes()),safeError);controller.setSession(session);await controller.generateNotes();assert(doc.ids['notes-content'].children.length);
 controller.setSession({...session,selected_concept_ids:['c2']});assert.equal(doc.ids['notes-content'].children.length,0);
});
test('foreign response scope cannot render',()=>{assert.throws(()=>ui.renderNotes(new Document(),{...notes(),source_version:8},scope));});
test('all navigation paths invalidate Notes and default markup is disabled',()=>{
 const html=fs.readFileSync(require.resolve('../app/static/learning.html'),'utf8');const source=fs.readFileSync(require.resolve('../app/static/learning.js'),'utf8');
 assert.match(html,/id="notes-tab"[^>]*disabled/);assert(html.includes('aria-live="polite"'));assert(source.includes('notesUI.setSession(session)'));assert((source.match(/notesUI.setSession\(null\)/g)||[]).length>=3);
});
