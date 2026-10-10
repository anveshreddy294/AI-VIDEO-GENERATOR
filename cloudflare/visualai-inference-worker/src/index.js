// @ts-check
/** @typedef {Record<string, unknown>} Row */
/** @typedef {{role:string,content:string}} Message */
/** @typedef {import('./visual.js').VisualEnv & {API_KEY?:string,TEXT_TIMEOUT_MS?:string,TEXT_GENERAL_MODEL?:string,TEXT_STRUCTURED_MODEL?:string}} Env */
import {handleVisual, readBoundedBody, MAX_VISUAL_BODY_BYTES, configuredTimeout, providerFailure} from "./visual.js";

/** @type {Readonly<Record<string,string>>} */
const MODELS = Object.freeze({
    content_understanding: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    structure_repair: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    assessment_structured: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",

    reasoning: "@cf/qwen/qwen3-30b-a3b-fp8",
    qa: "@cf/qwen/qwen3-30b-a3b-fp8",
    notes: "@cf/qwen/qwen3-30b-a3b-fp8",
    roadmap: "@cf/qwen/qwen3-30b-a3b-fp8",
});

const STRUCTURED_TASKS = new Set([
    "content_understanding",
    "structure_repair",
    "assessment_structured",
]);

const MAX_BODY_BYTES = 256 * 1024;
const MAX_MESSAGES = 64;

export default {
    /** @param {Request} request @param {Env} env */
    async fetch(request, env) {
        const url = new URL(request.url);

        // Lightweight health endpoint.
        if (request.method === "GET" && url.pathname === "/health") {
            return json({
                status: "ok",
                service: "visualai-cloudflare-inference",
            });
        }

        // Only one inference endpoint.
        if (
            request.method !== "POST" ||
            (url.pathname !== "/v1/generate" && url.pathname !== "/")
        ) {
            return json({ error: "Not found" }, 404);
        }

        // Backend-to-backend authentication.
        const auth = request.headers.get("Authorization");

        if (
            !env.API_KEY ||
            auth !== `Bearer ${env.API_KEY}`
        ) {
            return json({ error: "Unauthorized" }, 401);
        }

        const contentType = request.headers.get("Content-Type") || "";

        if (!contentType.toLowerCase().includes("application/json")) {
            return json({ error: "Content-Type must be application/json" }, 415);
        }

        const contentLength = Number(
            request.headers.get("Content-Length") || "0"
        );

        if (contentLength > MAX_VISUAL_BODY_BYTES) {
            return json({ error: "Request too large" }, 413);
        }

        const requestId = crypto.randomUUID();

        try {
            const parsed = await readBoundedBody(request);
            const body = /** @type {Row} */ (parsed.body);
            if (body?.task === "vision_extract" || body?.task === "vision_verify") return handleVisual(body, env, requestId);
            if (parsed.bytes > MAX_BODY_BYTES || contentLength > MAX_BODY_BYTES) return json({error:"Request too large"}, 413);

            const task =
                typeof body.task === "string"
                    ? body.task
                    : "reasoning";

            const configuredModel = STRUCTURED_TASKS.has(task) ? env.TEXT_STRUCTURED_MODEL : env.TEXT_GENERAL_MODEL;
            const model = Object.hasOwn(MODELS, task) ? (configuredModel || MODELS[task]) : undefined;

            if (!model) {
                return json(
                    {
                        error: "Unsupported task",
                        request_id: requestId,
                    },
                    422
                );
            }
            if (!Object.values(MODELS).includes(model)) return json({error:"Invalid text model configuration",request_id:requestId},503);

            const messages = normalizeMessages(body);

            if (messages.length === 0) {
                return json(
                    {
                        error: "At least one message is required",
                        request_id: requestId,
                    },
                    400
                );
            }

            if (messages.length > MAX_MESSAGES) {
                return json(
                    {
                        error: "Too many messages",
                        request_id: requestId,
                    },
                    413
                );
            }

            const maxTokens = clampInteger(
                body.max_tokens,
                1,
                8192,
                STRUCTURED_TASKS.has(task) ? 2048 : 1024
            );

            const temperature = clampNumber(
                body.temperature,
                0,
                1,
                STRUCTURED_TASKS.has(task) ? 0.1 : 0.2
            );

            /** @type {Row} */
            const input = {
                messages,
                max_tokens: maxTokens,
                temperature,
            };

            // JSON-schema mode only for strict structured tasks.
            if (
                body.response_schema &&
                typeof body.response_schema === "object"
            ) {
                input.response_format = {
                    type: "json_schema",
                    json_schema: body.response_schema,
                };
            }

            const started = Date.now();

            let timer;
            let aiResponse;
            try {
                aiResponse = /** @type {Row} */ (await Promise.race([
                    env.AI.run(model, input),
                    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('3007: inference budget exhausted')), configuredTimeout(env.TEXT_TIMEOUT_MS,180000)); })
                ]));
            } finally { clearTimeout(timer); }

            const latencyMs = Date.now() - started;

            return json({
                ok: true,
                request_id: requestId,
                task,
                model,
                response: textResponse(aiResponse),
                usage: aiResponse.usage || null,
                latency_ms: latencyMs,
            });
        } catch (error) {
            if (error instanceof RangeError || contentLength > MAX_BODY_BYTES) return json({error:"Request too large"}, 413);
            // Do not return raw provider exception text to callers.
            console.error("Workers AI request failed", {
                request_id: requestId,
                error_name: /** @type {Row | null | undefined} */ (error)?.name || "UnknownError",
            });

            const failure = providerFailure(error);
            return json(
                {
                    ok: false,
                    error: failure.error,
                    native_code: failure.native_code,
                    request_id: requestId,
                },
                failure.status
            );
        }
    },
};

