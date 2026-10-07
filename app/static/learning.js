// @ts-check
/* Canonical learner UI. All private data comes through authenticated backend APIs. */
(() => {
    'use strict';
    /** @typedef {Record<string, unknown>} Row */
    /** @typedef {{source_id:string, filename:string, status:string, version:number}} Source */
    const POLL_INTERVAL_MS = 2000;
    const MAX_JOB_POLLS = 120;
    /** @param {unknown} value @returns {Row} */
    function row(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid learning response.');
        return /** @type {Row} */ (value);
    }
    /** @param {unknown} value @returns {Row[]} */
    function rows(value) {
        if (!Array.isArray(value)) throw new Error('Invalid learning response.');
        return value.map(row);
    }
    /** @param {Row} value @param {string} key @returns {string} */
    function text(value, key) {
        if (typeof value[key] !== 'string') throw new Error('Invalid learning response.');
        return /** @type {string} */ (value[key]);
    }
    /** @param {unknown} value @returns {string[]} */
    function strings(value) {
        if (!Array.isArray(value) || !value.every(v => typeof v === 'string')) throw new Error('Invalid learning response.');
        return /** @type {string[]} */ (value);
    }
    /** @param {unknown} value @returns {string} */
    function readiness(value) {
        switch (value) {
        case 'READY': return 'Your topics are ready. Choose a topic or subtopic to focus your learning.';
        case 'PENDING': return 'Your material is processing. Refresh when it is ready.';
        case 'FAILED': return 'Knowledge mapping could not finish. You can retry analysis from your source.';
        case 'LEGACY_UNMAPPED': return 'Knowledge mapping is not yet available for this material.';
        default: throw new Error('Invalid knowledge readiness.');
        }
    }
    /** @param {number} status @param {unknown} value @returns {string} */
    function safeError(status, value) {
        if (status === 404) return 'This source or learning session is unavailable.';
        if (status === 409) return 'This session or material is not ready for that action.';
        if (status === 422) return 'The selected learning scope is not valid. Choose it again.';
        if (status === 503 && value && typeof value === 'object') {
            const detail = row(value).detail;
            if (detail && typeof detail === 'object' && row(detail).code === 'SESSION_STORAGE_UNAVAILABLE') {
                return 'Focused sessions are not available yet. You can still explore your material.';
            }
        }
        return 'Learning is temporarily unavailable. Please try again.';
    }
    /** @param {string} sessionId @param {string} question @param {string|undefined} conceptId @returns {Row} */
    function qaPayload(sessionId, question, conceptId) {
        const body = {session_id: sessionId, question};
        return conceptId ? {...body, concept_ids: [conceptId]} : body;
    }
    /** @param {Row} metadata @returns {string} */
    function location(metadata) {
        const page = metadata.page_start ?? metadata.page_number;
        if (typeof page === 'number') return 'Page ' + page;
        if (typeof metadata.slide_number === 'number') return 'Slide ' + metadata.slide_number;
        if (typeof metadata.timestamp_start === 'number') return 'Timestamp ' + metadata.timestamp_start + '–' + metadata.timestamp_end;
        if (typeof metadata.section === 'string') return 'Section ' + metadata.section;
        if (typeof metadata.sequence_index === 'number') return 'Content ' + (metadata.sequence_index + 1);
        return 'Source evidence';
    }
    if (typeof module !== 'undefined') module.exports = {readiness, safeError, qaPayload, location, row, rows};
    if (typeof document === 'undefined') return;
    const auth = /** @type {{protectedFetch:(path:string,options?:RequestInit)=>Promise<Response>, logout:()=>Promise<void>}} */ (Reflect.get(window, 'VisualAIAuth'));
    /** @param {string} id @returns {HTMLElement} */
    function el(id) {
        const element = document.getElementById(id);
        if (!element) throw new Error('Learning screen unavailable.');
        return element;
    }
    /** @param {string} tag @param {string} content @param {string} [className] @returns {HTMLElement} */
    function node(tag, content, className = '') {
        const element = document.createElement(tag); element.textContent = content;
        element.className = className; return element;
    }
    /** @param {string} title @param {()=>Promise<void>} action @returns {HTMLButtonElement} */
    function button(title, action) {
        const b = document.createElement('button'); b.type = 'button'; b.textContent = title;
        b.addEventListener('click', () => run(async () => { b.disabled = true; try { await action(); } finally { b.disabled = false; } }));
        return b;
    }
    /** @param {()=>Promise<void>} action @returns {Promise<void>} */
    async function run(action) {
        try { await action(); } catch (error) {
            el('status').textContent = error instanceof Error ? error.message : 'Learning is unavailable.';
        }
    }
    /** @param {string} path @param {RequestInit} [options] @returns {Promise<unknown>} */
    async function api(path, options = {}) {
        const response = await auth.protectedFetch(path, options);
        let value;
        try { value = /** @type {unknown} */ (await response.json()); }
        catch { throw new Error('Learning returned an invalid response. Please try again.'); }
        if (!response.ok) throw new Error(safeError(response.status, value));
        return value;
    }
    /** @param {string} path @param {Row|undefined} [body] @returns {Promise<unknown>} */
    function post(path, body) {
        return api(path, {method:'POST', ...(body ? {headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {})});
    }
    let navigation = 0;
    /** @type {Source[]} */ let sources = [];
    /** @type {Source|null} */ let source = null;
    /** @type {Row|null} */ let session = null;
    /** @type {Row|null} */ let knowledge = null;
    /** @param {string} panel */
    function show(panel) {
        for (const name of ['sources','explorer','session']) el(name + '-panel').hidden = name !== panel;
        el('status').textContent = '';
    }
    /** @param {Row} value @returns {Source} */
    function decodeSource(value) {
        if (!Number.isInteger(value.version) || /** @type {number} */ (value.version) < 1) throw new Error('Invalid source version.');
        return {source_id:text(value,'source_id'), filename:text(value,'filename'),status:text(value,'status'),version:/** @type {number} */ (value.version)};
    }
    async function loadSources() {
        const ticket = ++navigation; show('sources'); session = null;
        el('source-cards').replaceChildren(node('p','Loading your material…','muted'));
        sources = rows(row(await api('/sources')).sources).map(decodeSource);
        if (ticket !== navigation) return;
        el('source-cards').replaceChildren();
        if (!sources.length) el('source-cards').append(node('p','Your learning space is ready. Add your first source above.','muted'));
        for (const item of sources) {
            const card = node('article','','card'); card.append(node('span',item.status,'badge'),node('h3',item.filename),node('p','Version ' + item.version,'muted'));
            card.append(button('Explore topics',() => openSource(item,item.version))); el('source-cards').append(card);
        }
        el('session-cards').replaceChildren(node('p','Loading your sessions…','muted'));
        try {
            const saved = rows(await api('/learning-sessions'));
            if (ticket !== navigation) return;
            el('session-cards').replaceChildren();
            if (!saved.length) el('session-cards').append(node('p','Choose a topic to start your first focused session.','muted'));
            for (const s of saved) {
                const card = node('article','','card'); const title = sources.find(v => v.source_id === s.source_id)?.filename || 'Your learning material';
                card.append(node('h3',title),node('p',text(s,'state') + ' · Version ' + s.source_version,'muted'));
                card.append(button(s.state === 'ACTIVE' ? 'Resume learning' : 'View session', () => openSession(text(s,'session_id'),s.state === 'ACTIVE')));
                el('session-cards').append(card);
            }
        } catch (error) {
            if (ticket === navigation) el('session-cards').replaceChildren(node('p',error instanceof Error ? error.message : 'Sessions unavailable.','muted'));
        }
        history.replaceState(null,'','/dashboard');
    }
    /** @param {Source} item @param {number} version */
    async function openSource(item, version) {
        const ticket = ++navigation; source = item; session = null; knowledge = null; show('explorer');
        el('explorer-title').textContent = item.filename;
        el('source-location').textContent = 'YOUR MATERIAL · VERSION ' + version;
        el('readiness').textContent = 'Loading your knowledge map…'; el('topic-cards').replaceChildren();
        const map = row(await api('/sources/' + encodeURIComponent(item.source_id) + '/versions/' + version + '/knowledge'));
        if (ticket !== navigation) return;
        knowledge = map; el('readiness').textContent = readiness(map.knowledge_state);
        history.replaceState(null,'','/dashboard?source=' + encodeURIComponent(item.source_id) + '&version=' + version);
        if (map.knowledge_state !== 'READY') {
            if (map.knowledge_state === 'FAILED') el('topic-cards').append(button('Retry analysis',async () => {
                await post('/sources/' + encodeURIComponent(item.source_id) + '/retry-index'); await openSource(item,version);
            }));
            return;
        }
        for (const topic of rows(map.topics)) {
            const details = document.createElement('details'); const subs = rows(topic.subtopics);
            details.append(node('summary',text(topic,'title')));
            details.append(node('p',subs.length + ' subtopics · ' + subs.reduce((n,s) => n + rows(s.concepts).length,0) + ' concepts','muted'));
            details.append(button('Focus on this topic',() => createSession(item,version,text(topic,'topic_id'),null)));
            for (const sub of subs) {
                const block = node('div','','subtopic'); block.append(node('h3',text(sub,'title')));
                const list = document.createElement('ul'); list.className = 'concept-list';
                for (const concept of rows(sub.concepts)) {
                    const evidence = rows(concept.evidence);
                    list.append(node('li',text(concept,'name') + ' · ' + evidence.length + ' evidence references' + (strings(concept.prerequisite_concept_ids).length ? ' · has prerequisites' : '')));
                    if (evidence.length) list.lastElementChild?.append(node('span',' · ' + evidence.map(e => location(row(e.content))).join(' · '),'muted'));
                }
                block.append(list,button('Learn this subtopic',() => createSession(item,version,text(topic,'topic_id'),text(sub,'subtopic_id')))); details.append(block);
            }
            el('topic-cards').append(details);
        }
    }
    /** @param {Source} item @param {number} version @param {string} topic @param {string|null} sub */
    async function createSession(item,version,topic,sub) {
        el('status').textContent = 'Creating your focused learning session…';
        const created = row(await post('/learning-sessions',{session_id:crypto.randomUUID(),source_id:item.source_id,source_version:version,topic_id:topic,subtopic_id:sub}));
        await openSession(text(created,'session_id'),false);
    }
    /** @param {string} id @param {boolean} resume */
    async function openSession(id,resume) {
        const ticket = ++navigation; show('session'); session = null;
        el('session-title').textContent = 'Loading your focused session…'; el('concept-cards').replaceChildren();
        if (resume) await post('/learning-sessions/' + encodeURIComponent(id) + '/resume');
        const view = row(await api('/learning-sessions/' + encodeURIComponent(id)));
        if (ticket !== navigation) return;
        session = row(view.session); source = sources.find(s => s.source_id === session?.source_id) || decodeSource(row(await api('/sources/' + encodeURIComponent(text(session,'source_id')))));
        const version = session.source_version;
        el('session-source').textContent = source.filename + ' · Version ' + version;
        el('session-title').textContent = text(view,'topic_title');
        el('session-subtitle').textContent = typeof view.subtopic_title === 'string' ? view.subtopic_title : 'All concepts in this topic';
        el('session-state').textContent = text(session,'state');
        el('new-version').hidden = !(typeof version === 'number' && source.version > version);
        for (const name of ['ask-button','complete-session','abandon-session']) /** @type {HTMLButtonElement} */ (el(name)).disabled = session.state !== 'ACTIVE';
        const concepts = rows(view.concepts);
        for (const c of concepts) {
            const block = node('article','','concept'); block.append(node('h3',text(c,'name')));
            if (typeof c.definition === 'string') block.append(node('p',c.definition));
            const prerequisites = strings(c.prerequisite_concept_ids);
            if (prerequisites.length) block.append(node('p','Builds on: ' + prerequisites.map(id => concepts.find(v => v.concept_id === id)?.name || 'a prerequisite in your source').join(', '),'muted'));
            block.append(node('p',rows(c.evidence).map(e => location(row(e.content))).join(' · '),'muted'));
            const explain = button('Explain this',async () => {
                /** @type {HTMLTextAreaElement} */ (el('question')).value = 'What is ' + text(c,'name') + '?';
                await ask(text(c,'concept_id'));
            }); explain.disabled = session.state !== 'ACTIVE'; block.append(explain); el('concept-cards').append(block);
        }
        el('answer').textContent = ''; el('citations').replaceChildren();
        history.replaceState(null,'','/dashboard?session=' + encodeURIComponent(id));
    }
    /** @param {string} [concept] */
    async function ask(concept) {
        if (!session || session.state !== 'ACTIVE') throw new Error('Choose an active learning session first.');
        const id = text(session,'session_id'); const ticket = navigation;
        const question = /** @type {HTMLTextAreaElement} */ (el('question')).value.trim();
        if (!question) throw new Error('Enter a question first.');
        const b = /** @type {HTMLButtonElement} */ (el('ask-button')); b.disabled = true;
        el('answer').textContent = 'Finding evidence in your selected topic…'; el('citations').replaceChildren();
        try {
            const answer = row(await post('/qa/answer',qaPayload(id,question,concept)));
            if (ticket !== navigation || !session || session.session_id !== id) return;
            el('answer').textContent = text(answer,'answer');
            for (const citation of rows(answer.citations)) el('citations').append(node('li',text(citation,'location') + ' — ' + text(citation,'quote')));
        } finally { if (ticket === navigation) b.disabled = false; }
    }
    /** @param {'complete'|'abandon'} action */
    async function transition(action) {
        if (!session) return;
        const id = text(session,'session_id'); await post('/learning-sessions/' + encodeURIComponent(id) + '/' + action); await openSession(id,false);
    }
    el('sources-nav').addEventListener('click',() => run(loadSources));
    el('explorer-back').addEventListener('click',() => run(loadSources));
    el('session-back').addEventListener('click',() => run(async () => {
        if (source && session && typeof session.source_version === 'number') await openSource(source,session.source_version); else await loadSources();
    }));
    el('logout').addEventListener('click',() => run(auth.logout));
    el('ask-form').addEventListener('submit',e => { e.preventDefault(); run(() => ask()); });
    el('complete-session').addEventListener('click',() => run(() => transition('complete')));
    el('abandon-session').addEventListener('click',() => run(() => transition('abandon')));
    el('upload-form').addEventListener('submit',e => { e.preventDefault(); run(async () => {
        const file = /** @type {HTMLInputElement} */ (el('upload-file')).files?.[0]; if (!file) return;
        const b = /** @type {HTMLButtonElement} */ (el('upload-button')); b.disabled = true;
        const body = new FormData(); body.append('file',file);
        try {
            const job = row(await api('/pipeline/upload-and-assess',{method:'POST',body}));
            for (let i=0; i<MAX_JOB_POLLS; i++) {
                const current = row(await api('/pipeline/jobs/' + encodeURIComponent(text(job,'job_id'))));
                el('status').textContent = 'Analyzing your material… ' + (typeof current.progress_percent === 'number' ? current.progress_percent : 0) + '%';
                if (current.is_finished === true) {
                    if (current.status !== 'completed') throw new Error('Analysis could not finish. Check your source and retry.');
                    await loadSources(); return;
                }
                await new Promise(resolve => setTimeout(resolve,POLL_INTERVAL_MS));
            }
            throw new Error('Analysis is still running. Refresh your sources before retrying.');
        } finally { b.disabled = false; }
    }); });
    run(async () => {
        const params = new URLSearchParams(window.location.search);
        if (params.has('session')) await openSession(params.get('session') || '',false);
        else {
            await loadSources();
            const selected = sources.find(s => s.source_id === params.get('source'));
            const version = Number(params.get('version'));
            if (selected && Number.isInteger(version) && version > 0) await openSource(selected,version);
        }
    });
})();
