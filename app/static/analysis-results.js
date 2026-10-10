/* A single card per source/version or active upload; status comes from owned APIs. */
(() => {
    'use strict';
    function createController(doc, actions) {
        const entries=new Map();let sequence=0;
        const container=doc.getElementById('analysis-cards');
        const node=(tag,value,cls='')=>{const el=doc.createElement(tag);el.textContent=value;el.className=cls;return el;};
        function render() {
            container.replaceChildren();
            if(!entries.size) container.append(node('p','Analyzed materials and processing updates will appear here.','muted'));
            for(const [key,item] of entries) {
                const card=node('article','','card analysis-result');card.setAttribute('data-analysis-key',key);
                card.append(node('h3',item.filename || 'Your learning material'));
                card.append(node('p',[item.modality || 'material',item.version?'Version '+item.version:'',item.created_at?'Uploaded '+new Date(item.created_at).toLocaleString():''].filter(Boolean).join(' · '),'muted'));
                const pending=item.job && item.job.is_finished!==true;
                const failed=item.job ? item.job.is_finished===true && item.job.status!=='completed' : ['FAILED','VISION_EXTRACTION_FAILED','EXTRACTION_FAILED','STRUCTURING_FAILED','QUARANTINED'].includes(item.status);
                const ready=!pending && !failed && item.content_ready===true;
                const warnings=item.warnings?.length>0;
                const label=failed?'Failed':pending?'Processing':ready?(warnings?'Completed with warnings':'Completed'):item.job?.status==='completed'?'Completed — content not available':'Processing';
                card.append(node('span',label,'badge'));
                if(!failed && (pending || item.message)) card.append(node('p',item.message || 'Analysis is processing…','analysis-message'));
                if(warnings && ready) card.append(node('p','Some optional visual evidence remains unavailable or uncertain.','muted'));
                if(Number.isInteger(item.topics_count)) card.append(node('p',item.topics_count+' detected topics','muted'));
                if(Array.isArray(item.topic_previews) && item.topic_previews.length) card.append(node('p',item.topic_previews.slice(0,3).filter(v=>typeof v==='string').join(' · '),'muted'));
                const action=(title,fn)=>{const b=node('button',title);b.type='button';b.addEventListener('click',async()=>{if(b.disabled)return;b.disabled=true;try{await fn();}catch{card.append(node('p','This action is temporarily unavailable. Please try again.'));}finally{b.disabled=false;}});card.append(b);};
                if(ready && item.source_id && item.version) action('Learn with VisualAI',()=>actions.learn(item));
                if(ready && item.status==='READY' && actions.explore) action('Explore topics',()=>actions.explore(item));
                if(failed) {
                    card.append(node('p',item.message || 'Analysis could not finish. Check the material and upload it again.'));
                    if(item.job?.job_id && item.job.failure?.retryable===true && item.job.retry_supported!==false && !(item.job.metadata?.retry_count>=3)) action('Retry analysis',()=>actions.retry(key,item.job.job_id));
                }
                container.append(card);
            }
        }
        function merge(key,item) {
            if(item.source_id && item.version) {
                const canonical=item.source_id+':'+item.version;
                const old=entries.get(canonical);
                if(key!==canonical) {const rest=[...entries].filter(([id])=>id!==key && id!==canonical);entries.clear();entries.set(canonical,{...old,...item});for(const [id,value] of rest)entries.set(id,value);}
                entries.set(canonical,{...old,...item});key=canonical;
            } else entries.set(key,item);
            render();return key;
        }
        function sources(values) {
            for(const value of values) {
                const key=value.source_id+':'+value.version;
                for(const [pendingKey,pending] of entries) if(pending.source_id===value.source_id && !pending.version){entries.delete(pendingKey);entries.set(key,pending);}
                const old=entries.get(key);
                entries.set(key,{...value,content_ready:value.content_ready===true || value.status==='READY' || value.status==='CONTENT_READY',...old,
                    ...(!old?.job || old.job.status==='completed'?{content_ready:value.content_ready===true || value.status==='READY' || value.status==='CONTENT_READY'}:{}),
                    filename:value.filename,modality:value.modality,status:value.status,version:value.version,created_at:value.created_at});
                if(value.analysis) update(key,value.analysis,value.analysis.status==='failed'?actions.failure?.(value.analysis.failure):'');
            }render();
        }
        function begin(file) {const key='upload:'+ ++sequence,rest=[...entries];entries.clear();entries.set(key,{filename:file.name,modality:file.name.split('.').pop(),job:{status:'pending',is_finished:false},message:'Uploading your material…'});for(const [id,value] of rest)entries.set(id,value);render();return key;}
        function update(key,job,message) {
            const result=job.result || {},metadata=job.metadata || {},old=entries.get(key) || {};
            const sourceId=result.source_id ?? metadata.source_id ?? old.source_id;
            const matching=[...entries.values()].filter(v=>v.source_id===sourceId && Number.isInteger(v.version));
            const version=[result.version,result.source_version,metadata.source_version,old.version,matching.length===1?matching[0].version:undefined].find(v=>Number.isInteger(v) && v>0);
            const item={...old,job,source_id:result.source_id ?? metadata.source_id ?? old.source_id,version,
                filename:old.filename || result.filename || metadata.filename,modality:old.modality || result.modality || metadata.modality,created_at:old.created_at || job.created_at,
                content_ready:job.is_finished===true && job.status==='completed' && (result.content_ready===true || result.knowledge_state==='READY'),
                warnings:Array.isArray(result.warnings)?result.warnings:[],message};
            if(Number.isInteger(result.topics_count)) item.topics_count=result.topics_count;
            return merge(key,item);
        }
        function error(key,message,confirmed=false) {const old=entries.get(key);if(old){entries.set(key,{...old,job:{...old.job,is_finished:confirmed,status:confirmed?'failed':'running'},content_ready:false,message});render();}}
        render();return {begin,update,error,sources,hasSource:(id,version)=>entries.has(id+':'+version)};
    }
    const api={createController};if(typeof module!=='undefined')module.exports=api;if(typeof window!=='undefined')window.VisualAIAnalysis=api;
})();
