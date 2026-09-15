import { useEffect, useRef, useState } from 'react';
import { useSession } from '../context/SessionContext';

  function drawCanvas(canvas, ctx, time, topic) {
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // 1. Sleek sci-fi background space
    ctx.fillStyle = '#09090d';
    ctx.fillRect(0, 0, w, h);

    // 2. Mesh lines grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
    ctx.lineWidth = 1;
    const grid = 24;
    for (let x = 0; x < w; x += grid) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += grid) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    const tLower = topic.toLowerCase();

    // Custom subject specific mathematical simulations
    if (tLower.includes('relativity') || tLower.includes('dilation') || tLower.includes('gravity') || tLower.includes('light')) {
      // 1. Warping space-time coordinate grid
      ctx.strokeStyle = 'rgba(59, 130, 246, 0.07)';
      ctx.lineWidth = 1.2;
      const cx = w / 2;
      const cy = h / 2;
      const pullForce = 35 + 10 * Math.sin(time * 0.5);

      for (let r = 40; r < w * 0.8; r += 40) {
        ctx.beginPath();
        for (let angle = 0; angle <= Math.PI * 2 + 0.1; angle += 0.05) {
          const rx = cx + Math.cos(angle) * r;
          const ry = cy + Math.sin(angle) * r;
          const dist = Math.sqrt((rx - cx)**2 + (ry - cy)**2) || 1;
          const warp = pullForce * (150 / (dist + 80));
          const wx = rx - Math.cos(angle) * warp;
          const wy = ry - Math.sin(angle) * warp;
          if (angle === 0) ctx.moveTo(wx, wy);
          else ctx.lineTo(wx, wy);
        }
        ctx.stroke();
      }

      // Gravitational mass warp glow
      const grad = ctx.createRadialGradient(cx, cy, 3, cx, cy, 32);
      grad.addColorStop(0, 'rgba(245, 158, 11, 0.85)');
      grad.addColorStop(0.3, 'rgba(245, 158, 11, 0.35)');
      grad.addColorStop(1, 'rgba(245, 158, 11, 0)');
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(cx, cy, 32, 0, Math.PI * 2); ctx.fill();

      // 2. Einstein's Light Clock Thought Experiment (Stationary vs Relativistic Clock)
      const mirrorY1 = h * 0.22;
      const mirrorY2 = h * 0.70;

      // 2A: Stationary frame (Clock S)
      const sX = w * 0.22;
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.moveTo(sX - 25, mirrorY1); ctx.lineTo(sX + 25, mirrorY1); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(sX - 25, mirrorY2); ctx.lineTo(sX + 25, mirrorY2); ctx.stroke();

      const bouncePeriod = 2.5; // full cycle duration
      const fract = (time % bouncePeriod) / bouncePeriod;
      const statY = mirrorY1 + (mirrorY2 - mirrorY1) * (fract < 0.5 ? fract * 2 : (1 - fract) * 2);

      // Stationary photon glow
      ctx.fillStyle = '#f59e0b';
      ctx.shadowColor = '#f59e0b';
      ctx.shadowBlur = 12;
      ctx.beginPath(); ctx.arc(sX, statY, 6, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;

      ctx.font = '10px var(--font-mono)';
      ctx.fillStyle = 'rgba(255,255,255,0.45)';
      ctx.textAlign = 'center';
      ctx.fillText('STATIONARY (Δt)', sX, mirrorY2 + 20);

      // 2B: Relativistic Moving Frame (Clock R)
      // Velocity changes dynamically as we progress to make it highly informative!
      const beta = 0.5 + 0.40 * Math.sin(time * 0.15); // Velocity parameter (v/c)
      const mX = w * 0.62 + Math.sin(time * 0.4) * 60;

      ctx.strokeStyle = '#a78bfa';
      ctx.beginPath(); ctx.moveTo(mX - 25, mirrorY1); ctx.lineTo(mX + 25, mirrorY1); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(mX - 25, mirrorY2); ctx.lineTo(mX + 25, mirrorY2); ctx.stroke();

      // Moving photon diagonal vector path tracing
      const movingY = mirrorY1 + (mirrorY2 - mirrorY1) * (fract < 0.5 ? fract * 2 : (1 - fract) * 2);
      ctx.fillStyle = '#a78bfa';
      ctx.shadowColor = '#a78bfa';
      ctx.shadowBlur = 12;
      ctx.beginPath(); ctx.arc(mX, movingY, 6, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;

      ctx.fillText("MOVING FRAME (Δt')", mX, mirrorY2 + 20);

      // Trace path of moving clock photon
      ctx.strokeStyle = 'rgba(167, 139, 250, 0.2)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(w * 0.50, mirrorY1);
      ctx.lineTo(w * 0.62, mirrorY2);
      ctx.lineTo(w * 0.74, mirrorY1);
      ctx.stroke();
      ctx.setLineDash([]);

      // 3. Telemetry HUD indicators overlay
      ctx.font = '11px var(--font-mono)';
      ctx.fillStyle = 'rgba(240, 239, 232, 0.75)';
      ctx.textAlign = 'left';
      ctx.fillText(`VELOCITY (v): ${(beta * 299792).toFixed(0)} km/s (${(beta * 100).toFixed(1)}% c)`, 25, 40);

      const gamma = 1 / Math.sqrt(1 - beta*beta);
      ctx.fillText(`LORENTZ FACTOR (γ): ${gamma.toFixed(4)}`, 25, 58);
      ctx.fillText(`TIME DILATION: Δt' = γΔt = ${(gamma).toFixed(2)}x slower`, 25, 76);
      ctx.fillText(`LENGTH CONTRACTION (L/L₀): ${(100 / gamma).toFixed(1)}%`, 25, 94);

      // 4. Relativistic length-contracted rocket ship drawing
      const rocketX = w * 0.5 + Math.sin(time * 0.25) * 140;
      const rocketY = h * 0.86;
      const stdLen = 36;
      const contractedLen = stdLen / gamma; // length contraction!

      ctx.fillStyle = 'rgba(20, 184, 166, 0.8)';
      ctx.beginPath();
      ctx.moveTo(rocketX + contractedLen, rocketY);
      ctx.lineTo(rocketX - contractedLen, rocketY - 8);
      ctx.lineTo(rocketX - contractedLen, rocketY + 8);
      ctx.closePath();
      ctx.fill();

      // Rocket flame
      ctx.beginPath();
      ctx.arc(rocketX - contractedLen - 4, rocketY, 5 + 3 * Math.sin(time * 20), 0, Math.PI * 2);
      ctx.fillStyle = '#f43f5e';
      ctx.fill();

    } else if (tLower.includes('atom') || tLower.includes('bohr') || tLower.includes('structure') || tLower.includes('quantum')) {
      // 1. NUCLEUS GLOW REPRESENTATION
      const cx = w / 2;
      const cy = h / 2;

      ctx.shadowColor = '#f43f5e';
      ctx.shadowBlur = 10;
      
      const parts = [
        { dx: -4, dy: -4, c: '#f43f5e' },
        { dx: 5, dy: -3, c: '#3b82f6' },
        { dx: -3, dy: 5, c: '#3b82f6' },
        { dx: 4, dy: 4, c: '#f43f5e' },
        { dx: 0, dy: 1, c: '#f43f5e' }
      ];
      parts.forEach(p => {
        ctx.fillStyle = p.c;
        ctx.beginPath(); ctx.arc(cx + p.dx, cy + p.dy, 8, 0, Math.PI * 2); ctx.fill();
      });
      ctx.shadowBlur = 0;

      // 2. ORBITING CONCENTRIC ENERGY SHELLS
      const radii = [45, 80, 130];
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.setLineDash([2, 4]);

      radii.forEach((r, idx) => {
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

        // Orbiter
        const theta = time * (1.6 - idx * 0.45);
        const ex = cx + Math.cos(theta) * r;
        const ey = cy + Math.sin(theta) * r;

        ctx.setLineDash([]);
        ctx.fillStyle = '#14b8a6';
        ctx.beginPath(); ctx.arc(ex, ey, 5, 0, Math.PI * 2); ctx.fill();

        ctx.strokeStyle = 'rgba(20, 184, 166, 0.4)';
        ctx.beginPath(); ctx.arc(ex, ey, 8, 0, Math.PI * 2); ctx.stroke();

        ctx.setLineDash([2, 4]);
      });
      ctx.setLineDash([]);

      // 3. PHOTON QUANTUM ENERGY ABSOPTION TRANSITION
      const cycle = time % 6.0;
      if (cycle > 2.0 && cycle < 4.8) {
        const px = cx - 180 + (cycle - 2.0) * 105;


        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < 40; i++) {
          const sx = px - 40 + i;
          const sy = cy - 25 + Math.sin((cycle + i*0.06) * 18) * 10;
          if (i === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        }
        ctx.stroke();

        if (cycle > 4.0) {
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2.5;
          ctx.beginPath(); ctx.arc(cx, cy, 130, 0, Math.PI * 2); ctx.stroke();
          
          ctx.fillStyle = '#f59e0b';
          ctx.font = 'bold 11px var(--font-ui)';
          ctx.fillText('EXCITATION (ΔE = hν)', cx - 55, cy - 145);
        }
      }

      ctx.font = '11px var(--font-mono)';
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.textAlign = 'left';
      ctx.fillText(`ENERGY CONTEXT: E_n = -13.6 eV / n²`, 25, 40);
      ctx.fillText(`GROUND LEVEL (n=1): -13.60 eV`, 25, 58);
      ctx.fillText(`EXCITED LEVEL (n=2): -3.40 eV`, 25, 76);
      ctx.fillText(`EXCITED LEVEL (n=3): -1.51 eV`, 25, 94);

    } else {
      // GENERAL PHYSICAL / CHEMICAL EQUATION SIMULATOR
      const cx = w / 2;
      const cy = h / 2;

      ctx.strokeStyle = 'rgba(59, 130, 246, 0.2)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 40; x < w - 40; x += 6) {
        const y = cy + Math.sin(x * 0.02 + time * 1.2) * 35 + Math.cos(x * 0.008 - time * 0.7) * 12;
        if (x === 40) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Floating dynamic molecular nodes
      for (let i = 0; i < 8; i++) {
        const px = cx + Math.sin(time * 0.3 + i) * 140;
        const py = cy + Math.cos(time * 0.5 + i * 2) * 65;


        ctx.fillStyle = i % 2 === 0 ? 'rgba(245, 158, 11, 0.7)' : 'rgba(20, 184, 166, 0.7)';
        ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fill();

        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(px, py); ctx.stroke();
      }

      ctx.font = '13px var(--font-mono)';
      ctx.fillStyle = 'var(--accent-amber)';
      ctx.textAlign = 'center';
      ctx.fillText(topic, cx, cy - 100);
    }
  };


export default function VideoPlayer({ videoUrl, scenePlan, onTimeUpdate }) {
  const { session } = useSession();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // States
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [volume, setVolume] = useState(0.8);
  const [hoverScene, setHoverScene] = useState(null);
  const [videoError, setVideoError] = useState(false);

  // Compute if we are in mock mode (either no URL, error loading, or the simulated test video)
  const isMock = !videoUrl || videoUrl === null || videoUrl === '' || videoUrl.includes('output.mp4') || videoError;

  // Dynamic context retrieval for animation rendering
  const activeTopic = session?.topic_resolved || 'Relativity Theory — Chapter 2';
  const activeSubject = session?.explanation_package?.subject || 'Physics';

  // Mock-mode duration from scene plan (real video uses element metadata instead)
  useEffect(() => {
    if (!isMock) return;
    if (scenePlan && scenePlan.length > 0) {
      const sum = scenePlan.reduce((acc, sc) => acc + (sc.duration_seconds || 10), 0);
      setDuration(sum);
    } else {
      setDuration(28.7);
    }
  }, [scenePlan, isMock]);

  // Reset player state when the video source changes
  useEffect(() => {
    setVideoError(false);
    setCurrentTime(0);
    setIsPlaying(false);
  }, [videoUrl]);

  // Bind native <video> events — must re-run when videoUrl changes so listeners
  // attach to the newly mounted element (ref is null on first render in mock mode).
  useEffect(() => {
    if (isMock || videoError) return;

    const video = videoRef.current;
    if (!video) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleTime = () => {
      setCurrentTime(video.currentTime);
      onTimeUpdate?.(video.currentTime);
    };
    const handleDuration = () => {
      if (Number.isFinite(video.duration) && video.duration > 0) {
        setDuration(video.duration);
      }
    };

    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('timeupdate', handleTime);
    video.addEventListener('durationchange', handleDuration);
    video.addEventListener('loadedmetadata', handleDuration);

    // Sync UI with element state after mount / source change
    setIsPlaying(!video.paused);
    setCurrentTime(video.currentTime);
    handleDuration();

    return () => {
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('timeupdate', handleTime);
      video.removeEventListener('durationchange', handleDuration);
      video.removeEventListener('loadedmetadata', handleDuration);
    };
  }, [videoUrl, isMock, videoError, onTimeUpdate]);

  // 60FPS Fallback Animation clock ticking
  useEffect(() => {
    // Only run custom clock ticking if we are in mock mode or video failed to load
    if (!isMock) return;
    if (!isPlaying) return;

    let lastTime = performance.now();
    let animId;

    const tick = (now) => {
      const delta = (now - lastTime) / 1000;
      lastTime = now;

      setCurrentTime((prev) => {
        const next = prev + delta * speed;
        if (next >= duration) {
          setIsPlaying(false);
          return 0; // Wrap/Stop
        }
        if (onTimeUpdate) onTimeUpdate(next);
        return next;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, speed, duration, isMock, onTimeUpdate]);

  // Draw fallbacks vectors loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Trigger canvas vector draws
    drawCanvas(canvas, ctx, currentTime, activeTopic, activeSubject);
  }, [currentTime, activeTopic, activeSubject]);

  const togglePlay = async () => {
    if (isMock) {
      setIsPlaying((prev) => !prev);
      return;
    }

    const video = videoRef.current;
    if (!video) return;

    // Use element state, not React state — avoids desync when listeners were missing
    if (video.paused) {
      try {
        await video.play();
        setIsPlaying(true);
      } catch (err) {
        console.warn('Video playback failed:', err);
        setIsPlaying(false);
      }
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleScrub = (e) => {
    const pct = parseFloat(e.target.value) / 100;
    const time = pct * duration;

    if (isMock) {
      setCurrentTime(time);
      onTimeUpdate?.(time);
      return;
    }

    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
    onTimeUpdate?.(time);
  };

  const handleSpeed = (s) => {
    setSpeed(s);
    if (videoRef.current && !videoError) {
      videoRef.current.playbackRate = s;
    }
  };

  const handleVolume = (e) => {
    const v = parseFloat(e.target.value);
    setVolume(v);
    if (videoRef.current && !videoError) {
      videoRef.current.volume = v;
    }
  };

  const getSceneTicks = () => {
    if (!scenePlan || !duration) return [];

    const plannedTotal = scenePlan.reduce(
      (acc, sc) => acc + (sc.duration_seconds || 10),
      0
    );
    const scale = plannedTotal > 0 ? duration / plannedTotal : 1;

    let accTime = 0;
    return scenePlan.map((sc) => {
      const sceneDuration = sc.duration_seconds || 10;
      const startTime = accTime * scale;
      const pct = (startTime / duration) * 100;
      accTime += sceneDuration;
      return { ...sc, pct, startTime };
    });
  };

  const ticks = getSceneTicks();

  // Premium Fallback drawing engine
  const showFallbackCanvas = isMock;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        background: '#000000',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden',
        border: '1px solid var(--border-default)',
        position: 'relative'
      }}
    >
      {/* Real Video Core or Aesthetic Mock Canvas Card */}
      {showFallbackCanvas ? (
        <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', background: '#0a0a0f', display: 'block', overflow: 'hidden' }}>
          <canvas
            ref={canvasRef}
            width={640}
            height={360}
            style={{ width: '100%', height: '100%', display: 'block' }}
          />
          {/* Overlay indicator */}
          <div
            style={{
              position: 'absolute',
              top: '15px',
              right: '15px',
              background: 'rgba(15,15,20,0.85)',
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              color: 'var(--accent-amber)',
              fontFamily: 'var(--font-mono)'
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: '6px',
                height: '6px',
                background: 'var(--accent-amber)',
                borderRadius: '50%',
                boxShadow: '0 0 8px var(--accent-amber)'
              }}
            ></span>
            LIVE VECTOR ENGINE FALLBACK
          </div>
        </div>
      ) : (
        <video
          ref={videoRef}
          src={videoUrl}
          playsInline
          preload="metadata"
          onError={() => setVideoError(true)}
          style={{ width: '100%', aspectRatio: '16/9', display: 'block', background: '#000000' }}
          onClick={togglePlay}
        />
      )}

      {/* Scrubber Timeline Area */}
      <div style={{ padding: '8px 16px 4px', background: 'var(--bg-overlay)', position: 'relative' }}>
        
        {/* Hovering Scene Tooltip Label */}
        {hoverScene && (
          <div
            style={{
              position: 'absolute',
              bottom: '100%',
              left: `${hoverScene.pct}%`,
              transform: 'translateX(-50%)',
              background: 'var(--bg-base)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 10px',
              fontSize: '11px',
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              zIndex: 10,
              boxShadow: '0 4px 10px rgba(0,0,0,0.3)',
              marginBottom: '6px'
            }}
          >
            <strong>Scene {hoverScene.scene_number}:</strong> {hoverScene.title} ({hoverScene.duration_seconds}s)
          </div>
        )}

        {/* The Track Slider */}
        <div style={{ position: 'relative', width: '100%', height: '14px', display: 'flex', alignItems: 'center' }}>
          <input
            type="range"
            min="0"
            max="100"
            value={duration ? (currentTime / duration) * 100 : 0}
            onChange={handleScrub}
            style={{
              width: '100%',
              height: '4px',
              background: 'var(--bg-raised)',
              borderRadius: '2px',
              outline: 'none',
              cursor: 'pointer',
              accentColor: 'var(--accent-amber)',
              position: 'relative',
              zIndex: 2
            }}
          />

          {/* Scene Ticks Overlaid on Timeline Track */}
          {ticks.map((t, idx) => (
            <div
              key={idx}
              onMouseEnter={() => setHoverScene(t)}
              onMouseLeave={() => setHoverScene(null)}
              onClick={() => {
                if (isMock) {
                  setCurrentTime(t.startTime);
                  onTimeUpdate?.(t.startTime);
                } else if (videoRef.current) {
                  videoRef.current.currentTime = t.startTime;
                  setCurrentTime(t.startTime);
                  onTimeUpdate?.(t.startTime);
                }
              }}
              style={{
                position: 'absolute',
                left: `${t.pct}%`,
                width: '6px',
                height: '6px',
                background: 'var(--accent-amber)',
                borderRadius: '50%',
                border: '1px solid var(--bg-overlay)',
                cursor: 'pointer',
                transform: 'translate(-50%, -50%)',
                top: '50%',
                zIndex: 3,
                boxShadow: '0 0 4px var(--accent-amber)'
              }}
            />
          ))}
        </div>
      </div>

      {/* Control Buttons Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          background: 'var(--bg-overlay)',
          borderTop: '1px solid var(--border-subtle)',
          flexWrap: 'wrap',
          gap: '10px'
        }}
      >
        {/* Play/Pause controls */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            onClick={togglePlay}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '18px',
              cursor: 'pointer'
            }}
          >
            {isPlaying ? '⏸️' : '▶️'}
          </button>
          
          <span className="mono-text" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {Math.floor(currentTime / 60)}:{(Math.floor(currentTime % 60) < 10 ? '0' : '') + Math.floor(currentTime % 60)}
            {' / '}
            {duration ? `${Math.floor(duration / 60)}:${(Math.floor(duration % 60) < 10 ? '0' : '') + Math.floor(duration % 60)}` : '0:30'}
          </span>
        </div>

        {/* Volume controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px' }}>🔊</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={handleVolume}
            style={{ width: '60px', accentColor: 'var(--accent-blue)', height: '4px' }}
          />
        </div>

        {/* Speed controls */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {[0.75, 1, 1.25, 1.5, 2].map((s) => (
            <button
              key={s}
              onClick={() => handleSpeed(s)}
              style={{
                padding: '2px 6px',
                borderRadius: '4px',
                border: 'none',
                background: speed === s ? 'var(--accent-amber-dim)' : 'transparent',
                color: speed === s ? 'var(--accent-amber)' : 'var(--text-secondary)',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)',
                cursor: 'pointer',
                fontWeight: speed === s ? '600' : '400'
              }}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
