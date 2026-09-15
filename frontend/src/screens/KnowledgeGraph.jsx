import { useEffect, useRef, useState } from 'react';
import { useSession } from '../context/SessionContext';

// Standard fallback syllabus structure matching high school Physics/Chemistry
const MOCK_SYLLABUS = {
  nodes: [
    { id: '1', label: 'Atomic Structure', subject: 'Chemistry', x: 200, y: 150, radius: 24, summary: 'Study of the constituents of atoms: protons, neutrons, and electrons.', details: 'Includes historical models: Dalton, Thomson, Rutherford, and Bohr.' },
    { id: '2', label: 'Bohr\'s Model', subject: 'Chemistry', x: 260, y: 220, radius: 18, summary: 'Explains hydrogen spectrum lines via quantized electron orbits.', details: 'Formulates energy level equations and orbital angular momentum values.' },
    { id: '3', label: 'Quantum Numbers', subject: 'Chemistry', x: 340, y: 250, radius: 18, summary: 'Defines four coordinates detailing electron address maps.', details: 'Includes Principal, Azimuthal, Magnetic, and Spin vectors.' },
    { id: '4', label: 'Chemical Bonding', subject: 'Chemistry', x: 120, y: 100, radius: 22, summary: 'How atoms unite to form compounds via valence shell forces.', details: 'Covers Ionic, Covalent, and Coordinate bonds.' },
    { id: '5', label: 'VSEPR Theory', subject: 'Chemistry', x: 80, y: 170, radius: 16, summary: 'Predicts molecular geometry based on electron pair repulsion.', details: 'Explains linear, trigonal planar, tetrahedral shape formulas.' },
    { id: '6', label: 'Periodic Classification', subject: 'Chemistry', x: 380, y: 120, radius: 20, summary: 'Organizes element groupings based on electronic configurations.', details: 'Investigates trends: electronegativity, ionization energy.' },
    { id: '7', label: 'Kinematics', subject: 'Physics', x: 500, y: 300, radius: 24, summary: 'Describes moving bodies without considering mass or cause.', details: 'Utilizes displacement, speed, acceleration curves.' },
    { id: '8', label: 'Newton\'s Laws', subject: 'Physics', x: 580, y: 220, radius: 22, summary: 'Grounds classical mechanics via inertia, force, and reaction.', details: 'Connects linear momentum conservation to textbook equations.' },
    { id: '9', label: 'Circular Motion', subject: 'Physics', x: 620, y: 320, radius: 16, summary: 'Studies particles tracing circular coordinates at varying speed.', details: 'Focuses on centripetal acceleration vector dynamics.' },
    { id: '10', label: 'Work & Energy', subject: 'Physics', x: 480, y: 180, radius: 20, summary: 'Investigates work done by conservative and non-conservative fields.', details: 'Exposes mechanical energy conservation ratios.' }
  ],
  links: [
    { source: '1', target: '2' },
    { source: '2', target: '3' },
    { source: '1', target: '4' },
    { source: '4', target: '5' },
    { source: '1', target: '6' },
    { source: '7', target: '8' },
    { source: '7', target: '9' },
    { source: '8', target: '10' }
  ]
};

function shortDocLabel(doc) {
  const name = doc.doc_name || doc.id || '';
  if (name.toLowerCase().includes('chemistry')) return 'Chemistry (Class 9)';
  if (name.toLowerCase().includes('physics')) return 'Physics (Class 10)';
  if (name.length > 36) return `${name.slice(0, 33)}...`;
  return name;
}

function buildGraphFromStructure(structureData, subject = 'General') {
  const nodes = [];
  const links = [];
  let nodeIndex = 0;

  const addNode = (item, parentId = null, depth = 0) => {
    if (!item?.title || item.content_type === 'preface') return null;
    const id = item.node_id || `node_${nodeIndex++}`;
    const radius = depth === 0 ? 22 : depth === 1 ? 18 : 16;
    const x = 120 + (nodeIndex % 6) * 90 + depth * 20;
    const y = 80 + Math.floor(nodeIndex / 6) * 70 + depth * 15;
    nodes.push({
      id,
      label: item.title,
      subject,
      x,
      y,
      radius,
      summary: item.summary || `Section from the indexed textbook: ${item.title}`,
      details: item.keywords?.length
        ? `Keywords: ${item.keywords.slice(0, 6).join(', ')}`
        : `Pages ${item.start_index || item.start_page || '?'}–${item.end_index || item.end_page || '?'}`,
    });
    if (parentId) links.push({ source: parentId, target: id });
    const children = item.nodes || item.children || [];
    children.forEach((child) => addNode(child, id, depth + 1));
    return id;
  };

  const structure = structureData?.structure || [];
  structure.forEach((chapter) => addNode(chapter, null, 0));

  if (!nodes.length) return null;
  return { nodes, links };
}

