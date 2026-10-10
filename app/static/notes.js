// @ts-check
/* Grounded Notes are data. This renderer executes no provider-generated markup. */
(() => {
    'use strict';
    /** @typedef {Record<string, unknown>} Row */
    /** @typedef {{session_id:string,source_id:string,source_version:number,selected_concept_ids:string[]}} Scope */
    /** @typedef {(path:string,options?:RequestInit)=>Promise<Response>} Fetch */
    /** @param {unknown} value @returns {Row} */
    function row(value) { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid notes response'); return /** @type {Row} */(value); }
    /** @param {unknown} value @returns {Row[]} */
    function rows(value) { if (!Array.isArray(value) || value.length > 128) throw new Error('Invalid notes response'); return value.map(row); }
    /** @param {Row} value @param {string} key @returns {string} */
    function text(value,key) { const result=value[key]; if(typeof result!=='string' || result.length>4096) throw new Error('Invalid notes response'); return result; }
    /** @param {Document} doc @param {string} tag @param {string} value @param {string} [className] */
    function node(doc,tag,value,className='') { const element=doc.createElement(tag); element.textContent=value; element.className=className; return element; }
    /** @param {Document} doc @param {unknown} citations */
    function citationList(doc,citations) {
        const list=node(doc,'ul','','notes-citations');
        for(const citation of rows(citations)) list.append(node(doc,'li',text(citation,'location')));
        return list;
    }
    /** @param {Document} doc @param {unknown} value @param {string} [tag] */
    function noteItem(doc,value,tag='div') { const item=row(value);const element=node(doc,tag,'','notes-item');element.append(node(doc,'p',text(item,'text')),citationList(doc,item.citations));return element; }
    /** @param {Document} doc @param {unknown} value @returns {HTMLElement|null} */
    function renderDiagram(doc,value) {
        const spec=row(value);
        if(!['FLOWCHART','CONCEPT_MAP','RELATIONSHIP_MAP'].includes(String(spec.type))) return null;
        const nodes=rows(spec.nodes);const edges=rows(spec.edges);
        if(nodes.length>32 || edges.length>64) throw new Error('Invalid diagram response');
        /** @type {Map<string,string>} */ const labels=new Map();
        const card=node(doc,'article','','notes-diagram '+String(spec.type).toLowerCase());
        card.append(node(doc,'h4',text(row(spec.title),'text')),citationList(doc,row(spec.title).citations));
        const collection=node(doc,'div','','notes-diagram-nodes');
        for(const entry of nodes) {
            const id=text(entry,'node_id');if(labels.has(id)) throw new Error('Invalid diagram response');
            const item=row(entry.item);const label=text(item,'text');labels.set(id,label);
            const chip=node(doc,'div',label,'notes-diagram-node');chip.append(citationList(doc,item.citations));collection.append(chip);
        }
        card.append(collection);
        for(const edge of edges) {
            const from=labels.get(text(edge,'from_node'));const to=labels.get(text(edge,'to_node'));
            if(from===undefined || to===undefined) throw new Error('Invalid diagram response');
            const link=node(doc,'div','','notes-diagram-edge');link.append(node(doc,'span',from,'notes-edge-node'),node(doc,'span','→','notes-arrow'),node(doc,'span',to,'notes-edge-node'));
            const label=row(edge.item);link.append(node(doc,'p',text(label,'text'),'notes-edge-label'),citationList(doc,label.citations));card.append(link);
        }
        return card;
    }
    /** @param {Document} doc @param {unknown} value @param {Scope} scope */
    function renderNotes(doc,value,scope) {
        const notes=row(value);
        if(notes.session_id!==scope.session_id || notes.source_id!==scope.source_id || notes.source_version!==scope.source_version) throw new Error('Notes scope mismatch');
        const content=node(doc,'div','','grounded-notes');content.append(node(doc,'h3',text(row(notes.title),'text')),citationList(doc,row(notes.title).citations));
        if(notes.summary!==null) {const section=node(doc,'section','');section.append(node(doc,'h4','Summary'),noteItem(doc,notes.summary));content.append(section);}
        for(const [key,title] of [['key_points','Key Points'],['concepts','Concepts'],['definitions','Definitions'],['relationships','Relationships'],['examples','Examples'],['important_equations','Important Equations']]) {
            const items=rows(notes[key]);if(!items.length) continue;
            const section=node(doc,'section','');section.append(node(doc,'h4',title));
            const list=node(doc,'ul','','notes-items');for(const item of items) list.append(noteItem(doc,item,'li'));section.append(list);content.append(section);
        }
        const diagrams=rows(notes.diagram_specs);const maps=node(doc,'section','');let count=0;
        for(const spec of diagrams) {const diagram=renderDiagram(doc,spec);if(diagram){maps.append(diagram);count++;}}
        if(count){maps.prepend(node(doc,'h4','Grounded Visual Map'));content.append(maps);}
        const sources=node(doc,'section','');sources.append(node(doc,'h4','Sources / Citations'),citationList(doc,notes.citations));content.append(sources);
        return content;
    }
    /** @param {number} status @param {unknown} value @param {(status:number,value:unknown)=>string} safeError */
    function errorMessage(status,value,safeError) {
        const detail=value && typeof value==='object' ? row(value).detail : null;
        const code=detail && typeof detail==='object' ? row(detail).code : null;
        if(code==='INVALID_NOTES' || code==='INSUFFICIENT_EVIDENCE') return 'Notes could not be safely generated from the available evidence.';
        if(code==='NOTES_PROVIDER_UNAVAILABLE') return 'Notes generation is temporarily unavailable. Please try again.';
        return safeError(status,value);
    }
    /** @param {Document} doc @param {Fetch} fetch @param {(status:number,value:unknown)=>string} safeError */
    function createController(doc,fetch,safeError) {
        /** @param {string} id */
        function el(id){const element=doc.getElementById(id);if(!element) throw new Error('Notes panel unavailable');return element;}
        const tab=/** @type {HTMLButtonElement} */(el('notes-tab'));
        const generate=/** @type {HTMLButtonElement} */(el('generate-notes'));
        const detail=/** @type {HTMLSelectElement} */(el('notes-detail'));
        const panel=el('notes-panel');const status=el('notes-status');const content=el('notes-content');
        /** @type {Scope|null} */let scope=null;let revision=0;let topicMode=false;
        function reset(){revision++;content.replaceChildren();status.textContent=topicMode?'Generate notes for this topic.':'Generate grounded notes for this learning session.';generate.disabled=!scope&&!topicMode;detail.disabled=!scope&&!topicMode;}
        /** @param {Row|null} session */
        function setSession(session){
            topicMode=false;
            scope=null;tab.disabled=true;panel.hidden=true;tab.setAttribute('aria-expanded','false');
            if(session && session.state==='ACTIVE') {
                const ids=session.selected_concept_ids;
                if(!Array.isArray(ids) || !ids.every(id=>typeof id==='string') || !Number.isInteger(session.source_version)) throw new Error('Invalid learning session');
                scope={session_id:text(session,'session_id'),source_id:text(session,'source_id'),source_version:/** @type {number} */(session.source_version),selected_concept_ids:[...ids]};tab.disabled=false;
            }
            reset();
        }
        async function generateNotes(){
            if(!scope || generate.disabled) return;
            const selected=scope;const ticket=++revision;generate.disabled=true;detail.disabled=true;content.replaceChildren();status.textContent='Generating notes from your selected learning material…';
            try {
                if(!['concise','standard','detailed'].includes(detail.value)) throw new Error('Invalid detail level');
                const response=await fetch('/learning-sessions/'+encodeURIComponent(selected.session_id)+'/notes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({detail_level:detail.value})});
                const value=/** @type {unknown} */(await response.json());
                if(ticket!==revision || scope!==selected) return;
                if(!response.ok){status.textContent=errorMessage(response.status,value,safeError);return;}
                content.replaceChildren(renderNotes(doc,value,selected));status.textContent='Grounded notes generated from your selected learning material.';
            }catch {
                if(ticket===revision) status.textContent='Notes could not be safely generated from the available evidence.';
            }finally {if(ticket===revision){generate.disabled=!scope;detail.disabled=!scope;}}
        }
        tab.addEventListener('click',()=>{if(scope){panel.hidden=!panel.hidden;tab.setAttribute('aria-expanded',String(!panel.hidden));}});
        generate.addEventListener('click',()=>{void generateNotes();});detail.addEventListener('change',reset);
        setSession(null);
        /** @param {boolean} enabled */
        function setTopic(enabled){setSession(null);topicMode=enabled;tab.disabled=!enabled;reset();}
        return {setSession,setTopic,generateNotes};
    }
    const api={createController,renderNotes,renderDiagram,errorMessage};
    if(typeof module!=='undefined') module.exports=api;
    if(typeof window!=='undefined') Reflect.set(window,'VisualAINotes',api);
})();
