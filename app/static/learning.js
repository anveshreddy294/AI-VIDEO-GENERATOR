// @ts-check
/* Canonical learner UI. All private data comes through authenticated backend APIs. */
(() => {
    'use strict';
    /** @typedef {Record<string, unknown>} Row */
    /** @typedef {{source_id:string, filename:string, status:string, version:number, modality:string, content_ready?:boolean}} Source */
    const POLL_INTERVAL_MS = 2000;
    const configuredPollSeconds = Number(globalThis.document?.body?.dataset?.jobPollTimeoutSeconds);
    const MAX_JOB_POLLS = Math.ceil((Number.isFinite(configuredPollSeconds) && configuredPollSeconds >= 60 ? configuredPollSeconds : 3600) * 1000 / POLL_INTERVAL_MS);
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
    /** @type {Record<string,string>} */
    const uploadValidation = {
        EMPTY_FILE:'The uploaded file is empty.', EMPTY_CONTENT:'The file contains no readable evidence.',
        CORRUPT_IMAGE:'The image is damaged or unreadable.', INVALID_TEXT:'Upload a readable UTF-8 text file.',
        IMAGE_TOO_LARGE:'Images must be at most 8 MB and 16 megapixels.', FILE_TOO_LARGE:'The file exceeds the upload limit.',
        FILE_TYPE_MISMATCH:'The file contents do not match a supported file type.',
        UNSUPPORTED_FILE_TYPE:'This file type is not supported.', UNSUPPORTED_IMAGE_FORMAT:'Use a single-frame PNG, JPEG or WEBP image.'
    };
    /** @param {number} status @param {unknown} value @returns {string} */
    function safeError(status, value) {
        if (status === 401) return 'Your session has expired. Please sign in again.';
        const failures = {
            INVALID_RESPONSE: 'The model returned invalid output. No generated result was saved. Retry generation.',
            VIDEO_PLAN_INVALID: 'This lesson could not be converted into a valid video plan.',
            VIDEO_START_FAILED: 'Video generation could not start. Please retry.',
            VIDEO_TOPIC_MISMATCH: 'Create a lesson for the requested video topic first.',
            VIDEO_SOURCE_REQUIRED: 'Open a lesson from uploaded material to generate a source-grounded video.',
            VIDEO_GROUNDING_REQUIRED: 'Enable source grounding when selecting source content or chunks.',
            VIDEO_EVIDENCE_INSUFFICIENT: 'The selected source does not provide enough eligible evidence for this video.',
            VIDEO_EVIDENCE_NOT_READY: 'Source retrieval is unavailable. Check indexing and retry.',
            VIDEO_EVIDENCE_UNAVAILABLE: 'The original evidence is no longer available for this video.',
            VIDEO_GENERATION_IN_PROGRESS: 'A video is already processing for this lesson. Wait for it to finish.',
            VIDEO_CAPACITY_REACHED: 'Video processing is busy. Retry in 30 seconds.',
            VIDEO_SCENE_SEARCH_UNAVAILABLE: 'Video scene search is unavailable. Check the embedding and search services.',
            VIDEO_SCENE_TOO_LONG: 'This scene exceeds the duration limit. Choose a shorter target or more concise lesson.',
            ASSESSMENT_SUBMISSION_INVALID: 'Answer every question before submitting this assessment.',
            ASSESSMENT_GRADING_FAILED: 'Assessment grading is unavailable. Your answers have not been scored; please retry.',
            NOTES_GENERATION_FAILED: 'Notes generation failed. Please retry.',
            DIAGRAM_GENERATION_FAILED: 'Flowchart generation failed. Please retry.',
            ASSESSMENT_GENERATION_FAILED: 'Assessment generation failed. Please retry.'
        };
        if (value && typeof value === 'object' && !Array.isArray(value)) {
            const detail = row(value).detail;
            if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
                if ((status === 422 || status === 503) && typeof row(detail).stage === 'string') return sourceJobFailure(detail);
                const code = row(detail).code;
                if (typeof code === 'string' && Object.hasOwn(failures, code)) return Reflect.get(failures, code);
            }
        }
        if (status === 404) return 'This source or learning session is unavailable.';
        if (status === 409) return 'This session or material is not ready for that action.';
        if ((status === 422 || status === 415) && value && typeof value === 'object' && !Array.isArray(value)) {
            const detail = row(value).detail;
            if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
                const code = row(detail).code;
                if (typeof code === 'string' && Object.hasOwn(uploadValidation, code)) return uploadValidation[code];
                if (code === 'EDUCATIONAL_CONTENT_INVALID') return 'The model returned an invalid lesson. No lesson was saved. Retry generation.';
                if (code === 'LESSON_NOT_FOUND') return 'The requested educational lesson was not found.';
            }
            if (Array.isArray(detail)) return 'Invalid input format. Please check your topic and try again.';
        }
        if (status === 422) return 'The input topic or selected learning scope is not valid. Try another topic.';
        if (status === 503 && value && typeof value === 'object') {
            const detail = row(value).detail;
            if (detail && typeof detail === 'object' && row(detail).code === 'SESSION_STORAGE_UNAVAILABLE') {
                return 'Focused sessions are not available yet. You can still explore your material.';
            }
        }
        return 'Learning is temporarily unavailable. Please try again.';
    }
    /** Render only known safe job classifications and messages, never upstream details.
     * @param {unknown} value @returns {string}
     */
    function sourceJobFailure(value) {
        const fallback = 'Analysis could not finish. Check your source and retry.';
        if (!value || typeof value !== 'object' || Array.isArray(value)) return fallback;
        const failure = row(value);
        if (failure.code === 'VERIFICATION_REQUIRED') return 'Some image evidence could not be verified. Use a clearer image or upload the original PDF.';
        if (failure.code === 'VISUAL_EVIDENCE_REJECTED') return 'Image evidence was rejected; no unverified content was published.';
        const visionCodes = new Set(['VISION_TIMEOUT','VISION_RATE_LIMIT','VISION_AUTH_FAILED','VISION_INVALID_RESPONSE','VISION_PROVIDER_FAILED','VISION_STRUCTURED_OUTPUT_UNAVAILABLE','VISION_FALLBACK_UNAVAILABLE']);
        if (failure.stage === 'EXTRACTION' && failure.code === 'VISION_EXTRACTION_FAILED' && typeof failure.vision_error_code === 'string' && visionCodes.has(failure.vision_error_code)) {
            if (failure.vision_error_code === 'VISION_TIMEOUT') return 'Image understanding timed out. Retry this image.';
            return 'Image understanding failed (' + failure.vision_error_code + ').';
        }
        const stages = new Set(['EXTRACTION','VERIFICATION','NORMALIZATION','STRUCTURING','CHUNKING','PERSISTENCE','INDEXING']);
        const codes = new Set(['INVALID_MODEL_OUTPUT','INVALID_HIERARCHY','DUPLICATE_IDENTITY','UNSUPPORTED_EVIDENCE','UNSUPPORTED_PREREQUISITE','PREREQUISITE_CYCLE','SOURCE_TOO_LARGE','NO_SAFE_CONTENT','MODEL_UNAVAILABLE','AI_AUTH_REJECTED','AI_REQUEST_REJECTED','AI_INVALID_RESPONSE','AI_CONFIGURATION','STRUCTURE_TIMEOUT','STRUCTURE_EXTRACTION_FAILED','QDRANT_INDEX_FAILED','VECTOR_INDEX_FAILED','MODEL_TIMEOUT','VERIFICATION_FAILED','EXTRACTION_FAILED','NORMALIZATION_FAILED','CHUNKING_FAILED','PERSISTENCE_FAILED','INDEXING_FAILED']);
        if (typeof failure.stage !== 'string' || !stages.has(failure.stage)) return fallback;
        const code = typeof failure.code === 'string' && codes.has(failure.code) ? failure.code : 'SOURCE_PROCESSING_FAILED';
        const reason = typeof failure.reason_code === 'string' && codes.has(failure.reason_code) && failure.reason_code !== code ? ' / ' + failure.reason_code : '';
        const details = new Set(['REFERENCE','QUOTE','ROLE','LABEL','EDGE_ENDPOINTS','EDGE_NAMES','EDGE_ROLE','EDGE_DIRECTION','DEFINITION','PARENT_REFERENCE','EMPTY_REQUIRED_LEVEL','CHILD_SUPPORT']);
        const validation = typeof failure.validation_detail === 'string' && details.has(failure.validation_detail) ? ' / ' + failure.validation_detail : '';
        const saved = failure.message === 'Canonical source saved; knowledge preparation failed. Retry this source.';
        return 'Analysis failed during ' + failure.stage + ' (' + code + reason + validation + ').' +
            (saved ? ' Your canonical source was saved.' : '') +
            (failure.retryable === true ? ' You can retry analysis.' : ' Check your source before trying again.');
    }
    /** @param {HTMLElement} status @returns {{start:()=>void, progress:(job:Row)=>void, fail:(failure:unknown)=>void, error:(error:unknown)=>void}} */
    function createUploadStatus(status) {
        return {
            start() { status.textContent = "Uploading your material\u2026"; },
            progress(job) {
                if (job.current_stage === 'content_ready') {
                    const warnings = job.result && typeof job.result === 'object' ? row(job.result).warnings : [];
                    status.textContent = Array.isArray(warnings) && warnings.length ? 'Extracted content is available. Some optional visual evidence remains unavailable or uncertain.' : 'Extracted content is available.';
                    return;
                }
                /** @type {Record<string,string>} */
                const stages = {'PREPARING_IMAGE':'Preparing image', 'UNDERSTANDING_IMAGE':'Understanding image',
                    'VALIDATING_VISUAL_EVIDENCE':'Validating visual evidence', 'BUILDING_LEARNING_STRUCTURE':'Building learning structure',
                    'INDEXING_SOURCE':'Indexing source', 'source_ready':'Ready'};
                const stage = typeof job.current_stage === 'string' ? job.current_stage : '';
                status.textContent = (stages[stage] || (stage === 'EXTRACTION' || stage === 'ingesting_source' ? 'Understanding your material' : 'Analyzing your material')) + '\u2026';
            },
            fail(failure) { status.textContent = sourceJobFailure(failure); },
            error(error) {
                const safe = new Set([...Object.values(uploadValidation), 'Analysis is still running. Refresh your sources before retrying.',
                    'Your session expired. Please sign in again.', 'Please sign in to continue.',
                    'Learning is temporarily unavailable. Please try again.',
                    'Learning returned an invalid response. Please try again.',
                    'This source or learning session is unavailable.',
                    'This session or material is not ready for that action.',
                    'The selected learning scope is not valid. Choose it again.']);
                status.textContent = error instanceof Error && safe.has(error.message) ? error.message : 'Upload is temporarily unavailable.';
            }
        };
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
        if (typeof metadata.extraction_method === 'string' && metadata.extraction_method.startsWith('vision_')) return 'Image upload -- visual evidence';
        if (typeof metadata.sequence_index === 'number') return 'Content ' + (metadata.sequence_index + 1);
        return 'Source evidence';
    }
    const MAX_QUESTION_CHARS = 4000;
    const MAX_PREVIOUS_QUESTIONS = 3;
    const MAX_VISIBLE_TURNS = 6;
    const MAX_ANSWER_CHARS = 20000;
    const MAX_CITATIONS = 25;
    const MAX_CITATION_LOCATION_CHARS = 2000;
    const MAX_UNANSWERED_PARTS = 5;
    const INSUFFICIENT_MESSAGE = "I couldn't find enough evidence in your selected learning material to answer that reliably.";
    /** @param {Document} doc @param {(path:string,options?:RequestInit)=>Promise<Response>} fetchProtected */
    function createAskController(doc, fetchProtected) {
        /** @param {string} id @returns {HTMLElement} */
        function element(id) {
            const found = doc.getElementById(id);
            if (!found) throw new Error('Learning screen unavailable.');
            return found;
        }
        const output = element('answer');
        const status = element('ask-status');
        const button = /** @type {HTMLButtonElement} */ (element('ask-button'));
        const input = /** @type {HTMLTextAreaElement} */ (element('question'));
        /** @type {Row|null} */ let scope = null;
        /** @type {string[]} */ let previous = [];
        /** @type {HTMLElement[]} */ let turns = [];
        let revision = 0;
        let pending = false;
        /** @param {Row|null} value */
        function setSession(value) {
            revision++; pending = false; previous = []; turns = [];
            scope = value && value.state === 'ACTIVE' ? {...value} : null;
            output.replaceChildren(); element('citations').replaceChildren(); input.value = '';
            input.disabled = !scope; button.disabled = !scope;
            status.textContent = scope ? 'Ask about your selected learning material.' : 'Choose an active learning session first.';
        }
        /** @param {string} tag @param {string} value @param {string} [className] */
        function create(tag, value, className = '') {
            const node = doc.createElement(tag); node.textContent = value; node.className = className; return node;
        }
        /** @param {Row} value @param {string} question @param {Row} current */
        function render(value, question, current) {
            const evidence = value.refusal === true ? 'INSUFFICIENT' : value.evidence_status;
            if (!['SUFFICIENT','PARTIAL','INSUFFICIENT'].includes(/** @type {string} */ (evidence))) throw new Error('Invalid answer status');
            const turn = create('article', '', 'ask-turn');
            turn.append(create('h3','You'),create('p',question),create('h3','VisualAI'));
            const isEnriched = value.provenance_kind === 'AI_ENRICHED';
            const label = isEnriched
                ? 'AI-enriched supplemental explanation'
                : evidence === 'PARTIAL'
                    ? 'Some parts could not be answered from the selected material.'
                    : evidence === 'SUFFICIENT'
                        ? 'Grounded in your selected material'
                        : 'Not enough evidence in your selected material';
            turn.append(create('p',label,'ask-evidence-status'));
            if (evidence === 'INSUFFICIENT') {
                turn.append(create('p',INSUFFICIENT_MESSAGE)); return turn;
            }
            const answerText = text(value,'answer');
            if (!answerText.trim() || answerText.length > MAX_ANSWER_CHARS) throw new Error('Invalid answer');
            const citations = rows(value.citations);
            if (!isEnriched && (!citations.length || citations.length > MAX_CITATIONS)) throw new Error('Invalid citations');
            if (citations.length > MAX_CITATIONS) throw new Error('Invalid citations');
            const list = create('ul','','ask-citations');
            for (const c of citations) {
                if (c.source_version !== current.source_version || c.source_id !== current.source_id || c.verified !== true) throw new Error('Invalid citation scope');
                const label = text(c,'location'); const quote = text(c,'quote');
                if (!label.trim() || label.length > MAX_CITATION_LOCATION_CHARS || quote.length > MAX_QUESTION_CHARS) throw new Error('Invalid citation');
                list.append(create('li',label + ' · Version ' + c.source_version + ' — ' + quote));
            }
            if (citations.length > 0) {
                turn.append(create('p',answerText,'ask-answer'),list);
            } else {
                turn.append(create('p',answerText,'ask-answer'));
            }
            if (evidence === 'PARTIAL') {
                const parts = strings(value.unanswered_parts);
                if (parts.length > MAX_UNANSWERED_PARTS || parts.some(part => part.length > MAX_QUESTION_CHARS)) throw new Error('Invalid limitations');
                if (parts.length) {
                    const limits = create('ul','','ask-limitations');
                    for (const part of parts) limits.append(create('li',part));
                    turn.append(create('h4','Still unanswered'),limits);
                }
            }
            return turn;
        }
        /** @param {string} [concept] */
        async function ask(concept) {
            if (!scope) { status.textContent = 'Choose an active learning session first.'; return; }
            if (pending) return;
            const question = input.value.trim();
            if (!question || question.length > MAX_QUESTION_CHARS) {
                status.textContent = !question ? 'Enter a question first.' : 'Keep your question within 4,000 characters.'; return;
            }
            const current = scope; const ticket = revision;
            const body = {...qaPayload(text(current,'session_id'),question,concept), previous_questions: previous.slice(-MAX_PREVIOUS_QUESTIONS)};
            pending = true; button.disabled = true;
            status.textContent = 'Searching your learning material…';
            try {
                const response = await fetchProtected('/qa/answer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
                if (ticket !== revision) return;
                const value = await response.json();
                if (ticket !== revision) return;
                if (!response.ok) {
                    status.textContent = response.status === 401 ? 'Please sign in again to continue.' : response.status === 503 ? 'Assistant is temporarily unavailable.' : response.status === 422 ? 'Your question or selected learning scope is not valid. Check it and try again.' : safeError(response.status,value);
                    return;
                }
                const turn = render(row(value),question,current);
                turns = [...turns,turn].slice(-MAX_VISIBLE_TURNS); output.replaceChildren(...turns);
                previous = [...previous,question].slice(-MAX_PREVIOUS_QUESTIONS);
                status.textContent = ''; input.value = '';
            } catch (error) {
                if (ticket === revision) {
                    const expired = error instanceof Error && ['Sign in to continue.', 'Your session expired. Please sign in again.'].includes(error.message);
                    status.textContent = expired ? 'Please sign in again to continue.' : 'Assistant is temporarily unavailable.';
                }
            } finally {
                if (ticket === revision) { pending = false; button.disabled = !scope; }
            }
        }
        setSession(null);
        return {setSession,ask};
    }
    if (typeof module !== 'undefined') module.exports = {readiness, safeError, sourceJobFailure, createUploadStatus, qaPayload, location, row, rows, createAskController};
    if (typeof document === 'undefined') return;
    const auth = /** @type {{protectedFetch:(path:string,options?:RequestInit)=>Promise<Response>, logout:()=>Promise<void>}} */ (Reflect.get(window, 'VisualAIAuth'));
    const notesUI = /** @type {{createController:(doc:Document,fetch:(path:string,options?:RequestInit)=>Promise<Response>,safeError:(status:number,value:unknown)=>string)=>{setSession:(session:Row|null)=>void,setTopic:(enabled:boolean)=>void}}} */ (Reflect.get(window, "VisualAINotes")).createController(document, (path,options) => auth.protectedFetch(path,options), safeError);
    const practiceUI = /** @type {{createController:(doc:Document,fetch:(path:string,options?:RequestInit)=>Promise<Response>,store:Storage)=>{setSession:(session:Row|null,concepts?:Row[])=>void}}} */ (Reflect.get(window,"VisualAIPractice")).createController(document,(path,options)=>auth.protectedFetch(path,options),window.sessionStorage);
    const askUI = createAskController(document, (path,options) => auth.protectedFetch(path,options));
    const resources = Reflect.get(window, 'VisualAIResources');
    let diagramExport = '';
    let diagramScope = null;
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
        try { el('status').textContent = ''; await action(); } catch (error) {
            el('status').textContent = error instanceof Error ? error.message : 'Learning is unavailable.';
        }
    }
    /** @param {string} path @param {RequestInit} [options] @returns {Promise<unknown>} */
    async function api(path, options = {}) {
        const response = await auth.protectedFetch(path, options);
        let value;
        try { value = /** @type {unknown} */ (await response.json()); }
        catch { throw new Error(response.ok ? 'Learning returned an invalid response. Please try again.' : safeError(response.status, {})); }
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
    const analysis = Reflect.get(window, 'VisualAIAnalysis').createController(document, {
        learn: async item => {
            el('status').textContent = 'Preparing lesson for ' + item.filename + '…';
            const lesson = row(await post('/educational-content', {source_id:item.source_id,source_version:item.version}));
            await openEducationalLesson(text(lesson,'content_id'));
        },
        retry: async (key,jobId) => {
            const job = row(await post('/pipeline/jobs/' + encodeURIComponent(jobId) + '/retry'));
            key = analysis.update(key,{...job,is_finished:false},'Retry queued…');
            await trackAnalysis(key,job);
        },
        explore: async item => openSource(item,item.version),
        index: prepareSourceSearch,
        failure: sourceJobFailure
    });
    async function prepareSourceSearch(item) {
        el('status').textContent = 'Preparing source search for ' + item.filename + '…';
        try {
            await post('/sources/' + encodeURIComponent(item.source_id) + '/retry-index?version=' + item.version);
            await loadSources();
            el('status').textContent = 'Source search is ready.';
        } catch (error) {
            el('status').textContent = error instanceof Error ? error.message : 'Source search preparation failed. Please retry.';
            throw error;
        }
    }
    function show(panel) {
        diagramExport = ''; diagramScope = null;
        for (const name of ['notes','diagram','lesson']) el(name + '-export-status').textContent = '';
        if (panel !== 'session') resetEducationalVideo();
        for (const name of ['sources','explorer','session']) el(name + '-panel').hidden = name !== panel;
        el('status').textContent = '';
    }
    /** @param {Row} value @returns {Source} */
    function decodeSource(value) {
        if (!Number.isInteger(value.version) || /** @type {number} */ (value.version) < 1) throw new Error('Invalid source version.');
        return {
            source_id: text(value, 'source_id'),
            filename: text(value, 'filename'),
            modality: typeof value.modality === 'string' ? value.modality : typeof value.source_type === 'string' ? value.source_type : 'material',
            status: text(value, 'status'),
            version: /** @type {number} */ (value.version),
            content_ready: Boolean(value.content_ready),
            created_at: typeof value.created_at === 'string' ? value.created_at : '',
            topics_count: Number.isInteger(value.topics_count) ? value.topics_count : undefined,
            topic_previews: Array.isArray(value.topic_previews) ? value.topic_previews : [],
            analysis: value.analysis && typeof value.analysis === 'object' ? value.analysis : null,
        };
    }

    // Active educational lesson state
    /** @type {Row|null} */ let currentEducationalLesson = null;
    /** @type {ReturnType<typeof setInterval>|null} */ let videoPollInterval = null;
    let videoGeneration = 0;
    let initialVideoLink = true;
    let videoObjectURL = '';
    let captionObjectURL = '';
    let displayedVideo = null;

    function resetEducationalVideo() {
        videoGeneration++;
        if (videoPollInterval) clearInterval(videoPollInterval);
        videoPollInterval = null;
        const player = /** @type {HTMLVideoElement} */ (el('video-player'));
        player.pause(); player.removeAttribute('src'); player.load();
        if (videoObjectURL) URL.revokeObjectURL(videoObjectURL);
        videoObjectURL = '';
        el('download-video').hidden = true;
        el('download-video').removeAttribute('href');
        el('download-video').removeAttribute('download');
        if (captionObjectURL) URL.revokeObjectURL(captionObjectURL);
        captionObjectURL = '';
        el('video-captions-track').removeAttribute('src');
        el('video-scenes').replaceChildren();
        el('video-evidence').replaceChildren();
        el('video-details-status').textContent = '';
        displayedVideo = null;
        el('retry-video-index').disabled = true;
        el('video-index-status').textContent = '';
        el('video-scene-search-results').replaceChildren();
        el('video-player-container').style.display = 'none';
    }

    /** @param {'learn'|'notes'|'diagram'|'practice'|'video'} tab */
    function switchLessonTab(tab) {
        const tabs = ['learn', 'notes', 'diagram', 'practice', 'video'];
        for (const t of tabs) {
            const btn = document.getElementById(t + '-tab');
            if (btn) {
                if (t === tab) {
                    btn.classList.add('primary');
                } else if (t !== 'video') {
                    btn.classList.remove('primary');
                }
            }
        }
        const mainCols = el('learning-main-columns');
        const notesPanel = el('notes-panel');
        const diagramPanel = el('diagram-panel');
        const practicePanel = el('practice-panel');
        const videoPanel = el('video-panel');

        mainCols.style.display = (tab === 'learn') ? 'grid' : 'none';
        notesPanel.hidden = (tab !== 'notes');
        diagramPanel.hidden = (tab !== 'diagram');
        practicePanel.hidden = (tab !== 'practice');
        videoPanel.hidden = (tab !== 'video');
    }

    /** @param {Row} notesData */
    function renderEducationalNotes(notesData) {
        const container = el('notes-content');
        container.replaceChildren();
        if (typeof notesData.title === 'string') container.append(node('h3', notesData.title));

        const summaryBlock = node('div', '', 'card');
        summaryBlock.append(node('h3', 'Summary'));
        summaryBlock.append(node('p', text(notesData, 'summary')));
        container.append(summaryBlock);

        const takeaways = strings(notesData.key_takeaways || notesData.key_points || []);
        if (takeaways.length) {
            const tBlock = node('div', '', 'card');
            tBlock.append(node('h3', 'Key Takeaways'));
            const ul = document.createElement('ul');
            for (const t of takeaways) ul.append(node('li', t));
            tBlock.append(ul);
            container.append(tBlock);
        }

        const detailed = typeof notesData.detailed_notes === 'string' ? notesData.detailed_notes : '';
        if (detailed) {
            const dBlock = node('div', '', 'card');
            dBlock.append(node('h3', 'Detailed Study Notes'));
            const p = node('p', detailed);
            p.style.whiteSpace = 'pre-wrap';
            dBlock.append(p);
            container.append(dBlock);
        }
        for (const concept of rows(notesData.key_concepts || [])) {
            const section = node('article', '', 'card');
            section.append(node('h3', text(concept, 'name')), node('p', text(concept, 'explanation')));
            container.append(section);
        }

        const examples = strings(notesData.examples || []);
        if (examples.length) {
            const eBlock = node('div', '', 'card');
            eBlock.append(node('h3', 'Illustrative Examples'));
            const ul = document.createElement('ul');
            for (const ex of examples) ul.append(node('li', ex));
            eBlock.append(ul);
            container.append(eBlock);
        }

        const formulas = strings(notesData.formula_sheet || notesData.equations || []);
        if (formulas.length) {
            const fBlock = node('div', '', 'card');
            fBlock.append(node('h3', 'Formula Sheet'));
            const ul = document.createElement('ul');
            for (const f of formulas) ul.append(node('li', f));
            fBlock.append(ul);
            container.append(fBlock);
        }
    }

    /** @param {Row} diagramData */
    function renderEducationalDiagram(diagramData) {
        const container = el('diagram-content');
        container.replaceChildren();
        diagramExport = ''; diagramScope = null;
        const svg = resources.diagramSVG(diagramData);

        const card = node('article', '', 'notes-diagram flowchart');
        const titleText = diagramData.title && typeof diagramData.title === 'object' ? text(row(diagramData.title), 'text') : (typeof diagramData.title === 'string' ? diagramData.title : 'Process Flowchart');
        card.append(node('h3', titleText));
        const image = document.createElement('img');
        image.className = 'flowchart-image'; image.alt = titleText + ' — nodes and directed connections';
        image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
        const viewport = node('div', '', 'flowchart-viewport');
        viewport.tabIndex = 0; viewport.setAttribute('role','region'); viewport.setAttribute('aria-label','Flowchart image. Scroll horizontally to view all connections.');
        viewport.append(image); card.append(viewport);

        const nodesCollection = node('div', '', 'notes-diagram-nodes');
        const nodes = rows(diagramData.nodes || []);
        const nodeLabels = new Map();
        for (const n of nodes) {
            const id = typeof n.node_id === 'string' ? n.node_id : (typeof n.id === 'string' ? n.id : 'node');
            const item = n.item && typeof n.item === 'object' ? row(n.item) : null;
            const label = item && typeof item.text === 'string' ? item.text : (typeof n.label === 'string' ? n.label : id);
            nodeLabels.set(id, label);
            const chip = node('div', '', 'notes-diagram-node');
            chip.append(node('strong', label));
            if (typeof n.description === 'string' && n.description) {
                chip.append(node('p', n.description, 'muted'));
            }
            nodesCollection.append(chip);
        }
        card.append(nodesCollection);

        const edges = rows(diagramData.edges || []);
        if (edges.length) {
            const edgesTitle = node('h4', 'Connections & Transitions');
            edgesTitle.style.marginTop = '20px';
            card.append(edgesTitle);
            for (const e of edges) {
                const fromId = text(e, 'from_node');
                const toId = text(e, 'to_node');
                const fromLabel = nodeLabels.get(fromId) || fromId;
                const toLabel = nodeLabels.get(toId) || toId;
                const item = e.item && typeof e.item === 'object' ? row(e.item) : null;
                const edgeLabel = item && typeof item.text === 'string' ? item.text : (typeof e.label === 'string' ? e.label : '');
                const edgeDiv = node('div', '', 'notes-diagram-edge');
                edgeDiv.append(
                    node('span', fromLabel, 'notes-edge-node'),
                    node('span', '→', 'notes-arrow'),
                    node('span', toLabel, 'notes-edge-node')
                );
                if (edgeLabel) {
                    edgeDiv.append(node('p', edgeLabel, 'notes-edge-label'));
                }
                card.append(edgeDiv);
            }
        }
        container.append(card);
        diagramExport = svg; diagramScope = currentEducationalLesson;
    }

    /** @param {Row} assessmentData */
    function renderEducationalAssessment(assessmentData) {
        const container = el('practice-content');
        container.replaceChildren();

        const mcqs = rows(assessmentData.mcqs || []);
        const descs = assessmentData.descriptive ? [row(assessmentData.descriptive)] : [];

        const form = document.createElement('form');
        form.id = 'educational-assessment-form';

        if (mcqs.length) {
            form.append(node('h3', 'Multiple Choice Questions'));
            for (let i = 0; i < mcqs.length; i++) {
                const q = mcqs[i];
                const qId = text(q, 'question_id');
                const fieldset = document.createElement('fieldset');
                fieldset.style.margin = '16px 0';
                fieldset.style.padding = '16px';
                fieldset.style.borderRadius = '8px';
                fieldset.style.border = '1px solid var(--line)';

                const legend = node('legend', 'Question ' + (i + 1) + ' (' + (q.points || 1) + ' pt)');
                legend.style.fontWeight = 'bold';
                fieldset.append(legend);

                const prompt = node('p', text(q, 'prompt'));
                prompt.style.fontWeight = '600';
                fieldset.append(prompt);

                const options = strings(q.options || []);
                for (let optIdx = 0; optIdx < options.length; optIdx++) {
                    const label = document.createElement('label');
                    label.style.display = 'flex';
                    label.style.alignItems = 'center';
                    label.style.gap = '8px';
                    label.style.margin = '8px 0';
                    label.style.cursor = 'pointer';

                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = 'mcq_' + qId;
                    radio.value = String(optIdx);
                    radio.required = true;

                    label.append(radio, node('span', options[optIdx]));
                    fieldset.append(label);
                }
                form.append(fieldset);
            }
        }

        if (descs.length) {
            const descHeader = node('h3', 'Descriptive Questions');
            descHeader.style.marginTop = '24px';
            form.append(descHeader);

            for (let i = 0; i < descs.length; i++) {
                const dq = descs[i];
                const dqId = text(dq, 'question_id');
                const fieldset = document.createElement('fieldset');
                fieldset.style.margin = '16px 0';
                fieldset.style.padding = '16px';
                fieldset.style.borderRadius = '8px';
                fieldset.style.border = '1px solid var(--line)';

                const legend = node('legend', 'Descriptive Question ' + (i + 1) + ' (' + (dq.points || 2) + ' pts)');
                legend.style.fontWeight = 'bold';
                fieldset.append(legend);

                const prompt = node('p', text(dq, 'prompt'));
                prompt.style.fontWeight = '600';
                fieldset.append(prompt);

                if (typeof dq.context === 'string' && dq.context) {
                    fieldset.append(node('p', dq.context, 'muted'));
                }

                const textarea = document.createElement('textarea');
                textarea.name = 'desc_' + dqId;
                textarea.rows = 4;
                textarea.placeholder = 'Write your explanation here...';
                textarea.required = true;
                textarea.style.width = '100%';
                fieldset.append(textarea);

                form.append(fieldset);
            }
        }

        const submitBtn = button('Submit Assessment', async () => {
            if (!currentEducationalLesson) return;
            if (!form.reportValidity()) return;
            const selectedLesson = currentEducationalLesson;
            /** @type {Record<string, number>} */ const mcqAnswers = {};
            for (const q of mcqs) {
                const qId = text(q, 'question_id');
                const selected = form.querySelector('input[name="mcq_' + qId + '"]:checked');
                if (selected) {
                    mcqAnswers[qId] = parseInt(/** @type {HTMLInputElement} */ (selected).value, 10);
                }
            }
            /** @type {Record<string, string>} */ const descAnswers = {};
            for (const dq of descs) {
                const dqId = text(dq, 'question_id');
                const ta = form.querySelector('textarea[name="desc_' + dqId + '"]');
                if (ta) {
                    descAnswers[dqId] = /** @type {HTMLTextAreaElement} */ (ta).value;
                }
            }

            el('practice-status').textContent = 'Submitting answers and evaluating…';
            const result = row(await post('/educational-content/' + encodeURIComponent(text(selectedLesson, 'lesson_id')) + '/assessment' + '/submit', {
                mcq_answers: mcqAnswers,
                descriptive_answers: descAnswers,
            }));

            if (currentEducationalLesson === selectedLesson) renderAssessmentResults(result);
        });
        submitBtn.classList.add('primary');
        submitBtn.style.marginTop = '16px';
        form.append(submitBtn);

        container.append(form);
    }

    /** @param {Row} result */
    function renderAssessmentResults(result) {
        const container = el('mastery-content');
        container.replaceChildren();

        const banner = node('div', '', 'card');
        const score = result.score;
        const total = result.total_points;
        const pct = result.percentage;
        banner.append(node('h3', 'Assessment Result: ' + score + ' / ' + total + ' (' + pct + '%)'));
        banner.style.background = (Number(pct) >= 70) ? '#edf4e9' : '#fff3cd';
        banner.style.borderColor = (Number(pct) >= 70) ? 'var(--green)' : '#ffeeba';
        container.append(banner);

        const mcqResults = rows(result.mcq_results || []);
        if (mcqResults.length) {
            const section = node('div', '', 'card');
            section.append(node('h4', 'Multiple Choice Feedback'));
            for (const mr of mcqResults) {
                const item = node('div', '', 'concept');
                const isCorrect = mr.is_correct === true;
                item.append(node('span', isCorrect ? 'CORRECT' : 'INCORRECT', 'badge'));
                item.append(node('p', text(mr, 'explanation')));
                section.append(item);
            }
            container.append(section);
        }

        const descFeedback = typeof result.descriptive_feedback === 'string' ? result.descriptive_feedback : '';
        if (descFeedback) {
            const dSection = node('div', '', 'card');
            dSection.append(node('h4', 'Descriptive Feedback'));
            dSection.append(node('p', descFeedback));
            container.append(dSection);
        }
        el('practice-status').textContent = 'Assessment completed! See your feedback below.';
    }

    /** @param {string} lessonId @param {number} ticket */
    async function playEducationalVideo(lessonId, ticket, generationId = '', sceneId = '') {
        const query = generationId ? '?generation_id=' + encodeURIComponent(generationId) : '';
        const response = await auth.protectedFetch('/educational-content/' + encodeURIComponent(lessonId) + '/video/stream' + query);
        if (!response.ok) throw new Error(safeError(response.status, {}));
        const blob = await response.blob();
        if (ticket !== videoGeneration) return;
        history.replaceState(null, '', '/dashboard?lesson=' + encodeURIComponent(lessonId) +
            (generationId ? '&generation=' + encodeURIComponent(generationId) : '') +
            (sceneId ? '&scene=' + encodeURIComponent(sceneId) : ''));
        if (videoObjectURL) URL.revokeObjectURL(videoObjectURL);
        videoObjectURL = URL.createObjectURL(blob);
        const download = el('download-video');
        download.setAttribute('href', videoObjectURL);
        download.setAttribute('download', 'visualai-' + lessonId + (generationId ? '-' + generationId : '') + '.mp4');
        download.hidden = false;
        const player = /** @type {HTMLVideoElement} */ (el('video-player'));
        player.src = videoObjectURL; player.load();
        el('video-player-container').style.display = 'block';
        el('video-status').textContent = 'Animated narrated video is ready.';
        el('start-video-btn').textContent = 'Load Generated Video';
        el('regenerate-video-btn').disabled = false;
        void loadVideoSceneDetails(lessonId, ticket, query, sceneId);
    }

    async function loadVideoSceneDetails(lessonId, ticket, query, selectedSceneId = '') {
        const base = '/educational-content/' + encodeURIComponent(lessonId) + '/video';
        try {
            const metadata = row(await api(base + '/metadata' + query));
            if (ticket !== videoGeneration) return;
            displayedVideo = {lessonId, generationId:text(metadata, 'generation_id'), ticket};
            showVideoIndexStatus(metadata.indexing_status, metadata.indexing_error_code);
            el('video-details-status').textContent = metadata.provenance_kind === 'SOURCE_GROUNDED'
                ? 'This video uses retrieved source quotations. Select a scene to inspect its evidence.'
                : 'AI-enriched explanation. Illustrative examples are not source evidence.';
            const navigation = el('video-scenes'); navigation.replaceChildren();
            const scenes = Array.isArray(metadata.scenes) ? metadata.scenes : [];
            for (const value of scenes) {
                const scene = row(value); const timing = scene.timing ? row(scene.timing) : null;
                const button = document.createElement('button'); button.type = 'button';
                const seconds = timing ? Number(timing.start_seconds) : NaN;
                button.textContent = (Number.isFinite(seconds) ? Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0') + ' — ' : '') + text(scene, 'title');
                button.addEventListener('click', () => {
                    if (ticket !== videoGeneration) return;
                    if (Number.isFinite(seconds)) {
                        const player = el('video-player');
                        const seek = () => { if (ticket === videoGeneration) player.currentTime = seconds; };
                        if (player.readyState >= 1) seek();
                        else player.addEventListener('loadedmetadata', seek, {once:true});
                    }
                    const evidence = el('video-evidence'); evidence.replaceChildren();
                    const references = Array.isArray(scene.evidence_references) ? scene.evidence_references : [];
                    if (!references.length) evidence.textContent = 'AI-generated explanation or illustrative example; no source claim.';
                    for (const value of references) {
                        const reference = row(value); const paragraph = document.createElement('p');
                        paragraph.textContent = (reference.page_start ? 'Page ' + Number(reference.page_start) + ': ' : 'Source excerpt: ') + text(reference, 'quote');
                        evidence.append(paragraph);
                    }
                });
                navigation.append(button);
                if (scene.scene_id === selectedSceneId) button.click();
            }
            if (metadata.caption_url) {
                const response = await auth.protectedFetch(base + '/captions' + query);
                if (!response.ok) throw new Error('Captions unavailable.');
                const blob = await response.blob();
                if (ticket !== videoGeneration) return;
                if (captionObjectURL) URL.revokeObjectURL(captionObjectURL);
                captionObjectURL = URL.createObjectURL(blob);
                el('video-captions-track').src = captionObjectURL;
            }
        } catch (error) {
            if (ticket === videoGeneration) el('video-details-status').textContent = 'Scene details or captions are unavailable for this version. Generate a new version to refresh it.';
        }
    }

    function showVideoIndexStatus(status, errorCode) {
        const explanations = {
            EMBEDDING_MODEL_UNAVAILABLE:'The configured embedding model is unavailable.',
            EMBEDDING_FAILED:'Embedding generation or validation failed.',
            SCENE_EMBEDDING_FAILED:'Scene embeddings could not be prepared.',
            SCENE_INDEX_MEDIA_INVALID:'The stored media could not be validated for indexing.',
            SCENE_INDEX_WRITE_FAILED:'The scene search index could not be written or verified.',
        };
        el('video-index-status').textContent = status === 'INDEXED' ? 'Scenes are indexed and searchable.' :
            status === 'FAILED' ? (explanations[errorCode] || 'Scene indexing failed.') + ' Video playback is still available. Retry indexing after resolving the service issue.' :
            status === 'PENDING' ? 'Scene indexing is in progress. Refresh details or retry reconciliation later.' : 'Scenes have not been indexed.';
        el('retry-video-index').disabled = !['FAILED','PENDING','NOT_REQUESTED'].includes(String(status));
    }

    /** @param {Row} lesson */
    function setupEducationalVideoState(lesson) {
        const video = lesson.video ? row(lesson.video) : null;
        const id = text(lesson, 'lesson_id');
        el('video-grounded').disabled = !lesson.source_id;
        const params = new URLSearchParams(window.location.search);
        const linkedGeneration = initialVideoLink && params.get('lesson') === id ? params.get('generation') : null;
        initialVideoLink = false;
        if (linkedGeneration || (video && video.status === 'COMPLETED')) {
            const ticket = videoGeneration;
            if (linkedGeneration) switchLessonTab('video');
            void playEducationalVideo(id, ticket, linkedGeneration || (typeof video?.job_id === 'string' ? video.job_id : ''), linkedGeneration ? params.get('scene') || '' : '').catch(error => {
                if (ticket === videoGeneration) el('video-status').textContent = error instanceof Error ? error.message : 'Video playback is unavailable.';
            });
        } else if (video && !['FAILED', 'NOT_STARTED'].includes(String(video.status))) {
            pollVideoStatus(id);
        } else {
            el('video-status').textContent = video?.status === 'FAILED' ? 'The previous render failed. You can retry video generation.' : 'Generate an animated, narrated video for this lesson.';
            el('start-video-btn').textContent = 'Generate Educational Video';
        }
    }

    /** @param {string} lessonId */
    async function startEducationalVideo(lessonId, regenerate = false) {
        const ticket = videoGeneration;
        const startBtn = /** @type {HTMLButtonElement} */ (el('start-video-btn'));
        startBtn.disabled = true;
        el('regenerate-video-btn').disabled = true;
        el('video-status').textContent = 'Starting video generation pipeline…';
        try {
            const selectedDifficulty = el('video-difficulty').value;
            const selectedSeconds = Number(el('video-duration').value);
            const status = row(await post('/educational-content/' + encodeURIComponent(lessonId) + '/video', {
                regenerate, target_seconds: Number.isFinite(selectedSeconds) && selectedSeconds >= 20 ? selectedSeconds : 45,
                difficulty: ['foundational','intermediate','advanced'].includes(selectedDifficulty) ? selectedDifficulty : 'intermediate',
                grounded: !!el('video-grounded').checked && !el('video-grounded').disabled,
                instructions: String(el('video-instructions').value || '').slice(0, 1000),
            }));
            if (ticket !== videoGeneration) return;
            if (status.status === 'COMPLETED') {
                await playEducationalVideo(lessonId, ticket, typeof status.job_id === 'string' ? status.job_id : '');
                startBtn.disabled = false;
            } else pollVideoStatus(lessonId);
        } catch (error) {
            if (ticket !== videoGeneration) return;
            el('video-status').textContent = error instanceof Error ? error.message : 'Failed to start video.';
            startBtn.disabled = false;
            el('regenerate-video-btn').disabled = false;
        }
    }

    /** @param {string} lessonId */
    function pollVideoStatus(lessonId) {
        if (videoPollInterval) clearInterval(videoPollInterval);
        const ticket = videoGeneration;
        const startBtn = /** @type {HTMLButtonElement} */ (el('start-video-btn'));
        startBtn.disabled = true;
        let pending = false;
        let polls = 0;
        const check = async () => {
            if (pending || ticket !== videoGeneration) return;
            pending = true;
            try {
                if (++polls > MAX_JOB_POLLS) throw new Error('Video is still processing. Reopen this lesson to check its status.');
                const status = row(await api('/educational-content/' + encodeURIComponent(lessonId) + '/video/status'));
                if (ticket !== videoGeneration) return;
                const state = text(status, 'status');
                if (!['QUEUED', 'PLANNING', 'GENERATING_AUDIO', 'ALIGNING', 'RENDERING', 'COMPOSITING', 'COMPLETED', 'FAILED', 'NOT_STARTED'].includes(state)) throw new Error('Unexpected video status. Please retry.');
                el('video-status').textContent = 'Rendering video: ' + text(status, 'stage') + ' (' + Number(status.progress || 0) + '%)…';
                if (['COMPLETED', 'FAILED', 'NOT_STARTED'].includes(state)) {
                    if (videoPollInterval) clearInterval(videoPollInterval);
                    videoPollInterval = null;
                    startBtn.disabled = false;
                    el('regenerate-video-btn').disabled = false;
                    if (state === 'COMPLETED') await playEducationalVideo(lessonId, ticket, typeof status.job_id === 'string' ? status.job_id : '');
                    else el('video-status').textContent = state === 'FAILED' ? (status.error_code === 'VIDEO_AUDIO_FAILED' ? 'Spoken narration could not be generated. Check the voice service and retry.' : 'Video generation failed. Please retry.') : 'Video generation has not started.';
                }
            } catch (error) {
                if (ticket !== videoGeneration) return;
                if (videoPollInterval) clearInterval(videoPollInterval);
                videoPollInterval = null;
                startBtn.disabled = false;
                el('regenerate-video-btn').disabled = false;
                el('video-status').textContent = error instanceof Error ? error.message : 'Failed checking video progress.';
            } finally { pending = false; }
        };
        videoPollInterval = setInterval(() => { void check(); }, POLL_INTERVAL_MS);
        void check();
    }

    async function askEducationalLesson() {
        if (!currentEducationalLesson) return;
        const selected = currentEducationalLesson;
        const input = /** @type {HTMLTextAreaElement} */ (el('question'));
        const question = input.value.trim();
        if (!question) { el('ask-status').textContent = 'Enter a question first.'; return; }

        const status = el('ask-status');
        const button = /** @type {HTMLButtonElement} */ (el('ask-button'));
        const output = el('answer');

        button.disabled = true;
        status.textContent = 'Generating educational response…';
        try {
            const res = row(await post('/educational-content/' + encodeURIComponent(text(selected, 'lesson_id')) + '/ask', { question }));
            if (selected !== currentEducationalLesson) return;
            const turn = document.createElement('article');
            turn.className = 'ask-turn';
            turn.append(node('h3', 'You'), node('p', question), node('h3', 'VisualAI'), node('p', 'AI-enriched supplemental explanation', 'ask-evidence-status'), node('p', text(res, 'answer'), 'ask-answer'));
            const citations = rows(res.citations || []);
            if (citations.length > MAX_CITATIONS) throw new Error('Invalid citations');
            if (citations.length) {
                const list = node('ul', '', 'ask-citations');
                for (const citation of citations) {
                    if (!selected.source_id || citation.source_id !== selected.source_id || citation.source_version !== selected.source_version || citation.verified !== true) throw new Error('Invalid citation scope');
                    const label = text(citation, 'location');
                    const quote = text(citation, 'quote');
                    if (!label.trim() || label.length > MAX_CITATION_LOCATION_CHARS || quote.length > MAX_QUESTION_CHARS) throw new Error('Invalid citation');
                    list.append(node('li', label + ' · Version ' + citation.source_version + ' — ' + quote));
                }
                turn.append(node('h4', 'Source observations'), list);
            }
            const keyPoints = strings(res.key_points || []);
            if (keyPoints.length) {
                const kpUl = document.createElement('ul');
                for (const kp of keyPoints) kpUl.append(node('li', kp));
                turn.append(node('h4', 'Key Concepts'), kpUl);
            }
            output.prepend(turn);
            status.textContent = '';
            input.value = '';
        } catch (e) {
            if (selected === currentEducationalLesson) status.textContent = e instanceof Error ? e.message : 'Failed to ask question.';
        } finally {
            if (selected === currentEducationalLesson) button.disabled = false;
        }
    }

    /** @param {string} lessonId */
    async function openEducationalLesson(lessonId) {
        const ticket = ++navigation;
        resetEducationalVideo();
        notesUI.setSession(null); askUI.setSession(null); practiceUI.setSession(null);
        show('session');
        session = null;
        currentEducationalLesson = null;
        if (videoPollInterval) { clearInterval(videoPollInterval); videoPollInterval = null; }

        switchLessonTab('learn');

        el('session-title').textContent = 'Loading your educational lesson…';
        el('concept-cards').replaceChildren();
        el('session-state').textContent = 'LOADING';

        const lesson = row(await api('/educational-content/' + encodeURIComponent(lessonId)));
        if (ticket !== navigation) return;
        currentEducationalLesson = lesson;
        notesUI.setTopic(true);
        el('mastery-content').replaceChildren();
        el('ask-status').textContent = 'Ask a follow-up question about this lesson.';

        const topic = typeof lesson.topic === 'string' ? lesson.topic : 'Educational Lesson';
        el('session-source').textContent = typeof lesson.source_id === 'string' ? ('Uploaded learning material · version ' + Number(lesson.source_version)) : 'Independent Topic Lesson';
        el('session-title').textContent = topic;
        el('session-subtitle').textContent = 'Interactive AI-generated lesson: explanation, notes, flowcharts, assessments, and video';
        el('session-state').textContent = typeof lesson.status === 'string' ? lesson.status : 'READY';
        el('new-version').hidden = true;

        for (const name of [
            'learn-tab', 'notes-tab', 'diagram-tab', 'practice-tab', 'video-tab',
            'generate-notes', 'notes-detail', 'generate-diagram', 'start-practice', 'start-video-btn',
            'ask-button'
        ]) {
            const btn = document.getElementById(name);
            if (btn && 'disabled' in btn) btn.disabled = false;
        }
        /** @type {HTMLTextAreaElement} */ (el('question')).disabled = false;

        const teaching = row(lesson.content || lesson.teaching || lesson);
        el('concept-cards').replaceChildren();

        const overviewBlock = node('article', '', 'concept');
        overviewBlock.append(node('h3', 'Core Explanation'));
        overviewBlock.append(node('p', typeof teaching.explanation === 'string' ? teaching.explanation : ''));
        el('concept-cards').append(overviewBlock);

        for (const [key, title] of [['mathematical_notation', 'Mathematical Notation'], ['common_misconceptions', 'Common Misconceptions']]) {
            const entries = teaching[key];
            if (!Array.isArray(entries) || !entries.length) continue;
            const section = node('article', '', 'concept');
            section.append(node('h3', title));
            const list = document.createElement('ul');
            for (const entry of entries) {
                const value = typeof entry === 'string' ? entry : key === 'mathematical_notation'
                    ? text(row(entry), 'symbol') + ': ' + text(row(entry), 'meaning')
                    : text(row(entry), 'misconception') + ' — ' + text(row(entry), 'correction');
                list.append(node('li', value));
            }
            section.append(list);
            el('concept-cards').append(section);
        }

        const concepts = rows(teaching.key_concepts || []);
        if (concepts.length) {
            const conceptsSection = node('article', '', 'concept');
            conceptsSection.append(node('h3', 'Key Concepts'));
            const list = document.createElement('ul');
            for (const c of concepts) {
                const li = document.createElement('li');
                const strong = document.createElement('strong');
                strong.textContent = typeof c.name === 'string' ? c.name : 'Concept';
                li.append(strong, ': ' + (typeof c.explanation === 'string' ? c.explanation : ''));
                list.append(li);
            }
            conceptsSection.append(list);
            el('concept-cards').append(conceptsSection);
        }

        const examples = strings(teaching.examples || []);
        if (examples.length) {
            const exSection = node('article', '', 'concept');
            exSection.append(node('h3', 'Worked Examples'));
            const list = document.createElement('ul');
            for (const ex of examples) {
                const li = document.createElement('li');
                li.textContent = ex;
                list.append(li);
            }
            exSection.append(list);
            el('concept-cards').append(exSection);
        }

        const equations = strings(teaching.equations || []);
        if (equations.length) {
            const eqSection = node('article', '', 'concept');
            eqSection.append(node('h3', 'Key Equations & Formulas'));
            const list = document.createElement('ul');
            for (const eq of equations) {
                const li = document.createElement('li');
                li.textContent = eq;
                list.append(li);
            }
            eqSection.append(list);
            el('concept-cards').append(eqSection);
        }

        if (lesson.notes) {
            renderEducationalNotes(row(lesson.notes));
            const savedDetail = row(lesson.notes).detail_level;
            if (['concise','standard','detailed'].includes(savedDetail)) /** @type {HTMLSelectElement} */ (el('notes-detail')).value = savedDetail;
            el('notes-status').textContent = 'Saved study notes loaded.';
        } else {
            el('notes-content').replaceChildren();
            el('notes-status').textContent = 'Click "Generate Notes" to create comprehensive structured notes.';
        }

        if (lesson.diagram) {
            renderEducationalDiagram(row(lesson.diagram));
        } else {
            el('diagram-content').replaceChildren();
            el('diagram-status').textContent = 'Click "Generate Diagram" to render an algorithmic flowchart.';
        }

        if (lesson.assessment) {
            renderEducationalAssessment(row(lesson.assessment));
        } else {
            el('practice-content').replaceChildren();
            el('practice-status').textContent = 'Click "Start assessment" to test your knowledge with MCQs and descriptive questions.';
        }

        setupEducationalVideoState(lesson);
        history.replaceState(null, '', '/dashboard?lesson=' + encodeURIComponent(lessonId));
    }

    async function loadSources() {
        const ticket = ++navigation; show('sources'); session = null; currentEducationalLesson = null;
        history.replaceState(null, '', '/dashboard');
        if (videoPollInterval) { clearInterval(videoPollInterval); videoPollInterval = null; }
        notesUI.setSession(null); askUI.setSession(null); practiceUI.setSession(null);
        el('source-cards').replaceChildren(node('p', 'Loading your material…', 'muted'));
        sources = rows(row(await api('/sources')).sources).sort((a, b) => String(b.created_at || b.uploaded_at || '').localeCompare(String(a.created_at || a.uploaded_at || ''))).map(decodeSource);
        if (ticket !== navigation) return;
        el('source-cards').replaceChildren();
        el('source-count').textContent = 'My sources (' + sources.length + ')';
        analysis.sources(sources.slice(0,5));
        for (const item of sources.slice(0,5)) if(item.analysis && item.analysis.is_finished!==true) void trackAnalysis(item.source_id+':'+item.version,row(item.analysis));
        await restoreAnalysisJobs();
        if (ticket !== navigation) return;
        if (!sources.length) el('source-cards').append(node('p', 'Your learning space is ready. Add your first source above.', 'muted'));
        for (const item of sources) {
            if (analysis.hasSource(item.source_id,item.version)) continue;
            const card = node('article', '', 'card');
            const isReady = item.status === 'READY';
            const isContentReady = item.content_ready || item.status === 'CONTENT_READY' || isReady;
            card.append(node('span', isContentReady && !isReady ? 'CONTENT_READY' : item.status, 'badge'), node('h3', item.filename), node('p', 'Version ' + item.version, 'muted'));
            if (isContentReady) {
                card.append(button('Learn with VisualAI', async () => {
                    el('status').textContent = 'Preparing lesson for ' + item.filename + '…';
                    const res = row(await post('/educational-content', { source_id: item.source_id, source_version: item.version }));
                    await openEducationalLesson(text(res, 'content_id'));
                }));
            }
            if (isReady) {
                card.append(button('Prepare source search', () => prepareSourceSearch(item)));
                card.append(button('Explore topics', () => openSource(item, item.version)));
            }
            el('source-cards').append(card);
        }
        el('session-cards').replaceChildren(node('p', 'Loading your sessions…', 'muted'));
        try {
            const saved = rows(await api('/learning-sessions'));
            let educationalLessons = [];
            try {
                const edRes = row(await api('/educational-content'));
                educationalLessons = rows(edRes.lessons);
            } catch {
                educationalLessons = [];
            }
            if (ticket !== navigation) return;
            el('session-cards').replaceChildren();
            // Recent materials are shown once, directly beneath the analysis panel.

            if (!saved.length && !educationalLessons.length) {
                el('session-cards').append(node('p', 'Enter a topic above or choose a source to start learning.', 'muted'));
            }
            for (const ed of educationalLessons) {
                const card = node('article', '', 'card');
                const topicText = typeof ed.topic === 'string' ? ed.topic : 'Untitled Lesson';
                const statusText = typeof ed.status === 'string' ? ed.status : 'READY';
                const lessonId = typeof ed.lesson_id === 'string' ? ed.lesson_id : (typeof ed.content_id === 'string' ? ed.content_id : '');
                card.append(node('span', 'AI LESSON', 'badge'), node('h3', topicText), node('p', 'Status: ' + statusText, 'muted'));
                if (lessonId) {
                    card.append(button('Open lesson', () => openEducationalLesson(lessonId)));
                }
                el('session-cards').append(card);
            }
            for (const s of saved) {
                const card = node('article', '', 'card');
                const title = sources.find(v => v.source_id === s.source_id)?.filename || 'Your learning material';
                card.append(node('h3', title), node('p', text(s, 'state') + ' · Version ' + s.source_version, 'muted'));
                card.append(button(s.state === 'ACTIVE' ? 'Resume learning' : 'View session', () => openSession(text(s, 'session_id'), s.state === 'ACTIVE')));
                el('session-cards').append(card);
            }
        } catch (error) {
            if (ticket === navigation) el('session-cards').replaceChildren(node('p', error instanceof Error ? error.message : 'Sessions unavailable.', 'muted'));
        }
    }

    /** @param {Source} item @param {number} version */
    async function openSource(item, version) {
        const ticket = ++navigation; source = item; session = null; currentEducationalLesson = null;
        notesUI.setSession(null); askUI.setSession(null); practiceUI.setSession(null); knowledge = null; show('explorer');
        el('explorer-title').textContent = item.filename;
        el('source-location').textContent = 'YOUR MATERIAL · VERSION ' + version;
        el('readiness').textContent = 'Loading your knowledge map…'; el('topic-cards').replaceChildren();
        const map = row(await api('/sources/' + encodeURIComponent(item.source_id) + '/versions/' + version + '/knowledge'));
        if (ticket !== navigation) return;
        knowledge = map; el('readiness').textContent = readiness(map.knowledge_state);
        history.replaceState(null, '', '/dashboard?source=' + encodeURIComponent(item.source_id) + '&version=' + version);
        if (map.knowledge_state !== 'READY') {
            if (map.knowledge_state === 'FAILED') el('topic-cards').append(button('Retry analysis', async () => {
                await post('/sources/' + encodeURIComponent(item.source_id) + '/retry-index'); await openSource(item, version);
            }));
            return;
        }
        const topics = rows(map.topics);
        const conceptCount = /** @param {Row} topic */(topic) => rows(topic.subtopics).reduce((count, sub) => count + rows(sub.concepts).length, 0);
        for (const topic of topics.sort((a, b) => conceptCount(b) - conceptCount(a))) {
            const details = document.createElement('details'); const subs = rows(topic.subtopics);
            details.append(node('summary', text(topic, 'title')));
            details.append(node('p', subs.length + ' subtopics · ' + subs.reduce((n, s) => n + rows(s.concepts).length, 0) + ' concepts', 'muted'));
            details.append(button('Focus on this topic', () => createSession(item, version, text(topic, 'topic_id'), null)));
            for (const sub of subs) {
                const block = node('div', '', 'subtopic'); block.append(node('h3', text(sub, 'title')));
                const list = document.createElement('ul'); list.className = 'concept-list';
                for (const concept of rows(sub.concepts)) {
                    const evidence = rows(concept.evidence);
                    list.append(node('li', text(concept, 'name') + ' · ' + evidence.length + ' evidence references' + (strings(concept.prerequisite_concept_ids).length ? ' · has prerequisites' : '')));
                    if (evidence.length) list.lastElementChild?.append(node('span', ' · ' + evidence.map(e => location(row(e.content))).join(' · '), 'muted'));
                }
                block.append(list, button('Learn this subtopic', () => createSession(item, version, text(topic, 'topic_id'), text(sub, 'subtopic_id')))); details.append(block);
            }
            el('topic-cards').append(details);
        }
    }

    /** @param {Source} item @param {number} version @param {string} topic @param {string|null} sub */
    async function createSession(item, version, topic, sub) {
        el('status').textContent = 'Creating your focused learning session…';
        const created = row(await post('/learning-sessions', { session_id: crypto.randomUUID(), source_id: item.source_id, source_version: version, topic_id: topic, subtopic_id: sub }));
        await openSession(text(created, 'session_id'), false);
    }

    /** @param {string} id @param {boolean} resume */
    async function openSession(id, resume) {
        resetEducationalVideo();
        currentEducationalLesson = null;
        const ticket = ++navigation; show('session'); session = null; currentEducationalLesson = null;
        notesUI.setSession(null); askUI.setSession(null); practiceUI.setSession(null);
        switchLessonTab('learn');
        el('session-title').textContent = 'Loading your focused session…'; el('concept-cards').replaceChildren();
        if (resume) await post('/learning-sessions/' + encodeURIComponent(id) + '/resume');
        const view = row(await api('/learning-sessions/' + encodeURIComponent(id)));
        if (ticket !== navigation) return;
        const loadedSession = row(view.session);
        const loadedSource = sources.find(s => s.source_id === loadedSession.source_id) || decodeSource(row(await api('/sources/' + encodeURIComponent(text(loadedSession, 'source_id')))));
        if (ticket !== navigation) return;
        session = loadedSession; source = loadedSource;
        notesUI.setSession(session); askUI.setSession(session); practiceUI.setSession(session, rows(view.concepts));
        const version = session.source_version;
        el('session-source').textContent = source.filename + ' · Version ' + version;
        el('session-title').textContent = text(view, 'topic_title');
        el('session-subtitle').textContent = typeof view.subtopic_title === 'string' ? view.subtopic_title : 'All concepts in this topic';
        el('session-state').textContent = text(session, 'state');
        el('new-version').hidden = !(typeof version === 'number' && source.version > version);
        for (const name of ['ask-button', 'complete-session', 'abandon-session']) /** @type {HTMLButtonElement} */ (el(name)).disabled = session.state !== 'ACTIVE';
        const concepts = rows(view.concepts);
        for (const c of concepts) {
            const block = node('article', '', 'concept'); block.append(node('h3', text(c, 'name')));
            if (typeof c.definition === 'string') block.append(node('p', c.definition));
            const prerequisites = strings(c.prerequisite_concept_ids);
            if (prerequisites.length) block.append(node('p', 'Builds on: ' + prerequisites.map(id => concepts.find(v => v.concept_id === id)?.name || 'a prerequisite in your source').join(', '), 'muted'));
            block.append(node('p', rows(c.evidence).map(e => location(row(e.content))).join(' · '), 'muted'));
            const explain = button('Explain this', async () => {
                /** @type {HTMLTextAreaElement} */ (el('question')).value = 'What is ' + text(c, 'name') + '?';
                await ask(text(c, 'concept_id'));
            }); explain.disabled = session.state !== 'ACTIVE'; block.append(explain); el('concept-cards').append(block);
        }
        history.replaceState(null, '', '/dashboard?session=' + encodeURIComponent(id));
    }

    /** @param {string} [concept] */
    async function ask(concept) {
        await askUI.ask(concept);
    }

    /** @param {'complete'|'abandon'} action */
    async function transition(action) {
        if (!session) return;
        const id = text(session, 'session_id'); await post('/learning-sessions/' + encodeURIComponent(id) + '/' + action); await openSession(id, false);
    }

    // Tab buttons
    el('learn-tab').addEventListener('click', () => switchLessonTab('learn'));
    el('notes-tab').addEventListener('click', () => switchLessonTab('notes'));
    el('diagram-tab').addEventListener('click', () => switchLessonTab('diagram'));
    el('practice-tab').addEventListener('click', () => switchLessonTab('practice'));
    el('video-tab').addEventListener('click', () => switchLessonTab('video'));

    // Generation triggers
    el('generate-notes').addEventListener('click', () => run(async () => {
        if (!currentEducationalLesson) return;
        const selected = currentEducationalLesson;
        const detail = /** @type {HTMLSelectElement} */ (el('notes-detail'));
        const generate = /** @type {HTMLButtonElement} */ (el('generate-notes'));
        generate.disabled = true; detail.disabled = true;
        el('notes-content').replaceChildren();
        el('notes-status').textContent = 'Generating comprehensive structured notes…';
        try {
            const res = row(await post('/educational-content/' + encodeURIComponent(text(selected, 'lesson_id')) + '/notes', {detail_level: detail.value, regenerate: true}));
            if (selected !== currentEducationalLesson) return;
            renderEducationalNotes(row(res.notes || res));
            el('notes-status').textContent = 'Structured educational notes ready.';
        } catch (error) {
            if (selected === currentEducationalLesson) el('notes-status').textContent = error instanceof Error ? error.message : 'Notes generation failed.';
        } finally { if (selected === currentEducationalLesson) { generate.disabled = false; detail.disabled = false; } }
    }));

    el('generate-diagram').addEventListener('click', () => run(async () => {
        if (!currentEducationalLesson) return;
        const selected = currentEducationalLesson;
        const generate = /** @type {HTMLButtonElement} */ (el('generate-diagram'));
        generate.disabled = true;
        diagramExport = ''; diagramScope = null; el('diagram-content').replaceChildren();
        el('diagram-status').textContent = 'Generating algorithmic flowchart diagram…';
        try {
            const res = row(await post('/educational-content/' + encodeURIComponent(text(selected, 'lesson_id')) + '/diagram', {regenerate:true}));
            if (selected !== currentEducationalLesson) return;
            renderEducationalDiagram(row(res.diagram || res));
            el('diagram-status').textContent = 'Flowchart diagram rendered.';
        } catch (error) {
            if (selected === currentEducationalLesson) el('diagram-status').textContent = error instanceof Error ? error.message : 'Flowchart generation failed.';
        } finally { if (selected === currentEducationalLesson) generate.disabled = false; }
    }));

    el('start-practice').addEventListener('click', () => run(async () => {
        if (!currentEducationalLesson) return;
        const selected = currentEducationalLesson;
        const start = /** @type {HTMLButtonElement} */ (el('start-practice'));
        start.disabled = true;
        el('practice-status').textContent = 'Generating practice assessment questions…';
        try {
            const res = row(await post('/educational-content/' + encodeURIComponent(text(selected, 'lesson_id')) + '/assessment'));
            if (selected !== currentEducationalLesson) return;
            renderEducationalAssessment(row(res.assessment || res));
            el('practice-status').textContent = 'Assessment questions ready.';
        } catch (error) {
            if (selected === currentEducationalLesson) el('practice-status').textContent = error instanceof Error ? error.message : 'Assessment generation failed.';
        } finally { if (selected === currentEducationalLesson) start.disabled = false; }
    }));

    el('start-video-btn').addEventListener('click', () => run(async () => {
        if (!currentEducationalLesson) return;
        await startEducationalVideo(text(currentEducationalLesson, 'lesson_id'));
    }));
    el('regenerate-video-btn').addEventListener('click', () => run(async () => {
        if (!currentEducationalLesson) return;
        await startEducationalVideo(text(currentEducationalLesson, 'lesson_id'), true);
    }));
    el('retry-video-index').addEventListener('click', () => run(async () => {
        const selected = displayedVideo;
        if (!selected || selected.ticket !== videoGeneration) return;
        el('retry-video-index').disabled = true;
        try {
            const result = row(await post('/educational-content/' + encodeURIComponent(selected.lessonId) +
                '/video/reindex?generation_id=' + encodeURIComponent(selected.generationId), {}));
            if (selected.ticket === videoGeneration) showVideoIndexStatus(result.indexing_status, result.error_code);
        } catch (error) {
            if (selected.ticket !== videoGeneration) return;
            el('video-index-status').textContent = error instanceof Error ? error.message : 'Scene indexing is unavailable.';
            el('retry-video-index').disabled = false;
        }
    }));
    el('video-scene-search-form').addEventListener('submit', event => {
        event.preventDefault();
        const query = String(el('video-scene-search').value || '').trim();
        if (!query) return;
        const ticket = videoGeneration;
        run(async () => {
            const result = row(await api('/educational-content/video-scenes/search?query=' + encodeURIComponent(query)));
            if (ticket !== videoGeneration) return;
            const container = el('video-scene-search-results'); container.replaceChildren();
            const scenes = Array.isArray(result.scenes) ? result.scenes : [];
            if (!scenes.length) container.textContent = 'No matching indexed video scenes.';
            for (const value of scenes) {
                const scene = row(value); const link = document.createElement('a');
                link.textContent = text(scene, 'title');
                link.href = '/learn?lesson=' + encodeURIComponent(text(scene, 'lesson_id')) +
                    '&generation=' + encodeURIComponent(text(scene, 'generation_id')) + '&scene=' + encodeURIComponent(text(scene, 'scene_id'));
                container.append(link);
            }
        });
    });

    // Topic direct learning
    const topicForm = document.getElementById('topic-form');
    if (topicForm) {
        topicForm.addEventListener('submit', e => {
            e.preventDefault();
            const input = /** @type {HTMLInputElement} */ (document.getElementById('topic-input'));
            const topic = input ? input.value.trim() : '';
            if (!topic) return;
            run(async () => {
                el('status').textContent = 'Creating educational lesson for "' + topic + '"…';
                const res = row(await post('/educational-content', { topic }));
                await openEducationalLesson(text(res, 'content_id'));
            });
        });
    }

    el('sources-nav').addEventListener('click', () => run(loadSources));
    el('explorer-back').addEventListener('click', () => run(loadSources));
    el('session-back').addEventListener('click', () => run(async () => {
        if (currentEducationalLesson) {
            currentEducationalLesson = null;
            await loadSources();
        } else if (source && session && typeof session.source_version === 'number') {
            await openSource(source, session.source_version);
        } else {
            await loadSources();
        }
    }));
    el('logout').addEventListener('click', () => run(auth.logout));
    el('ask-form').addEventListener('submit', e => {
        e.preventDefault();
        if (currentEducationalLesson) {
            run(askEducationalLesson);
        } else {
            run(() => ask());
        }
    });
    el('ask-nav').addEventListener('click', () => {
        switchLessonTab('learn');
        el('question').focus();
    });
    el('complete-session').addEventListener('click', () => run(() => transition('complete')));
    el('abandon-session').addEventListener('click', () => run(() => transition('abandon')));
    function exportText(resource,format) {
        const scope=currentEducationalLesson || session;
        const status=el(resource+'-export-status');
        try {
            if(!scope || el('session-panel').hidden) throw new Error('Open your learning resource before downloading.');
            const content=el(resource==='lesson'?'concept-cards':'notes-content');
            const result=resources.serialize(content,format==='md');
            const topic=el('session-title').textContent || 'lesson';
            const body=resource==='lesson'?(format==='md'?'# ':'')+topic+'\n\n'+result:result;
            resources.download(document,new Blob([body],{type:format==='md'?'text/markdown;charset=utf-8':'text/plain;charset=utf-8'}),resources.filename(topic,resource,format));
            status.textContent='Download started.';
        } catch(error) {status.textContent=error instanceof Error?error.message:'Download failed. Please try again.';}
    }
    for(const [id,resource,format] of [['download-notes-md','notes','md'],['download-notes-txt','notes','txt'],['download-lesson-md','lesson','md']]) {
        el(id).addEventListener('click',()=>exportText(resource,format));
    }
    for(const format of ['svg','png']) el('download-diagram-'+format).addEventListener('click',async()=>{
        const status=el('diagram-export-status');const svg=diagramExport,scope=diagramScope;
        const control=/** @type {HTMLButtonElement} */(el('download-diagram-'+format));control.disabled=true;
        try {
            if(!svg || !scope || scope!==currentEducationalLesson || el('session-panel').hidden) throw new Error('Generate a valid flowchart before downloading.');
            const topic=el('session-title').textContent || 'lesson';
            const blob=format==='svg'?new Blob([svg],{type:'image/svg+xml;charset=utf-8'}):await resources.png(svg);
            if(scope!==currentEducationalLesson || svg!==diagramExport) return;
            resources.download(document,blob,resources.filename(topic,'flowchart',format));status.textContent='Download started.';
        } catch(error) {if(scope===diagramScope)status.textContent=error instanceof Error?error.message:'Flowchart export failed. Download SVG instead.';}
        finally {control.disabled=false;}
    });
    const uploadStatus = createUploadStatus(el('upload-status'));
    const activeAnalysisJobs = new Set();
    let jobsRestored = false;
    function savedAnalysisJobs() {
        try {const ids=JSON.parse(window.sessionStorage.getItem('visualai-analysis-jobs') || '[]');return Array.isArray(ids)?ids.filter(id=>typeof id==='string' && /^JOB_[a-zA-Z0-9_-]+$/.test(id)).slice(-8):[];}catch{return [];}
    }
    function rememberAnalysisJob(id) {
        try {window.sessionStorage.setItem('visualai-analysis-jobs',JSON.stringify([...new Set([...savedAnalysisJobs(),id])].slice(-8)));}catch{/* Storage may be disabled; polling still works. */}
    }
    async function restoreAnalysisJobs() {
        if(jobsRestored)return;jobsRestored=true;
        await Promise.all(savedAnalysisJobs().map(async id=>{
            try {
                const job=row(await api('/pipeline/jobs/'+encodeURIComponent(id)));
                const key=analysis.update(id,job,job.status==='failed'?sourceJobFailure(job.failure):'');
                if(job.is_finished!==true) void trackAnalysis(key,job);
            } catch {/* Another account's or expired jobs never render. */}
        }));
    }
    async function trackAnalysis(initialKey,initialJob) {
        const jobId=text(initialJob,'job_id');if(activeAnalysisJobs.has(jobId))return;
        activeAnalysisJobs.add(jobId);rememberAnalysisJob(jobId);let key=initialKey;
        try {
            for(let i=0;i<MAX_JOB_POLLS;i++) {
                const current=row(await api('/pipeline/jobs/'+encodeURIComponent(jobId)));
                uploadStatus.progress(current);
                const message=current.is_finished===true?(current.status==='completed'?'':sourceJobFailure(current.failure)):el('upload-status').textContent;
                key=analysis.update(key,current,message);
                if(current.is_finished===true) {
                    if(current.status!=='completed'){uploadStatus.fail(current.failure);return;}
                    uploadStatus.progress({current_stage:row(current.result).content_ready===true?'content_ready':'source_ready',result:current.result});
                    if(!el('sources-panel').hidden) {
                        try{await loadSources();}catch{el('status').textContent='Your material was saved. Refresh the source list to open it.';}
                    }return;
                }
                await new Promise(resolve=>setTimeout(resolve,POLL_INTERVAL_MS));
            }
            throw new Error('Analysis is still running. Refresh your sources before retrying.');
        }catch(error){uploadStatus.error(error);analysis.error(key,el('upload-status').textContent);}
        finally{activeAnalysisJobs.delete(jobId);}
    }
    el('upload-form').addEventListener('submit', e => {
        e.preventDefault(); (async () => {
            const file = /** @type {HTMLInputElement} */ (el('upload-file')).files?.[0]; if (!file) return;
            const b = /** @type {HTMLButtonElement} */ (el('upload-button')); if(b.disabled)return;b.disabled = true;
            uploadStatus.start();
            const key=analysis.begin(file);
            const body = new FormData(); body.append('file', file);
            try {
                const job = row(await api('/pipeline/upload-and-assess', { method: 'POST', body }));
                await trackAnalysis(key,job);
            } catch (error) {uploadStatus.error(error);analysis.error(key,el('upload-status').textContent,true);} finally { b.disabled = false; }
        })();
    });
    async function initializeLearning() {
        const profileUI = Reflect.get(window,'VisualAILearningProfile');
        if(profileUI) {
            el('profile-gate-status').textContent='Checking your learning profile…';
            el('profile-gate-retry').hidden=true;
            let profile;
            try {profile=await profileUI.ensure(auth);}
            catch {el('profile-gate-status').textContent='Could not load your learning profile. Please retry.';el('profile-gate-retry').hidden=false;return;}
            if(!profile)return;
            el('profile-summary').textContent=profile.preferences.personalization_enabled?
                'Learning examples personalized for: '+profile.preferences.interested_domains.map(v=>v==='Other'?profile.preferences.custom_interest:v).join(', ')+'.':
                'Conventional explanations selected. You can edit this in Learning profile.';
            el('profile-gate-status').hidden=true;
        }
        el('learning-main').hidden=false;
        const params = new URLSearchParams(window.location.search);
        if (params.has('lesson')) {
            await openEducationalLesson(params.get('lesson') || '');
        } else if (params.has('session')) {
            await openSession(params.get('session') || '', false);
        } else {
            await loadSources();
            const selected = sources.find(s => s.source_id === params.get('source'));
            const version = Number(params.get('version'));
            if (selected && Number.isInteger(version) && version > 0) await openSource(selected, version);
        }
    }
    el('profile-gate-retry').addEventListener('click',()=>run(initializeLearning));
    run(initializeLearning);
})();
