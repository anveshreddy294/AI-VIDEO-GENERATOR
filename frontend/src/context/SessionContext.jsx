import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { useProfile } from './ProfileContext';
import { buildProfileSnapshot } from '../utils/profileSnapshot';

const SessionContext = createContext();

export const useSession = () => useContext(SessionContext);

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:5000';

const DEFAULT_SESSION = {
  session_id: '',
  topic_query: '',
  topic_resolved: '',
  pipeline_stage: 'idle',
  messages: [],
  video_url: null,
  explanation_package: null,
  scene_plan: null,
  notes: '',
  script: ''
};

export const SessionProvider = ({ children }) => {
  const { profile } = useProfile() || {};
  const [session, setSession] = useState(DEFAULT_SESSION);
  const currentSessionRef = useRef(session);
  useEffect(() => { currentSessionRef.current = session; }, [session]);
  const [activeStageMsg, setActiveStageMsg] = useState('');
  const [activeProgress, setActiveProgress] = useState(0);
  const eventSourceRef = useRef(null);
  const notesSaveTimeoutRef = useRef(null);

  // Sync session on startup (load last session if it exists)
  useEffect(() => {
    async function loadLastSession() {
      try {
        const response = await fetch('/api/load/session.json');
        if (response.ok) {
          const data = await response.json();
          if (data && data.session_id) {
            // Ensure video_url points to backend
            const videoUrl = data.video_url?.startsWith('http') 
              ? data.video_url 
              : `${BACKEND_URL}${data.video_url}`;
            setSession({ ...data, video_url: videoUrl });
          }
        }
      } catch (err) {
        console.warn('No existing workspace session loaded:', err);
      }
    }
    loadLastSession();

    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
      if (notesSaveTimeoutRef.current) clearTimeout(notesSaveTimeoutRef.current);
    };
  }, []);

  // Saves notes automatically (autosave every 3 seconds of silence)
  const saveNotesToServer = async (newNotes, currentSession) => {
    if (!currentSession.session_id) return;
    const updatedPayload = { ...currentSession, notes: newNotes };

    try {
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'session.json',
          payload: updatedPayload
        })
      });
    } catch (err) {
      console.error('Failed to autosave notes:', err);
    }
  };

  const updateNotes = (newNotes) => {
    setSession(prev => {
      const updated = { ...prev, notes: newNotes };
      
      // Debounce the save endpoint
      if (notesSaveTimeoutRef.current) clearTimeout(notesSaveTimeoutRef.current);
      notesSaveTimeoutRef.current = setTimeout(() => {
        saveNotesToServer(newNotes, updated);
      }, 3000);

      return updated;
    });
  };

  const incrementFollowUpCount = async (sessionId) => {
    if (!sessionId) return;
    try {
      const response = await fetch('/api/load/history.json');
      if (!response.ok) return;
      const historyData = await response.json();
      const sessions = historyData.sessions || [];
      const idx = sessions.findIndex((s) => s.session_id === sessionId);
      if (idx === -1) return;

      sessions[idx] = {
        ...sessions[idx],
        follow_up_count: (sessions[idx].follow_up_count || 0) + 1,
      };

      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'history.json',
          payload: { sessions },
        }),
      });
    } catch (err) {
      console.warn('Failed to update follow-up count:', err);
    }
  };

  const addChatMessage = async (role, content) => {
    if (!session.session_id) return;

    const newMessage = { role, content, timestamp: new Date().toISOString() };
    const updatedMessages = [...session.messages, newMessage];

    const updatedSession = { ...session, messages: updatedMessages };
    setSession(updatedSession);

    // Save chat message
    try {
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'session.json',
          payload: updatedSession
        })
      });

      if (role === 'user') {
        await incrementFollowUpCount(session.session_id);
      }

      if (role === 'user') {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: content,
            session_id: session.session_id,
            topic: session.topic_query,
            subject: session.subject || null,
            documentId: session.document_id || null,
            history: session.messages.slice(-8).map(({ role, content }) => ({ role, content }))
          })
        });
        const data = await response.json();
        if (currentSessionRef.current.session_id !== updatedSession.session_id) return;
        if (!response.ok) throw new Error(data.detail || 'Chat request failed');
        const references = (data.sources || []).map(s =>
          s.title || s.document_id || s.source_id
        ).join('\n');
        const aiMessage = {
          role: 'assistant', content: data.answer + (references ? `\n\nSources:\n${references}` : ''),
          sources: data.sources, timestamp: new Date().toISOString()
        };
        const withAI = { ...currentSessionRef.current,
          messages: [...currentSessionRef.current.messages, aiMessage] };
        currentSessionRef.current = withAI;
        setSession(withAI);
        await fetch('/api/persist', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: 'session.json', payload: withAI })
        });
      }
    } catch (err) {
      console.error('Chat request failed:', err);
      setSession(prev => prev.session_id === updatedSession.session_id ? { ...prev, messages: [...prev.messages, { role: 'assistant', content: 'Chat unavailable: ' + err.message, timestamp: new Date().toISOString() }] } : prev);
    }
  };

  const newSession = async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (notesSaveTimeoutRef.current) {
      clearTimeout(notesSaveTimeoutRef.current);
      notesSaveTimeoutRef.current = null;
    }
    setSession({ ...DEFAULT_SESSION });
    setActiveStageMsg('');
    setActiveProgress(0);
    try {
      await fetch('/api/persist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: 'session.json',
          payload: DEFAULT_SESSION,
        }),
      });
    } catch (err) {
      console.warn('Failed to clear workspace session:', err);
    }
  };

  const adoptKnowledge = (knowledge) => {
    setSession({ ...DEFAULT_SESSION, session_id: knowledge.session_id,
      topic_query: knowledge.topic, topic_resolved: knowledge.topic,
      subject: knowledge.subject, knowledge, knowledge_ready: true, pipeline_stage: 'knowledge_ready' });
  };

  const startPipeline = async (query, subject = '', documentId = null, options = {}) => {
    // Reset previous pipeline
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setSession(prev => ({
      ...DEFAULT_SESSION,
      knowledge: prev.knowledge, knowledge_ready: prev.knowledge_ready,
      session_id: options.session_id || '',
      topic_query: query,
      subject,
      document_id: documentId,
      pipeline_stage: 'retrieving'
    }));
    setActiveStageMsg('Contacting classroom agent pipeline...');
    setActiveProgress(5);

    try {
      const learnerProfile = buildProfileSnapshot(profile, subject);
      const response = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: query,
          subject,
          documentId,
          session_id: options.session_id || null,
          target_concept_id: options.target_concept_id || null,
          remediation_mode: options.remediation_mode || false,
          learnerProfile
        })
      });

      if (!response.ok) {
        throw new Error('Failed to bootstrap pipeline server.');
      }

      const runData = await response.json();
      const { sessionId, resolvedTopic } = runData;

      setSession(prev => ({
        ...prev,
        session_id: sessionId,
        topic_resolved: resolvedTopic
      }));

      // Listen for SSE events
      eventSourceRef.current = new EventSource(`/api/pipeline/status/${sessionId}`);

      eventSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.stage === 'error') {
            setSession(prev => ({ ...prev, pipeline_stage: 'error' }));
            setActiveStageMsg(`Error rendering lesson: ${data.message}`);
            eventSourceRef.current.close();
            return;
          }

          setActiveProgress(data.progress);
          setActiveStageMsg(data.message);

          if (data.stage === 'complete') {
            const finalPayload = data.data;
            // Convert relative path to absolute URL pointing to backend
            const videoUrl = finalPayload.video_url?.startsWith('http') 
              ? finalPayload.video_url 
              : `${BACKEND_URL}${finalPayload.video_url}`;
            setSession(prev => ({
              ...prev,
              pipeline_stage: 'complete',
              video_url: videoUrl,
              explanation_package: finalPayload.explanation_package,
              scene_plan: finalPayload.scene_plan,
              script: finalPayload.script,
              assessment_id: finalPayload.assessment_id,
              provenance: finalPayload.provenance,
              notes: `# Notes: ${resolvedTopic}\n\n## Summary\n${finalPayload.explanation_package.core_explanation}\n\n## Analogies\n* ${finalPayload.explanation_package.analogies.join('\n* ')}`,
              messages: [
                {
                  role: 'assistant',
                  content: `Interactive lesson generated for **${resolvedTopic}**! Play the animation in the workspace player and review the textbook grounding below. Let me know if you have any follow-up questions!`,
                  timestamp: new Date().toISOString()
                }
              ]
            }));
            eventSourceRef.current.close();
          } else {
            // Incremental updates
            setSession(prev => {
              const updated = { ...prev, pipeline_stage: data.stage };
              if (data.stage === 'knowledge_ready') updated.knowledge_ready = true;
              if (data.stage === 'explaining' && data.data) {
                updated.explanation_package = data.data;
              }
              if (data.stage === 'planning' && data.data) {
                updated.scene_plan = data.data;
              }
              if (data.stage === 'generating' && data.data) {
                updated.script = data.data.script;
              }
              return updated;
            });
          }
        } catch (err) {
          console.error('Failed to parse SSE payload:', err);
        }
      };

      eventSourceRef.current.onerror = (err) => {
        console.error('SSE connection error:', err);
        setActiveStageMsg('Connection interrupted; reconnecting to the existing job...');
      };

    } catch (error) {
      setSession(prev => ({ ...prev, pipeline_stage: 'error' }));
      setActiveStageMsg(error.message || 'Pipeline rendering encountered a failure.');
    }
  };

  const loadSessionById = async (sid) => {
    try {
      const response = await fetch('/api/load/session.json');
      if (response.ok) {
        const data = await response.json();
        // Since we write session.json per session, in a single-user system we reload the active one
        if (data && data.session_id === sid) {
          // Ensure video_url points to backend
          const videoUrl = data.video_url?.startsWith('http') 
            ? data.video_url 
            : `${BACKEND_URL}${data.video_url}`;
          setSession({ ...data, video_url: videoUrl });
        } else {
          // If the selected session is from history but is different, load its details from history
          const hRes = await fetch('/api/load/history.json');
          if (hRes.ok) {
            const hData = await hRes.json();
            const hs = hData.sessions?.find(s => s.session_id === sid);
            if (hs) {
              // Construct a temporary session view
              const videoUrl = hs.video_path?.startsWith('http') 
                ? hs.video_path 
                : `${BACKEND_URL}${hs.video_path}`;
              setSession({
                session_id: sid,
                topic_query: hs.topic.split('—')[0].trim(),
                topic_resolved: hs.topic,
                pipeline_stage: 'complete',
                video_url: videoUrl,
                notes: `# Loaded session: ${hs.topic}`,
                messages: [{ role: 'assistant', content: `Rewatching previously saved module for **${hs.topic}**.`, timestamp: new Date().toISOString() }],
                explanation_package: {
                  topic: hs.topic,
                  learning_objectives: ['Review past learning objectives'],
                  core_explanation: 'This lesson was rendered and saved in your library. Double check the timeline segments to explore topics.',
                  analogies: ['Analogy details saved in past renders.'],
                  prerequisites: []
                },
                scene_plan: [
                  { scene_number: 1, title: 'Introductory Section', description: 'Past animation scene', duration_seconds: hs.duration || '01:30' }
                ]
              });
            }
          }
        }
      }
    } catch (err) {
      console.error('Failed to load session:', err);
    }
  };

  return (
    <SessionContext.Provider value={{
      session,
      updateNotes,
      adoptKnowledge,
      addChatMessage,
      startPipeline,
      newSession,
      loadSessionById,
      activeStageMsg,
      activeProgress
    }}>
      {children}
    </SessionContext.Provider>
  );
};
