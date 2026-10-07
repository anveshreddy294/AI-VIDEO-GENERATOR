// @ts-check
/** @typedef {Record<string, unknown>} Row */
/** @typedef {{role:string,content:string}} Message */
/** @typedef {import('./visual.js').VisualEnv & {API_KEY?:string}} Env */
import {handleVisual, readBoundedBody, MAX_VISUAL_BODY_BYTES} from "./visual.js";

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
            if (body?.task === "vision_extract") return handleVisual(body, env, requestId);
            if (parsed.bytes > MAX_BODY_BYTES || contentLength > MAX_BODY_BYTES) return json({error:"Request too large"}, 413);

            const task =
                typeof body.task === "string"
                    ? body.task
                    : "reasoning";

            const model = Object.hasOwn(MODELS, task) ? MODELS[task] : undefined;

            if (!model) {
                return json(
                    {
                        error: "Unsupported task",
                        request_id: requestId,
                    },
                    422
                );
            }

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
                4096,
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
                STRUCTURED_TASKS.has(task) &&
                body.response_schema &&
                typeof body.response_schema === "object"
            ) {
                input.response_format = {
                    type: "json_schema",
                    json_schema: body.response_schema,
                };
            }

            const started = Date.now();

            const aiResponse = /** @type {Row} */ (await env.AI.run(model, input));

            const latencyMs = Date.now() - started;

            return json({
                ok: true,
                request_id: requestId,
                task,
                model,
                response: aiResponse.response,
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

            return json(
                {
                    ok: false,
                    error: "AI_PROVIDER_ERROR",
                    request_id: requestId,
                },
                502
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
