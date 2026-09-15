from pathlib import Path
p = Path("frontend/src/context/SessionContext.jsx")
s = p.read_text()
s = s.replace("const startPipeline = async (query, subject = 'Physics', documentId = null) => {",
"""const adoptKnowledge = (knowledge) => {
    setSession({ ...DEFAULT_SESSION, session_id: knowledge.session_id,
      topic_query: knowledge.topic, topic_resolved: knowledge.topic,
      subject: knowledge.subject, knowledge, knowledge_ready: true, pipeline_stage: 'knowledge_ready' });
  };

  const startPipeline = async (query, subject = '', documentId = null, options = {}) => {""")
s = s.replace("setSession(prev => ({\n      ...DEFAULT_SESSION,\n      topic_query: query,",
"""setSession(prev => ({
      ...DEFAULT_SESSION,
      knowledge: prev.knowledge, knowledge_ready: prev.knowledge_ready,
      session_id: options.session_id || '',
      topic_query: query,""")
s = s.replace("      const geminiApiKey = localStorage.getItem('GEMINI_API_KEY') || '';\n", "")
s = s.replace("      const nvidiaApiKey = localStorage.getItem('NVIDIA_API_KEY') || '';\n", "")
s = s.replace("          apiKey: geminiApiKey || nvidiaApiKey,\n          geminiApiKey,\n          nvidiaApiKey,",
"""          session_id: options.session_id || null,
          target_concept_id: options.target_concept_id || null,
          remediation_mode: options.remediation_mode || false,""")
s = s.replace("            message: content,", "            message: content,\n            session_id: session.session_id,")
s = "\n".join("          s.title || s.document_id || s.source_id" if "s.pages.join" in line else line for line in s.split("\n"))
s = s.replace("              script: finalPayload.script,", "              script: finalPayload.script,\n              assessment_id: finalPayload.assessment_id,\n              provenance: finalPayload.provenance,")
s = s.replace("              const updated = { ...prev, pipeline_stage: data.stage };",
              "              const updated = { ...prev, pipeline_stage: data.stage };\n              if (data.stage === 'knowledge_ready') updated.knowledge_ready = true;")
s = s.replace("      updateNotes,\n      addChatMessage,", "      updateNotes,\n      adoptKnowledge,\n      addChatMessage,")
s = s.replace("Lost connection to API pipe. Retrying rendering process...", "Connection interrupted; reconnecting to the existing job...")
p.write_text(s)

p = Path("frontend/src/screens/Workspace.jsx")
s = p.read_text()
s = s.replace("import PipelineStatus", "import LearningInput from '../components/LearningInput';\nimport LearningLoop from '../components/LearningLoop';\nimport PipelineStatus")
s = s.replace("    session,\n", "    session,\n    adoptKnowledge,\n", 1)
start = s.index("        <form onSubmit=")
end = s.index("</form>", start) + len("</form>")
s = s[:start] + """        <LearningInput onReady={adoptKnowledge} disabled={isPipelineRunning}
          onGenerate={knowledge => startPipeline(knowledge.topic, knowledge.subject || '', null, {session_id: knowledge.session_id})} />
""" + s[end:]
s = s.replace("    session.pipeline_stage !== 'idle' &&", "    session.pipeline_stage !== 'knowledge_ready' &&\n    session.pipeline_stage !== 'idle' &&")
s = s.replace("{isPipelineRunning ? (", "{isPipelineRunning && !session.knowledge_ready ? (")
s = s.replace("      {/* Main Workspace Workspace Flow */}", """      {isPipelineRunning && session.knowledge_ready && <PipelineStatus currentStage={session.pipeline_stage}
        message={activeStageMsg} progress={activeProgress} />}
      {session.pipeline_stage === 'error' && <p role="alert">{activeStageMsg}</p>}
      {/* Main Workspace Workspace Flow */}""")
s = s.replace("isPipelineRunning={isPipelineRunning}\n                />", "isPipelineRunning={isPipelineRunning && !session.knowledge_ready}\n                />")
anchor = "              {/* Time synchronized word highlight scrolling transcription */}"
s = s.replace(anchor, """              <LearningLoop key={session.session_id} session={session}
                onVisual={request => startPipeline(request.topic, request.subject, null, request)} />
""" + anchor)
start = s.index("  const [inputTopic")
end = s.index("  const isPipelineRunning", start)
s = s[:start] + """  const [currentTime, setCurrentTime] = useState(0);
  const handleNewLesson = async () => { await newSession(); setCurrentTime(0); };

""" + s[end:]
start = s.index("const BACKEND_URL")
end = s.index("export default function Workspace", start)
s = s[:start] + s[end:]
s = s.replace("import React, { useState, useEffect }", "import { useState }")
s = s.replace("The multi-agent educational pipeline will index the syllabus, planning visual scenes, and synthesizing premium animated movies with professional spoken explanations.",
              "Prepare evidence from a topic or your material, generate a narrated visual lesson, and use the tutor, assessment and roadmap.")
p.write_text(s)
