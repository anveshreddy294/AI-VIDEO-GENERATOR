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

        if (contentLength > MAX_BODY_BYTES) {
            return json({ error: "Request too large" }, 413);
        }

        const requestId = crypto.randomUUID();

        try {
            const body = await request.json();

            const task =
                typeof body.task === "string"
                    ? body.task
                    : "reasoning";

            const model = MODELS[task];

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

            const aiResponse = await env.AI.run(model, input);

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
            // Do not return raw provider exception text to callers.
            console.error("Workers AI request failed", {
                request_id: requestId,
                error_name: error?.name || "UnknownError",
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

function normalizeMessages(body) {
    if (Array.isArray(body.messages)) {
        return body.messages
            .filter(
                (m) =>
                    m &&
                    typeof m.role === "string" &&
                    typeof m.content === "string" &&
                    m.content.trim().length > 0
            )
            .map((m) => ({
                role: m.role,
                content: m.content,
            }));
    }

    // Temporary compatibility with the YouTube Worker contract.
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
        for (const item of body.history) {
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

function clampInteger(value, min, max, fallback) {
    if (!Number.isInteger(value)) {
        return fallback;
    }

    return Math.min(max, Math.max(min, value));
}

function clampNumber(value, min, max, fallback) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return fallback;
    }

    return Math.min(max, Math.max(min, value));
}

function json(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
        },
    });
}