export default function KnowledgeGraph({ setActiveScreen }) {
  const canvasRef = useRef(null);
  const { startPipeline } = useSession();
  
  const [selectedNode, setSelectedNode] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeSubject, setActiveSubject] = useState('All');
  
  // Pan and Zoom coordinates state
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const [draggedNode, setDraggedNode] = useState(null);

  const [graphData, setGraphData] = useState(MOCK_SYLLABUS);
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [activeDocLabel, setActiveDocLabel] = useState('Mock syllabus');
  const [graphLoading, setGraphLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState('');

  const loadStructureForDoc = async (doc) => {
    if (!doc?.id) return;
    setGraphLoading(true);
    setSelectedDocId(doc.id);
    setActiveDocLabel(shortDocLabel(doc));
    setSelectedNode(null);
    try {
      const response = await fetch(`/results/${encodeURIComponent(doc.id)}/structure.json`);
      if (!response.ok) throw new Error('structure.json not found');
      const structureData = await response.json();
      const built = buildGraphFromStructure(structureData, doc.subject || 'General');
      if (built?.nodes?.length) {
        setGraphData(built);
      } else {
        setGraphData(MOCK_SYLLABUS);
        setActiveDocLabel(`${shortDocLabel(doc)} (fallback mock)`);
      }
    } catch (err) {
      console.warn('Failed to load curriculum structure:', err);
      setGraphData(MOCK_SYLLABUS);
      setActiveDocLabel(`${shortDocLabel(doc)} (fallback mock)`);
    } finally {
      setGraphLoading(false);
    }
  };

  useEffect(() => {
    async function loadDocuments() {
      try {
        const response = await fetch('/api/curriculum/documents');
        if (!response.ok) return;
        const data = await response.json();
        const docs = (data.documents || []).filter((d) =>
          /chemistry|physics/i.test(`${d.doc_name} ${d.id}`)
        );
        setDocuments(docs.length ? docs : data.documents || []);
        if (docs.length) {
          await loadStructureForDoc(docs[0]);
        } else if (data.documents?.length) {
          await loadStructureForDoc(data.documents[0]);
        }
      } catch (err) {
        console.warn('Failed to load curriculum documents:', err);
      }
    }
    loadDocuments();
  }, []);

  const handleIndexPdf = async () => {
    const filename = window.prompt(
      'Enter PDF filename from PageIndex/examples/documents (e.g. Chemistry.pdf):',
      'Chemistry.pdf'
    );
    if (!filename) return;
    setIndexing(true);
    setIndexMessage('');
    try {
      const response = await fetch('/api/curriculum/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'Indexing failed');
      setIndexMessage('Indexing complete.');
      const listRes = await fetch('/api/curriculum/documents');
      if (listRes.ok) {
        const listData = await listRes.json();
        const docs = listData.documents || [];
        setDocuments(docs);
        const match = docs.find((d) => d.id === filename || d.doc_name === filename);
        if (match) await loadStructureForDoc(match);
      }
    } catch (err) {
      setIndexMessage(err.message || 'Indexing failed');
    } finally {
      setIndexing(false);
    }
  };

  // Load history metadata if any to overlay completed node markers
  const [historyIds, setHistoryIds] = useState([]);
  useEffect(() => {
    async function loadHistory() {
      try {
        const response = await fetch('/api/load/history.json');
        if (response.ok) {
          const data = await response.json();
          if (data && data.sessions) {
            const completedTopics = data.sessions.map(s => s.topic.split('—')[0].trim().toLowerCase());
            setHistoryIds(completedTopics);
          }
        }
      } catch { /* Optional persisted data may be absent. */ }
    }
    loadHistory();
  }, []);

  // Simple Spring physics simulation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationId;

    const runSimulation = () => {
      // Create local deep copies to manipulate positions
      const nodes = [...graphData.nodes];
      const links = [...graphData.links];

      // Physics constants
      const kLink = 0.02;     // spring constant
      const lenLink = 100;    // link rest length
      const kRepel = 800;     // repulsion force

      // Simulate physics forces
      for (let step = 0; step < 3; step++) {
        // 1. Repulsion between nodes
        for (let i = 0; i < nodes.length; i++) {
          const n1 = nodes[i];
          if (n1 === draggedNode) continue;
          
          for (let j = i + 1; j < nodes.length; j++) {
            const n2 = nodes[j];
            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            
            // Force proportional to reciprocal square of distance
            const force = kRepel / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            if (n2 !== draggedNode) {
              n2.x += fx;
              n2.y += fy;
            }
            n1.x -= fx;
            n1.y -= fy;
          }
        }

        // 2. Attraction along link paths
        links.forEach(link => {
          const sNode = nodes.find(n => n.id === link.source);
          const tNode = nodes.find(n => n.id === link.target);
          if (!sNode || !tNode) return;

          const dx = tNode.x - sNode.x;
          const dy = tNode.y - sNode.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          const delta = dist - lenLink;
          const force = kLink * delta;
          
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (tNode !== draggedNode) {
            tNode.x -= fx;
            tNode.y -= fy;
          }
          if (sNode !== draggedNode) {
            sNode.x += fx;
            sNode.y += fy;
          }
        });

        // 3. Central gravity force to prevent drifting
        nodes.forEach(n => {
          if (n === draggedNode) return;
          const cx = canvas.width / 2;
          const cy = canvas.height / 2;
          n.x += (cx - n.x) * 0.005;
          n.y += (cy - n.y) * 0.005;
        });
      }

      // Draw Graph
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.translate(pan.x, pan.y);
      ctx.scale(zoom, zoom);

      // Draw links
      links.forEach(link => {
        const sNode = nodes.find(n => n.id === link.source);
        const tNode = nodes.find(n => n.id === link.target);
        if (!sNode || !tNode) return;

        ctx.beginPath();
        ctx.moveTo(sNode.x, sNode.y);
        ctx.lineTo(tNode.x, tNode.y);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      });

      // Draw nodes
      nodes.forEach(node => {
        const isMatched = activeSubject === 'All' || node.subject === activeSubject;
        const isSearched = !searchQuery.trim() || node.label.toLowerCase().includes(searchQuery.toLowerCase());
        const isCompleted = historyIds.includes(node.label.toLowerCase());

        const opacity = isMatched && isSearched ? 1 : 0.25;

        // Draw node aura glow if completed
        if (isCompleted) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.radius + 8, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(20, 184, 166, ${0.1 * opacity})`;
          ctx.fill();
        }

        // Draw node base circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        
        let nodeColor;
        let strokeColor;

        if (node.subject === 'Physics') {
          nodeColor = isCompleted ? 'rgba(20, 184, 166, 0.25)' : 'rgba(59, 130, 246, 0.25)';
          strokeColor = isCompleted ? 'var(--accent-teal)' : 'var(--accent-blue)';
        } else {
          nodeColor = isCompleted ? 'rgba(20, 184, 166, 0.25)' : 'rgba(245, 158, 11, 0.25)';
          strokeColor = isCompleted ? 'var(--accent-teal)' : 'var(--accent-amber)';
        }

        ctx.fillStyle = nodeColor;
        ctx.fill();
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = selectedNode?.id === node.id ? 3 : 1.5;
        ctx.stroke();

        // Node label
        ctx.font = '500 11px var(--font-ui)';
        ctx.fillStyle = `rgba(240, 239, 232, ${opacity})`;
        ctx.textAlign = 'center';
        ctx.fillText(node.label, node.x, node.y + node.radius + 16);
      });

      ctx.restore();
      animationId = requestAnimationFrame(runSimulation);
    };

    runSimulation();

    return () => cancelAnimationFrame(animationId);
  }, [graphData, pan, zoom, selectedNode, activeSubject, searchQuery, historyIds, draggedNode]);

  // Handle resizing canvas
  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current) {
        canvasRef.current.width = canvasRef.current.parentElement.clientWidth;
        canvasRef.current.height = 480;
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleMouseDown = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;

    // Check if node is clicked
    const clickedNode = graphData.nodes.find(node => {
      const dist = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2);
      return dist <= node.radius + 10;
    });

    if (clickedNode) {
      setDraggedNode(clickedNode);
      setSelectedNode(clickedNode);
    } else {
      isDraggingRef.current = true;
      dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = (e) => {
    if (draggedNode) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left - pan.x) / zoom;
      const y = (e.clientY - rect.top - pan.y) / zoom;
      
      draggedNode.x = x;
      draggedNode.y = y;
    } else if (isDraggingRef.current) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y
      });
    }
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
    setDraggedNode(null);
  };

  const handleZoom = (factor) => {
    setZoom(prev => Math.min(Math.max(prev + factor, 0.5), 2.5));
  };

  const handleLearnNode = async () => {
    if (!selectedNode) return;
    setActiveScreen('workspace');
    await startPipeline(selectedNode.label, selectedNode.subject, selectedDocId);
  };

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden' }}>
      
      {/* Accordion Left Topic List */}
      <div
        style={{
          width: '280px',
          height: '100%',
          borderRight: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-surface)'
        }}
      >
        <div style={{ padding: 'var(--space-5)', borderBottom: '1px solid var(--border-subtle)' }}>
          <h3 className="serif-title" style={{ fontSize: '20px', color: 'var(--text-primary)', margin: 0 }}>Syllabus Map</h3>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Active: <span style={{ color: 'var(--accent-amber)' }}>{activeDocLabel}</span>
            {graphLoading ? ' — loading…' : ''}
          </p>

          {documents.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
              {documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => loadStructureForDoc(doc)}
                  className="btn btn-ghost"
                  style={{
                    fontSize: '11px',
                    padding: '6px 10px',
                    textAlign: 'left',
                    background: selectedDocId === doc.id ? 'var(--bg-raised)' : 'transparent',
                    color: selectedDocId === doc.id ? 'var(--accent-amber)' : 'var(--text-secondary)',
                  }}
                >
                  {shortDocLabel(doc)} ({doc.node_count} nodes)
                </button>
              ))}
            </div>
          )}

          <button
            onClick={handleIndexPdf}
            disabled={indexing}
            className="btn btn-ghost"
            style={{ fontSize: '11px', padding: '6px 10px', marginTop: '8px', width: '100%' }}
          >
            {indexing ? 'Indexing PDF…' : 'Index PDF from examples/'}
          </button>
          {indexMessage && (
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>{indexMessage}</p>
          )}
          
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search syllabus..."
            style={{
              width: '100%',
              background: 'var(--bg-raised)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-primary)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 12px',
              fontSize: '12px',
              outline: 'none',
              marginTop: '12px'
            }}
          />
        </div>

        {/* Node list scroll */}
        <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-3)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {graphData.nodes
              .filter(n => activeSubject === 'All' || n.subject === activeSubject)
              .filter(n => !searchQuery.trim() || n.label.toLowerCase().includes(searchQuery.toLowerCase()))
              .map(node => {
                const isCompleted = historyIds.includes(node.label.toLowerCase());
                return (
                  <button
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      borderRadius: 'var(--r-sm)',
                      background: selectedNode?.id === node.id ? 'var(--bg-raised)' : 'transparent',
                      border: 'none',
                      color: selectedNode?.id === node.id ? 'var(--accent-amber)' : 'var(--text-secondary)',
                      fontSize: '12px',
                      textAlign: 'left',
                      cursor: 'pointer'
                    }}
                  >
                    <span>{node.label}</span>
                    <span style={{ fontSize: '10px' }}>{isCompleted ? '🟢' : '⚪'}</span>
                  </button>
                );
              })}
          </div>
        </div>
      </div>

      {/* Force directed interactive canvas center panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
        
        {/* Navigation Toolbar overlays */}
        <div style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 10, display: 'flex', gap: '8px' }}>
          {['All', 'Physics', 'Chemistry'].map(subj => (
            <button
              key={subj}
              onClick={() => setActiveSubject(subj)}
              className="btn btn-ghost"
              style={{
                fontSize: '11px',
                padding: '6px 12px',
                background: activeSubject === subj ? 'var(--bg-surface)' : 'rgba(23,23,30,0.5)',
                color: activeSubject === subj ? 'var(--accent-amber)' : 'var(--text-secondary)'
              }}
            >
              {subj}
            </button>
          ))}
        </div>

        {/* Zoom Controls overlay */}
        <div style={{ position: 'absolute', bottom: '20px', left: '20px', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <button onClick={() => handleZoom(0.1)} className="btn btn-ghost" style={{ padding: '6px 10px', fontSize: '13px' }}>＋</button>
          <button onClick={() => handleZoom(-0.1)} className="btn btn-ghost" style={{ padding: '6px 10px', fontSize: '13px' }}>－</button>
        </div>

        {/* Canvas container */}
        <div style={{ flex: 1, background: '#0e0e13', position: 'relative' }}>
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ display: 'block', cursor: draggedNode ? 'grabbing' : 'grab' }}
          />
        </div>

        {/* Selected Node Bottom Drawer */}
        {selectedNode && (
          <div
            style={{
              padding: 'var(--space-5) var(--space-8)',
              background: 'var(--bg-surface)',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 'var(--space-6)'
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '6px' }}>
                <span className="badge badge-amber" style={{ textTransform: 'uppercase', fontSize: '10px' }}>{selectedNode.subject}</span>
                <h4 className="serif-title" style={{ fontSize: '20px', color: 'var(--text-primary)', margin: 0 }}>
                  {selectedNode.label}
                </h4>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0', lineHeight: '1.4' }}>
                {selectedNode.summary}
              </p>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {selectedNode.details}
              </span>
            </div>
            <button onClick={handleLearnNode} className="btn btn-primary" style={{ padding: '10px 20px', fontSize: '13px', whiteSpace: 'nowrap' }}>
              Launch RAG Animation Pipeline →
            </button>
          </div>
        )}
      </div>

    </div>
  );
}
