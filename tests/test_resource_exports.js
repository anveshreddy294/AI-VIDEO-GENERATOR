'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');
const resources=require('../app/static/resource-exports.js');const analysis=require('../app/static/analysis-results.js');
class Element {
    constructor(tag='div',text=''){this.tag=tag;this.textContent=text;this.children=[];this.events={};this.attributes={};}
    append(...els){this.children.push(...els);}replaceChildren(...els){this.children=els;this.textContent='';}
    setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,fn){this.events[k]=fn;}
    set innerHTML(_){throw Error('Unsafe HTML');}
}
const all=el=>[el,...el.children.flatMap(all)];const text=el=>all(el).map(n=>n.textContent).join(' ');
const diagram=()=>({type:'FLOWCHART',title:{text:'BST — x ≤ y'},nodes:[{node_id:'root',item:{text:'Compare target'}},{node_id:'left',item:{text:'Go left'}}],edges:[{from_node:'root',to_node:'left',item:{text:'x < y'}}]});
test('results precede My sources immediately after upload panel without a duplicate Ready card',()=>{
    const html=fs.readFileSync('app/static/learning.html','utf8');
    const end=html.indexOf('</form>',html.indexOf('id="upload-form"'));
    assert.match(html.slice(end+7),/^\s*<section id="analysis-results"/);
    assert(!html.includes('id="recent-source"'));
    assert(html.indexOf('id="analysis-results"')<html.indexOf('id="source-history"'));
});
test('UTF-8 notes export preserves all displayed sections, lists, equations and code',()=>{
    const notes=new Element();notes.append(new Element('h3','Actual notes'),new Element('p','ΔΨ = ΔP − Δπ'),new Element('h4','Examples'));
    const ul=new Element('ul');ul.append(new Element('li','2 × 3 = 6'));notes.append(ul,new Element('pre','print("hello")\n```\n<script>unsafe</script>'));
    const md=resources.serialize(notes),txt=resources.serialize(notes,false);
    assert.match(md,/### Actual notes/);assert.match(md,/- 2 × 3 = 6/);assert.match(md,/ΔΨ = ΔP − Δπ/);
    assert.match(md,/````\nprint/);assert.match(txt,/print\("hello"\)/);assert(!txt.includes('###'));
});
test('exports reject empty content and omit interactive or active markup',()=>{
    assert.throws(()=>resources.serialize(new Element()),/Generate/);
    const el=new Element();el.append(new Element('p','<script>alert(1)</script>'),new Element('button','hidden prompt'),new Element('script','secret'));
    assert.equal(resources.serialize(el).trim(),'&lt;script&gt;alert(1)&lt;/script&gt;');
    assert.equal(resources.serialize(el,false).trim(),'<script>alert(1)</script>');
});
test('safe topic filenames contain no path or control characters',()=>{
    assert.equal(resources.filename('../../BST: ΔΨ\n','notes','md'),'BST- ΔΨ-notes.md');
    assert.equal(resources.filename('','notes','txt'),'lesson-notes.txt');
    assert(!/[\\/\x00-\x1f]/.test(resources.filename('a/b\\c\u0000','notes','txt')));
});
test('SVG exports the actual nodes and connections with a bounded viewBox',()=>{
    const svg=resources.diagramSVG(diagram());assert.match(svg,/xmlns="http:\/\/www.w3.org\/2000\/svg"/);assert.match(svg,/viewBox="0 0 \d+ \d+"/);
    assert.match(svg,/Compare target/);assert.match(svg,/Go left/);assert.match(svg,/x &lt; y/);assert.match(svg,/marker-end="url\(#arrow\)"/);
});
test('provider labels cannot inject SVG scripts, handlers, links or foreign objects',()=>{
    const d=diagram();d.title.text='" onload="alert(1)';d.nodes[0].item.text='<script>alert(1)</script><foreignObject><img src=x onerror=alert(1)></foreignObject>';
    const svg=resources.diagramSVG(d);assert(svg.includes('&lt;script&gt;'));assert(svg.includes('aria-label="&quot; onload=&quot;alert(1)"'));assert(!/<(?:script|foreignObject|image)\b|\son(?:load|error)="|\shref="/.test(svg));
});
test('empty, malformed and foreign-edge diagrams cannot produce placeholder downloads',()=>{
    assert.throws(()=>resources.diagramSVG({...diagram(),nodes:[]}));
    const d=diagram();d.edges[0].to_node='foreign';assert.throws(()=>resources.diagramSVG(d),/connection/);
    const duplicate=diagram();duplicate.nodes[1].node_id='root';assert.throws(()=>resources.diagramSVG(duplicate),/nodes/);
});
function setup(){const root=new Element();return {root,controller:analysis.createController({getElementById:()=>root,createElement:t=>new Element(t)},{learn:async()=>{},retry:async()=>{}})};}
test('analysis cards show truthful processing, warning completion, one learning action and no duplicates',()=>{
    const {root,controller}=setup();let key=controller.begin({name:'diagram.png'});assert.match(text(root),/Processing.*Uploading/);assert(!text(root).includes('Learn with VisualAI'));
    for(let i=0;i<5;i++)key=controller.update(key,{job_id:'JOB_test',status:'running',is_finished:false,current_stage:'UNDERSTANDING_IMAGE'},'Understanding image…');
    assert.equal(root.children.length,1);
    key=controller.update(key,{job_id:'JOB_test',status:'completed',is_finished:true,result:{source_id:'s',version:2,source_version:'v1',content_ready:true,warnings:['PARTIAL_VISUAL_VERIFICATION']}});
    controller.sources([{source_id:'s',version:2,filename:'diagram.png',modality:'image',content_ready:true}]);
    assert.equal(root.children.length,1);assert.match(text(root),/Version 2.*Completed with warnings.*Learn with VisualAI/);
});
test('failed jobs expose only supported retry and unavailable status never claims completion',()=>{
    const {root,controller}=setup();const key=controller.begin({name:'bad.png'});
    controller.update(key,{job_id:'JOB_test',status:'failed',is_finished:true,failure:{retryable:true}},'Image understanding timed out.');
    assert.match(text(root),/Failed.*timed out.*Retry analysis/);assert(!text(root).includes('Learn with VisualAI'));
    controller.update(key,{job_id:'JOB_test',status:'failed',is_finished:true,failure:{retryable:false}},'Check source.');assert(!text(root).includes('Retry analysis'));
    controller.error(key,'Status temporarily unavailable.');assert.match(text(root),/Processing/);assert(!text(root).includes('Completed'));
});
test('completion alone without backend content readiness never enables learning',()=>{
    const {root,controller}=setup();const key=controller.begin({name:'file.txt'});controller.update(key,{status:'completed',is_finished:true,result:{source_id:'s',version:1}});
    assert(!text(root).includes('Learn with VisualAI'));
});
test('source search preparation requires ready owned material and passes its exact version',async()=>{
    const root=new Element();const calls=[];
    const controller=analysis.createController({getElementById:()=>root,createElement:tag=>new Element(tag)},
        {index:async item=>calls.push([item.source_id,item.version]),learn:async()=>{}});
    controller.sources([{source_id:'s',version:3,filename:'physics.pdf',content_ready:true,status:'READY'}]);
    const button=all(root).find(el=>el.tag==='button' && el.textContent==='Prepare source search');
    assert(button);await button.events.click();assert.deepEqual(calls,[['s',3]]);
    controller.sources([{source_id:'failed',version:1,status:'FAILED',content_ready:false}]);
    const failedCard=root.children.find(el=>el.attributes['data-analysis-key']==='failed:1');
    assert(failedCard);
    assert(!all(failedCard).some(el=>el.tag==='button' && el.textContent==='Prepare source search'));
});
test('restored failed job merges with its unique owned source card and respects retry limit',()=>{
    const {root,controller}=setup();controller.sources([{source_id:'s',version:1,filename:'bad.png',status:'FAILED'}]);
    controller.update('JOB_failed',{job_id:'JOB_failed',status:'failed',is_finished:true,metadata:{source_id:'s',filename:'bad.png',retry_count:3},failure:{retryable:true}},'Analysis failed.');
    assert.equal(root.children.length,1);assert(!text(root).includes('Retry analysis'));assert.match(text(root),/Version 1.*Failed/);
});
