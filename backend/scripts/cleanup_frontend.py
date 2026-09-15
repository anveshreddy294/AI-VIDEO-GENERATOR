from pathlib import Path
import re
root = Path("frontend/src")
for p in root.rglob("*.jsx"):
    s = p.read_text(encoding="utf-8")
    if "React." not in s:
        s = s.replace("import React, {", "import {")
        s = re.sub(r"import React from ['\"]react['\"];?\n", "", s)
    s = re.sub(r"catch\s*\((?:e|err|_)\)\s*\{\s*\}", "catch { /* Optional persisted data may be absent. */ }", s)
    if p.name == "Analytics.jsx":
        s = s.replace("[historyData, setHistoryData]", "[, setHistoryData]")
    if p.name == "VideoPlayer.jsx":
        s = s.replace("const drawCanvas = (canvas, ctx, time, topic, subject) => {", "function drawCanvas(canvas, ctx, time, topic) {")
        s = re.sub(r"^\s*const py = [^;]+;\n", "\n", s, flags=re.M)
    if p.name == "KnowledgeGraph.jsx":
        s = re.sub(r"let nodeColor = [^;]+;", "let nodeColor;", s)
        s = re.sub(r"let strokeColor = [^;]+;", "let strokeColor;", s)
    p.write_text(s, encoding="utf-8")

p = Path("PageIndex/pageindex/local_llm.py")
s = p.read_text(encoding="utf-8")
s = s.replace("trying google.generativeai", "trying google.genai")
a = s.index("    try:\n        import google.generativeai as genai")
b = s.index("\n\ndef generate_structured(", a)
s = s[:a] + '''    from google import genai
    from google.genai import types
    model_name = fallback_model.split("/")[-1]
    full = f"Respond with ONLY valid JSON. No markdown.\\nJSON Schema:\\n{schema_text}\\n\\n{user_blob}"
    with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000)) as client:
        response = client.models.generate_content(model=model_name, contents=full,
            config=types.GenerateContentConfig(response_mime_type="application/json"))
    if not response.text:
        raise RuntimeError("Empty Gemini response")
    return response.text
''' + s[b:]
p.write_text(s, encoding="utf-8")
