import { useState } from 'react';
import { useSession } from '../context/SessionContext';
import VideoPlayer from '../components/VideoPlayer';
import TranscriptPanel from '../components/TranscriptPanel';
import ChatPanel from '../components/ChatPanel';
import MarkdownEditor from '../components/MarkdownEditor';
import LearningInput from '../components/LearningInput';
import LearningLoop from '../components/LearningLoop';
import PipelineStatus from '../components/PipelineStatus';

export default function Workspace() {
  const {
    session,
    adoptKnowledge,
    updateNotes,
    addChatMessage,
    startPipeline,
    newSession,
    activeStageMsg,
    activeProgress
  } = useSession();

  const [currentTime, setCurrentTime] = useState(0);
  const handleNewLesson = async () => { await newSession(); setCurrentTime(0); };

  const isPipelineRunning =
    session.pipeline_stage !== 'knowledge_ready' &&
    session.pipeline_stage !== 'idle' &&
    session.pipeline_stage !== 'complete' &&
    session.pipeline_stage !== 'error';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', overflow: 'hidden' }}>
      
      {/* Top Topic Input Bar */}
      <div
        style={{
          padding: 'var(--space-4) var(--space-8)',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)'
        }}
      >
        <LearningInput onReady={adoptKnowledge} disabled={isPipelineRunning}
          onGenerate={knowledge => startPipeline(knowledge.topic, knowledge.subject || '', null, {session_id: knowledge.session_id})} />


        {session.topic_resolved && session.pipeline_stage !== 'idle' ? (
          <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Current Topic:</span>
            <span
              className="badge badge-amber"
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '12px',
                padding: '4px 10px',
                borderRadius: '100px'
              }}
            >
              {session.topic_resolved}
            </span>
            <button
              type="button"
              onClick={handleNewLesson}
              disabled={isPipelineRunning}
              className="btn btn-ghost"
              style={{ fontSize: '11px', padding: '4px 10px' }}
            >
              New Lesson
            </button>
          </div>
        ) : null}
      </div>

      {isPipelineRunning && session.knowledge_ready && <PipelineStatus currentStage={session.pipeline_stage}
        message={activeStageMsg} progress={activeProgress} />}
      {session.pipeline_stage === 'error' && <p role="alert">{activeStageMsg}</p>}
      {/* Main Workspace Workspace Flow */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Pipeline running active screen view overlay */}
        {isPipelineRunning && !session.knowledge_ready ? (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              background: 'rgba(15,15,20,0.92)',
              backdropFilter: 'blur(10px)',
              zIndex: 100,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              padding: 'var(--space-6)',
              overflowY: 'auto'
            }}
          >
            <PipelineStatus
              currentStage={session.pipeline_stage}
              message={activeStageMsg}
              progress={activeProgress}
            />
          </div>
        ) : null}

        {/* Dynamic workspace views split panels */}
        {session.pipeline_stage === 'idle' && !isPipelineRunning ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              color: 'var(--text-secondary)',
              gap: 'var(--space-4)',
              textAlign: 'center',
              padding: 'var(--space-10)'
            }}
          >
            <span style={{ fontSize: '64px' }}>🎓</span>
            <h2 className="serif-title" style={{ fontSize: '28px', color: 'var(--text-primary)', margin: 0 }}>
              Your Lecture Theatre Awaits
            </h2>
            <p style={{ maxWidth: '400px', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              Type a textbook chapter or scientific concept above. Prepare evidence from a topic or your material, generate a narrated visual lesson, and use the tutor, assessment and roadmap.
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', flex: 1, height: '100%', overflow: 'hidden' }}>
            
            {/* Left Column: Player & Transcript */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-4)',
                padding: 'var(--space-6)',
                borderRight: '1px solid var(--border-subtle)',
                overflowY: 'auto',
                height: '100%'
              }}
            >
              {/* Custom custom video player with ticks */}
              <VideoPlayer
                videoUrl={session.video_url}
                scenePlan={session.scene_plan}
                onTimeUpdate={setCurrentTime}
              />

              <LearningLoop key={session.session_id} session={session}
                onVisual={request => startPipeline(request.topic, request.subject, null, request)} />
              {/* Time synchronized word highlight scrolling transcription */}
              <div style={{ flex: 1, minHeight: '200px' }}>
                <TranscriptPanel
                  currentTime={currentTime}
                  scenePlan={session.scene_plan}
                  isPipelineRunning={isPipelineRunning && !session.knowledge_ready}
                />
              </div>
            </div>

            {/* Right Column: AI Doubts Chat & Notebook */}
            <div style={{ display: 'grid', gridTemplateRows: '1.2fr 1fr', height: '100%', overflow: 'hidden' }}>
              
              {/* Bubble dialog conversation co-pilot */}
              <div style={{ overflow: 'hidden' }}>
                <ChatPanel
                  messages={session.messages || []}
                  onSendMessage={(content) => addChatMessage('user', content)}
                  isPipelineRunning={isPipelineRunning && !session.knowledge_ready}
                />
              </div>

              {/* Autosaving Personal markdown journal */}
              <div style={{ borderTop: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
                <MarkdownEditor
                  notes={session.notes || ''}
                  onNotesChange={updateNotes}
                />
              </div>

            </div>

          </div>
        )}
      </div>

    </div>
  );
}
