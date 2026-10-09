// @ts-check
/* Canonical LearningSession practice. No client-side grading or answer keys. */
(() => {
    'use strict';
    /** @typedef {Record<string,unknown>} Row */
    /** @param {unknown} value @returns {Row} */
    function row(value) { if(!value || typeof value!=='object' || Array.isArray(value)) throw new Error('Invalid practice response'); return /** @type {Row} */(value); }
    /** @param {unknown} value @returns {Row[]} */
    function rows(value) { if(!Array.isArray(value)) throw new Error('Invalid practice response'); return value.map(row); }
    /** @param {Row} value @param {string} key @returns {string} */
    function text(value,key) { if(typeof value[key]!=='string') throw new Error('Invalid practice response');return /** @type {string} */(value[key]); }
    /** @param {unknown} value */
    function assertSafeQuestions(value) {
        const forbidden=new Set(['correct_index','correct_answer','answer_key','explanation','grading_rationale','is_correct','rationale']);
        /** @param {unknown} item */
        function visit(item) { if(Array.isArray(item)) item.forEach(visit); else if(item && typeof item==='object') for(const [key,child] of Object.entries(item)) { if(forbidden.has(key)) throw new Error('Unsafe question response');visit(child); } }
        visit(value);for(const q of rows(value)) { text(q,'question_id');text(q,'stem');const options=rows(q.options);if(options.length<2 || options.some(o=>!Number.isInteger(o.index) || typeof o.text!=='string')) throw new Error('Invalid practice response'); }
    }
    /** @param {Document} doc @param {(path:string,options?:RequestInit)=>Promise<Response>} fetcher @param {Storage|null} [store] */
    function createController(doc,fetcher,store=null) {
        /** @param {string} id */
        function el(id) { const value=doc.getElementById(id);if(!value) throw new Error('Practice unavailable');return value; }
        /** @param {string} tag @param {string} value */
        function node(tag,value) { const n=doc.createElement(tag);n.textContent=value;return n; }
        /** @param {string} label @param {()=>Promise<void>} action */
        function button(label,action) { const b=doc.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',()=>{void run(action);});return b; }
        /** @type {Row|null} */ let session=null;
        /** @type {Row|null} */ let assessment=null;
        /** @type {Row[]} */ let questions=[];
        /** @type {Map<string,number>} */ const answers=new Map();
        let position=0;let generation=0;let busy=false;let requestId='';let artifactURL='';let needsFinalization=false;
        /** @type {Map<unknown,unknown>} */ let conceptNames=new Map();
        function storageKey() { return 'visualai-practice:'+text(row(session),'session_id'); }
        /** @param {string} id */
        function remember(id) { if(store && session) store.setItem(storageKey(),id); }
        /** @param {string} suffix */
        function path(suffix) { if(!session) throw new Error('Select an active learning session.');return '/learning-sessions/'+encodeURIComponent(text(session,'session_id'))+suffix; }
        /** @param {string} url @param {Row|undefined} [body] @param {boolean} [emptyPost] */
        async function api(url,body,emptyPost=false) {
            const response=await fetcher(url,body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : emptyPost ? {method:'POST'} : {});
            const value=/** @type {unknown} */(await response.json());
            if(!response.ok) { const code=value && typeof value==='object' && row(value).detail && typeof row(value).detail==='object' ? row(row(value).detail).code : '';
                throw new Error(code==='INSUFFICIENT_EVIDENCE' ? 'This selection needs more evidence for practice.' : response.status===409 ? 'This action is not ready. Refresh practice progress.' : 'Practice is temporarily unavailable. Try again.'); }
            return row(value);
        }
        /** @param {()=>Promise<void>} action */
        async function run(action) { if(busy || session?.state!=='ACTIVE') return;busy=true;const ticket=generation;el('practice-status').textContent='Working…';try { await action(); } catch(error) { if(ticket===generation) el('practice-status').textContent=error instanceof Error && /^(This selection|This action|Practice is|Select an)/.test(error.message) ? error.message : 'Practice returned an invalid response.'; } finally { if(ticket===generation) busy=false; } }
        function renderQuestion() {
            const panel=el('practice-content');panel.replaceChildren();const q=questions[position];if(!q) return;
            panel.append(node('p','Question '+(position+1)+' of '+questions.length),node('h3',text(q,'stem')));
            const group=doc.createElement('fieldset');group.append(node('legend','Choose one answer'));
            for(const option of rows(q.options)) {
                const label=doc.createElement('label');const radio=doc.createElement('input');radio.type='radio';radio.name='practice-answer';radio.value=String(option.index);radio.checked=answers.get(text(q,'question_id'))===option.index;
                radio.addEventListener('change',()=>answers.set(text(q,'question_id'),Number(option.index)));
                label.append(radio,node('span',text(option,'text')));group.append(label);
            }
            panel.append(group);
            if(position>0) panel.append(button('Previous',async()=>{position--;renderQuestion();el('practice-status').textContent='Choose your answer.';}));
            if(position<questions.length-1) panel.append(button('Next question',async()=>{if(!answers.has(text(q,'question_id'))) {el('practice-status').textContent='Choose an answer first.';return;}position++;renderQuestion();el('practice-status').textContent='Choose your answer.';}));
            else panel.append(button('Submit answers',submit));
        }
        /** @param {Row} value */
        function acceptAssessment(value) { assertSafeQuestions(value.questions);assessment=value;remember(text(value,'session_id'));questions=rows(value.questions);answers.clear();position=0;renderQuestion();el('practice-status').textContent='Choose your answer. Answers are graded only after submission.'; }
        async function start() {
            const ticket=generation;el('practice-status').textContent='Generating assessment…';requestId ||= crypto.randomUUID();
            const value=await api(path('/assessment'),{request_id:requestId,question_count:3});if(ticket!==generation) return;acceptAssessment(value);
        }
        /** @param {Row} result */
        function renderPerformance(result) {
            const panel=el('practice-content');panel.replaceChildren(node('h3','Score: '+result.overall_score+'%'));
            for(const c of rows(result.concept_results)) panel.append(node('p',String(conceptNames.get(c.concept_id) || questions.find(q=>q.concept_id===c.concept_id)?.concept_name || 'Concept')+': '+c.correct+' / '+c.attempted));
        }
        async function submit() {
            if(!assessment || answers.size!==questions.length) {el('practice-status').textContent='Answer every question before submitting.';return;}
            const ticket=generation;const id=text(assessment,'session_id');el('practice-status').textContent='Saving your answers…';
            await api(path('/assessments/'+encodeURIComponent(id)+'/submit'),{answers:questions.map(q=>({question_id:text(q,'question_id'),selected_index:answers.get(text(q,'question_id'))}))});
            if(ticket!==generation) return;
            const result=await api(path('/assessments/'+encodeURIComponent(id)+'/result'));if(ticket!==generation) return;
            renderPerformance(result);
            needsFinalization=true;assessment={...assessment,status:'SUBMITTED'};
            await api(path('/mastery/finalize'),{assessment_id:id});if(ticket!==generation) return;needsFinalization=false;requestId='';await refresh();el('practice-status').textContent='Assessment saved. Your learning progress is updated.';
        }
        async function refresh() {
            if(!session) return;const ticket=generation;
            if(!assessment && store) {
                const saved=store.getItem(storageKey());
                if(saved) {
                    const recovered=await api(path('/assessments/'+encodeURIComponent(saved)));if(ticket!==generation) return;
                    assertSafeQuestions(recovered.questions);
                    if(recovered.status==='READY') acceptAssessment(recovered);
                    else if(recovered.status==='SUBMITTED') {
                        assessment=recovered;questions=rows(recovered.questions);needsFinalization=true;
                        const result=await api(path('/assessments/'+encodeURIComponent(saved)+'/result'));if(ticket!==generation) return;
                        renderPerformance(result);
                    }
                }
            }
            if(needsFinalization && assessment) {
                await api(path('/mastery/finalize'),{assessment_id:text(assessment,'session_id')});if(ticket!==generation) return;needsFinalization=false;
            }
            const value=await api(path('/mastery'));if(ticket!==generation) return;
            const panel=el('mastery-content');panel.replaceChildren();
            const names=new Map([...questions.map(q=>/** @type {[unknown,unknown]} */([q.concept_id,q.concept_name])),...conceptNames]);
            for(const item of rows(value.mastery)) panel.append(node('p',String(names.get(item.concept_id)||'Selected concept')+' · '+text(item,'mastery_state')));
            if(rows(value.mastery).length===0) panel.append(node('p','Start practice to see your concept progress.'));
            if(rows(value.mastery).some(m=>m.mastery_state==='NEEDS_SUPPORT')) panel.append(node('p','Ask an instructor for help with the concepts that need support.'));
            for(const job of rows(value.remediation)) {
                const id=text(job,'remediation_job_id');const block=node('article','');block.append(node('h3','Targeted explanation · attempt '+job.attempt_number));
                const completed=row(job.metadata).completed===true;
                if(!completed) block.append(button('Prepare explanation video',()=>video(id)),button('I completed the explanation',async()=>{await api(path('/remediation/'+encodeURIComponent(id)+'/complete'),undefined,true);await refresh();el('practice-status').textContent='Ready for reassessment.';}));
                if(Array.isArray(value.reassessment_job_ids) && value.reassessment_job_ids.includes(id)) block.append(button('Reassess this concept',async()=>{const ticket=generation;el('practice-status').textContent='Generating reassessment…';const result=await api(path('/remediation/'+encodeURIComponent(id)+'/reassessment'),{request_id:crypto.randomUUID(),question_count:3});if(ticket===generation) acceptAssessment(result);}));
                panel.append(block);
            }
        }
        /** @param {string} id */
        async function video(id) {
            const ticket=generation;const base=path('/remediation/'+encodeURIComponent(id)+'/video');el('practice-status').textContent='Preparing remediation…';
            await api(base,{});
            for(let attempt=0;attempt<150 && ticket===generation;attempt++) {
                const value=await api(base);if(ticket!==generation) return;
                if(value.status==='FAILED') {
                    el('practice-status').textContent='Video generation failed. You can retry preparing the explanation video.';
                    throw new Error('Practice is temporarily unavailable. Try again.');
                }
                if(value.status==='COMPLETED') {
                    const response=await fetcher(base+'/stream');if(!response.ok) throw new Error('Practice is temporarily unavailable. Try again.');
                    const blob=await response.blob();if(ticket!==generation) return;if(artifactURL) URL.revokeObjectURL(artifactURL);artifactURL=URL.createObjectURL(blob);
                    const player=doc.createElement('video');player.controls=true;player.src=artifactURL;el('practice-content').replaceChildren(player);el('practice-status').textContent='Your grounded explanation is ready. Watch it, then mark it completed.';return;
                }
                const stageText = value.stage ? ('Rendering explanation: ' + value.stage) : 'Rendering explanation…';
                el('practice-status').textContent=stageText;await new Promise(resolve=>setTimeout(resolve,2000));
            }
            if(ticket===generation) el('practice-status').textContent='The video is still processing. Check its status again shortly.';
        }
        /** @param {Row|null} value @param {Row[]} [concepts] */
        function setSession(value,concepts=[]) { generation++;session=value;assessment=null;needsFinalization=false;conceptNames=new Map(concepts.map(c=>[c.concept_id,c.name]));questions=[];answers.clear();busy=false;requestId='';if(artifactURL) URL.revokeObjectURL(artifactURL);artifactURL='';el('practice-content').replaceChildren();el('mastery-content').replaceChildren();el('practice-panel').hidden=true;/** @type {HTMLButtonElement} */(el('practice-tab')).disabled=value?.state!=='ACTIVE';el('practice-status').textContent='Practice checks understanding of your selected material.'; }
        el('practice-tab').addEventListener('click',()=>{el('practice-panel').hidden=false;void run(refresh);});
        el('start-practice').addEventListener('click',()=>{void run(start);});
        el('refresh-practice').addEventListener('click',()=>{void run(refresh);});
        setSession(null);return {setSession,start:()=>run(start),submit:()=>run(submit),refresh:()=>run(refresh)};
    }
    const exports={createController,assertSafeQuestions};if(typeof module!=='undefined') module.exports=exports;if(typeof window!=='undefined') Reflect.set(window,'VisualAIPractice',exports);
})();
