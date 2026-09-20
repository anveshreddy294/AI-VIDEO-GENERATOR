// Exercise the actual dashboard tracker without a browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../../app/api/dashboard.py'), 'utf8');
const code = html.slice(html.indexOf('        let stopJobTracking'), html.indexOf('        async function runUpload'));

async function scenario(responses, cancel = false) {
    const timers = new Map();
    let next = 0, completed = 0, errors = 0, calls = 0, stream;
    const context = {
        activeEventSource: null, timelineTimerInterval: null,
        clearInterval() {}, updateTimelineEvent() {},
        setTimeout(fn) { timers.set(++next, fn); return next; },
        clearTimeout(id) { timers.delete(id); },
        AbortSignal: {timeout() {}},
        EventSource: class { constructor() { stream = this; } close() {} },
        async fetch() {
            const response = responses[Math.min(calls++, responses.length - 1)];
            if (response instanceof Error) throw response;
            return {ok: true, async json() { return response; }};
        },
        onComplete() { completed++; }, onError() { errors++; },
    };
    vm.createContext(context);
    vm.runInContext(code + '\ntrackJobSSE("job", onComplete, onError);', context);
    stream.onerror();
    if (cancel) vm.runInContext('stopJobTracking();', context);
    for (let i = 0; timers.size && i < 12; i++) {
        const [id, fn] = timers.entries().next().value;
        timers.delete(id);
        await fn();
    }
    return {completed, errors, calls, timers: timers.size};
}
(async () => {
    assert.deepEqual(await scenario([{status: 'running'}, {status: 'completed'}]),
        {completed: 1, errors: 0, calls: 2, timers: 0});
    assert.deepEqual(await scenario([new Error('offline')]),
        {completed: 0, errors: 1, calls: 5, timers: 0});
    assert.deepEqual(await scenario([{status: 'running'}], true),
        {completed: 0, errors: 0, calls: 0, timers: 0});
    assert.deepEqual(await scenario([{status: 'failed', error: 'ingestion failed'}]),
        {completed: 0, errors: 1, calls: 1, timers: 0});
    console.log('4 dashboard progress recovery scenarios passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