/** @param {Row} body @returns {Message[]} */
function normalizeMessages(body) {
    if (Array.isArray(body.messages)) {
        return /** @type {unknown[]} */ (body.messages)
            .filter(isNonemptyMessage)
            .map((m) => ({
                role: m.role,
                content: m.content,
            }));
    }

    // Temporary compatibility with the YouTube Worker contract.
    /** @type {Message[]} */
    const messages = [];

    if (
        typeof body.systemPrompt === "string" &&
        body.systemPrompt.trim()
    ) {
        messages.push({
            role: "system",
            content: body.systemPrompt,
        });
    }

    if (Array.isArray(body.history)) {
        for (const value of /** @type {unknown[]} */ (body.history)) {
            const item = /** @type {Row | null | undefined} */ (value);
            if (
                item &&
                typeof item.role === "string" &&
                typeof item.content === "string"
            ) {
                messages.push({
                    role: item.role,
                    content: item.content,
                });
            }
        }
    }

    if (typeof body.prompt === "string" && body.prompt.trim()) {
        messages.push({
            role: "user",
            content: body.prompt,
        });
    }

    return messages;
}

/** @param {unknown} value @param {number} min @param {number} max @param {number} fallback */
function clampInteger(value, min, max, fallback) {
    if (!Number.isInteger(value)) {
        return fallback;
    }

    return Math.min(max, Math.max(min, /** @type {number} */ (value)));
}

/** @param {unknown} value @param {number} min @param {number} max @param {number} fallback */
function clampNumber(value, min, max, fallback) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return fallback;
    }

    return Math.min(max, Math.max(min, value));
}

/** @param {unknown} data @param {number} status */
function json(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
        },
    });
}
/** @param {unknown} value @returns {value is Message} */
function isNonemptyMessage(value) {
    const m = /** @type {Row | null | undefined} */ (value);
    return Boolean(m && typeof m.role === 'string' && typeof m.content === 'string' && m.content.trim().length > 0);
}


/** Normalize documented native chat output and the existing structured-response envelope.
 * @param {Row} raw @returns {string | Row}
 */
function textResponse(raw) {
    const legacy = raw.response;
    if (typeof legacy === "string" && legacy.trim()) return legacy;
    if (legacy && typeof legacy === "object" && !Array.isArray(legacy)) return /** @type {Row} */ (legacy);
    const choices = raw.choices;
    if (Array.isArray(choices) && choices.length) {
        const message = choices[0]?.message;
        if (message && typeof message === "object" && typeof message.content === "string" && message.content.trim()) return message.content;
    }
    throw new Error("Invalid provider response envelope");
}
