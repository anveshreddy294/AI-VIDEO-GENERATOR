"""VisualAI - Landing, Authentication, and 3D Interactive Pedagogical Showcase.

Features:
- Solid 3D Architectural Pillar & Energy Conduit running vertically from header to footer with metallic plinths,
  machined collar hubs, hex bolts, and recessed illuminated fiber-optic channel.
- 6 High-Fidelity Scientific & Engineering Specimen Plates orbiting the central pillar via articulated support arms:
  1. Specimen 01: Vector Coordinate & Geometry Dial (interactive Cartesian coordinate projection).
  2. Specimen 02: Fourier Signal & Harmonic Waveform Analyzer (spectral trace & Whisper sync).
  3. Specimen 03: Directed Concept Mastery DAG Tree (prerequisite topology with kill-switch safe gates).
  4. Specimen 04: Grounded Theorem & LaTeX Proof Slate (Stokes/Maxwell-Ampère formal derivation).
  5. Specimen 05: Molecular Orbital Bohr Simulator (quantum energy shells & Manim vector engine).
  6. Specimen 06: Cognitive Telemetry Gauge (cohort mastery distribution & zero-hallucination verification).
- Front-face Hero Console with high-graphics typography, crisp contrast, zero emojis/vibe-coding clutter,
  and dedicated 'Get Started' (-> /signup) and 'Log In' (-> /login) CTAs.
- Dedicated Sign-Up (/signup) and Log-In (/login) pages with instant credential storage and redirection to /dashboard.
- Unified Botanical Peach Green palette matching the primary dashboard (#2e7d5e light / #4ecb94 dark, porcelain #f4f6fa, charcoal #333333).
- Zero clutter in the footer (removed all interaction hint banners).
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["landing"])

# ---------------------------------------------------------------------------
# Common CSS Styles & Themes (Strictly matching Dashboard Palette)
# ---------------------------------------------------------------------------
COMMON_STYLES = """
    :root {
        --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --font-display: 'Playfair Display', Georgia, serif;
        --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

        --bg-page: #f4f6fa;
        --bg-card: rgba(244, 246, 250, 0.94);
        --bg-surface: #f8f9fa;
        --bg-subtle: #e9edf5;

        --text-ink: #333333;
        --text-body: #4b5563;
        --text-muted: #6b7280;

        /* Peach Green Palette */
        --peach-green: #2e7d5e;
        --peach-green-hover: #24664c;
        --peach-green-soft: #edf6f2;
        --peach-green-border: #9ecab4;
        --peach-green-shadow: rgba(46, 125, 94, 0.28);

        --border-card: rgba(226, 232, 240, 0.8);
        --radius-sm: 4px;
        --radius-md: 8px;
        --radius-lg: 14px;

        /* Specimen Plate Styling */
        --plate-bg: rgba(255, 255, 255, 0.92);
        --plate-border: rgba(46, 125, 94, 0.32);
        --plate-glow: rgba(46, 125, 94, 0.16);

        /* Botanical Floral Background Pattern (Light Mode) */
        --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%232e7d5e%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.11%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.20%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M72%2C80%20C58%2C76%2048%2C84%2042%2C80%20C48%2C76%2058%2C84%2072%2C80%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M88%2C80%20C102%2C84%20112%2C76%20118%2C80%20C112%2C84%20102%2C76%2088%2C80%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
    }

    [data-theme="dark"] {
        --bg-page: #18191e;
        --bg-card: rgba(26, 29, 36, 0.94);
        --bg-surface: #22242c;
        --bg-subtle: #1f2026;

        --text-ink: #f3f4f6;
        --text-body: #d1d5db;
        --text-muted: #9ca3af;

        --peach-green: #4ecb94;
        --peach-green-hover: #3db882;
        --peach-green-soft: rgba(78, 203, 148, 0.16);
        --peach-green-border: rgba(78, 203, 148, 0.38);
        --peach-green-shadow: rgba(78, 203, 148, 0.28);

        --border-card: rgba(255, 255, 255, 0.09);

        --plate-bg: rgba(24, 26, 33, 0.94);
        --plate-border: rgba(78, 203, 148, 0.38);
        --plate-glow: rgba(78, 203, 148, 0.20);

        /* Botanical Floral Background Pattern (Dark Mode) */
        --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%234ecb94%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.13%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.24%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M72%2C80%20C58%2C76%2048%2C84%2042%2C80%20C48%2C76%2058%2C84%2072%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M88%2C80%20C102%2C84%20112%2C76%20118%2C80%20C112%2C84%20102%2C76%2088%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: var(--font-sans);
        background-color: var(--bg-page);
        background-image: var(--floral-bg);
        background-repeat: repeat;
        background-size: 160px 160px;
        background-attachment: fixed;
        color: var(--text-ink);
        line-height: 1.6;
        min-height: 100vh;
        overflow-x: hidden;
        transition: background-color 0.3s ease, color 0.3s ease;
    }

    #antigravityFloralCanvas {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 1;
    }

    /* Fixed Navigation Bar */
    .landing-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 100;
        padding: 16px 40px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--bg-card);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-bottom: 1px solid var(--border-card);
        transition: background 0.3s ease;
    }

    .brand-link {
        display: flex;
        align-items: center;
        gap: 12px;
        text-decoration: none;
        color: inherit;
    }

    .brand-logo-pill {
        width: 38px;
        height: 38px;
        border-radius: var(--radius-sm);
        background: var(--bg-surface);
        border: 1.5px solid var(--peach-green-border);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--peach-green);
        font-size: 18px;
        font-weight: 800;
        letter-spacing: -0.5px;
        box-shadow: 0 4px 12px var(--peach-green-shadow);
    }

    .brand-title-group h1 {
        font-family: var(--font-display);
        font-size: 21px;
        font-weight: 700;
        letter-spacing: -0.4px;
        color: var(--text-ink);
        line-height: 1.1;
    }
    .brand-title-group h1 span { color: var(--peach-green); }
    .brand-tagline-text {
        font-family: var(--font-mono);
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.4px;
        color: var(--peach-green);
        display: block;
        margin-top: 2px;
    }

    .nav-buttons {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .nav-btn {
        padding: 8px 18px;
        border-radius: var(--radius-sm);
        font-size: 13.5px;
        font-weight: 600;
        text-decoration: none;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: all 0.22s ease;
        border: 1px solid transparent;
        font-family: var(--font-sans);
    }

    .nav-btn-ghost {
        background: var(--bg-surface);
        color: var(--text-ink);
        border-color: var(--border-card);
    }
    .nav-btn-ghost:hover {
        border-color: var(--peach-green-border);
        color: var(--peach-green);
        background: var(--peach-green-soft);
    }

    .nav-btn-cta {
        background: var(--peach-green);
        color: #ffffff !important;
        box-shadow: 0 4px 14px var(--peach-green-shadow);
        border: 1px solid rgba(255, 255, 255, 0.18);
    }
    .nav-btn-cta:hover {
        background: var(--peach-green-hover);
        transform: translateY(-1px);
        box-shadow: 0 6px 18px var(--peach-green-shadow);
    }
"""

# ---------------------------------------------------------------------------
# Antigravity Canvas Script (Cohesive Botanical Colors, Zero-G Interactive Reaction)
# ---------------------------------------------------------------------------
CANVAS_ANTIGRAVITY_SCRIPT = """
    <script>
    (function initAntigravityFloral() {
        const canvas = document.getElementById('antigravityFloralCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let width = 0;
        let height = 0;
        let dpr = 1;

        const mouse = {
            x: -2000,
            y: -2000,
            targetX: -2000,
            targetY: -2000,
            radius: 180,
            active: false
        };

        function resize() {
            dpr = Math.min(window.devicePixelRatio || 1, 2);
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = Math.floor(width * dpr);
            canvas.height = Math.floor(height * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        window.addEventListener('resize', resize, { passive: true });
        resize();

        window.addEventListener('mousemove', function(e) {
            mouse.targetX = e.clientX;
            mouse.targetY = e.clientY;
            mouse.active = true;
        }, { passive: true });

        window.addEventListener('mouseleave', function() {
            mouse.active = false;
            mouse.targetX = -2000;
            mouse.targetY = -2000;
        }, { passive: true });

        function getPalette() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            return {
                petals: isDark
                    ? ['rgba(78, 203, 148, 0.35)', 'rgba(61, 184, 130, 0.30)', 'rgba(167, 243, 208, 0.22)', 'rgba(78, 203, 148, 0.18)']
                    : ['rgba(46, 125, 94, 0.30)', 'rgba(36, 102, 76, 0.25)', 'rgba(92, 184, 138, 0.22)', 'rgba(46, 125, 94, 0.15)'],
                node: isDark ? 'rgba(78, 203, 148, 0.60)' : 'rgba(46, 125, 94, 0.50)',
                line: isDark ? 'rgba(78, 203, 148, 0.14)' : 'rgba(46, 125, 94, 0.10)'
            };
        }

        class FloralParticle {
            constructor() {
                this.reset(true);
            }

            reset(initial) {
                this.x = Math.random() * (width || 1200);
                this.y = initial ? Math.random() * (height || 800) : (height + 25 + Math.random() * 40);
                this.size = 4 + Math.random() * 8;
                this.type = Math.random() > 0.4 ? 'petal' : 'spore';

                this.vx = (Math.random() - 0.5) * 0.35;
                this.vy = -(0.25 + Math.random() * 0.45);
                this.rotation = Math.random() * Math.PI * 2;
                this.rotSpeed = (Math.random() - 0.5) * 0.02;
                this.phase = Math.random() * Math.PI * 2;
                this.phaseSpeed = 0.01 + Math.random() * 0.015;

                this.fx = 0;
                this.fy = 0;
                this.colorIdx = Math.floor(Math.random() * 4);
            }

            update(time, palette) {
                this.phase += this.phaseSpeed;
                this.rotation += this.rotSpeed;
                this.x += this.vx + Math.sin(this.phase) * 0.3;
                this.y += this.vy;

                if (mouse.x > -1000 && mouse.y > -1000) {
                    const dx = this.x - mouse.x;
                    const dy = this.y - mouse.y;
                    const dist = Math.hypot(dx, dy);
                    const maxDist = mouse.radius;

                    if (dist < maxDist && dist > 1) {
                        const factor = 1 - dist / maxDist;
                        const angle = Math.atan2(dy, dx);
                        const push = factor * 4.2;
                        this.fx += Math.cos(angle) * push;
                        this.fy += Math.sin(angle) * push;
                    }
                }

                this.x += this.fx;
                this.y += this.fy;
                this.fx *= 0.92;
                this.fy *= 0.92;

                if (this.y < -30) this.y = height + 20;
                if (this.y > height + 35) this.y = -20;
                if (this.x < -30) this.x = width + 20;
                if (this.x > width + 30) this.x = -20;
            }

            draw(ctx, palette) {
                ctx.save();
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation);

                const color = palette.petals[this.colorIdx];
                ctx.fillStyle = color;

                if (this.type === 'petal') {
                    const s = this.size;
                    ctx.beginPath();
                    ctx.moveTo(0, -s);
                    ctx.bezierCurveTo(s * 0.65, -s * 0.4, s * 0.7, s * 0.5, 0, s);
                    ctx.bezierCurveTo(-s * 0.7, s * 0.5, -s * 0.65, -s * 0.4, 0, -s);
                    ctx.fill();
                } else {
                    ctx.beginPath();
                    ctx.arc(0, 0, this.size * 0.35, 0, Math.PI * 2);
                    ctx.fillStyle = palette.node;
                    ctx.fill();
                }
                ctx.restore();
            }
        }

        const count = Math.min(48, Math.max(22, Math.floor((width * height) / 26000)));
        const particles = [];
        for (let i = 0; i < count; i++) {
            particles.push(new FloralParticle());
        }

        function animate(now) {
            requestAnimationFrame(animate);

            if (mouse.active) {
                mouse.x += (mouse.targetX - mouse.x) * 0.16;
                mouse.y += (mouse.targetY - mouse.y) * 0.16;
            } else {
                mouse.x += (-2000 - mouse.x) * 0.1;
                mouse.y += (-2000 - mouse.y) * 0.1;
            }

            ctx.clearRect(0, 0, width, height);
            const palette = getPalette();

            if (mouse.x > -500 && mouse.y > -500) {
                for (let i = 0; i < particles.length; i++) {
                    const p1 = particles[i];
                    const distCursor = Math.hypot(p1.x - mouse.x, p1.y - mouse.y);
                    if (distCursor < 190) {
                        for (let j = i + 1; j < particles.length; j++) {
                            const p2 = particles[j];
                            const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
                            if (d < 80) {
                                ctx.beginPath();
                                ctx.moveTo(p1.x, p1.y);
                                ctx.lineTo(p2.x, p2.y);
                                ctx.strokeStyle = palette.line;
                                ctx.lineWidth = (1 - d / 80) * 1.2;
                                ctx.stroke();
                            }
                        }
                    }
                }
            }

            for (let i = 0; i < particles.length; i++) {
                particles[i].update(now, palette);
                particles[i].draw(ctx, palette);
            }
        }

        requestAnimationFrame(animate);
    })();

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('visualai_theme', next);
        updateThemeUI(next);
    }

    function updateThemeUI(theme) {
        const sun = document.getElementById('themeIconSun');
        const moon = document.getElementById('themeIconMoon');
        const text = document.getElementById('themeToggleText');
        if (theme === 'dark') {
            if (sun) sun.style.display = 'inline-block';
            if (moon) moon.style.display = 'none';
            if (text) text.textContent = 'Light Mode';
        } else {
            if (sun) sun.style.display = 'none';
            if (moon) moon.style.display = 'inline-block';
            if (text) text.textContent = 'Dark Mode';
        }
    }

    (function() {
        const saved = localStorage.getItem('visualai_theme');
        if (saved) {
            document.documentElement.setAttribute('data-theme', saved);
            updateThemeUI(saved);
        }
    })();
    </script>
"""

# ---------------------------------------------------------------------------
# 1. LANDING PAGE HTML
# ---------------------------------------------------------------------------
LANDING_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Open Multimodal Learning Architecture | Study With Your Vision</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
    <style>
        /*COMMON_STYLES*/

        .stage-container {
            position: relative;
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* ---------------------------------------------------------------------
           REAL 3D MECHANICAL PILLAR & CONDUIT (From Header to Footer)
           --------------------------------------------------------------------- */
        .center-pole-wrapper {
            position: absolute;
            top: 0;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 58px;
            pointer-events: none;
            z-index: 4;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
        }

        /* Heavy Machined Base Plinths */
        .pole-flange-top, .pole-flange-bottom {
            width: 58px;
            height: 16px;
            background: linear-gradient(180deg, #1b2126 0%, #2f3842 50%, #151a1e 100%);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 3px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
            z-index: 6;
        }

        /* 3D Cylindrical Pillar with Specular Metallic Surface */
        .center-pole {
            position: relative;
            width: 30px;
            height: 100%;
            background: linear-gradient(90deg, 
                #14191d 0%, 
                #232a30 16%, 
                #43505c 34%, 
                #7e93a4 48%, 
                #ffffff 51%, 
                #5b6d7c 58%, 
                #21282e 84%, 
                #0f1315 100%);
            box-shadow: 
                -8px 0 24px rgba(0, 0, 0, 0.35),
                8px 0 24px rgba(0, 0, 0, 0.35),
                0 0 18px var(--peach-green-shadow);
            display: flex;
            justify-content: center;
        }

        /* Recessed Luminescent Core Laser Channel */
        .pole-luminescent-core {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 5px;
            background: linear-gradient(180deg, 
                rgba(46, 125, 94, 0.1) 0%, 
                var(--peach-green) 15%, 
                #64f0b7 50%, 
                var(--peach-green) 85%, 
                rgba(46, 125, 94, 0.1) 100%);
            box-shadow: 0 0 10px var(--peach-green), 0 0 22px var(--peach-green);
            animation: coreBeamPulse 3.5s ease-in-out infinite alternate;
        }

        @keyframes coreBeamPulse {
            0% { opacity: 0.72; filter: drop-shadow(0 0 4px var(--peach-green)); }
            100% { opacity: 1; filter: drop-shadow(0 0 14px #64f0b7); }
        }

        /* Machined Mechanical Collar Hubs at Orbital Plate Altitudes */
        .pole-collar-hub {
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            width: 48px;
            height: 16px;
            border-radius: 3px;
            background: linear-gradient(180deg, #37434c 0%, #1c2227 60%, #111518 100%);
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.5), 0 0 6px var(--peach-green-shadow);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 4px;
            z-index: 5;
        }

        .hub-bolt {
            width: 4px;
            height: 4px;
            border-radius: 50%;
            background: #9ab0c2;
            box-shadow: inset 0 1px 1px #000;
        }

        .hub-indicator {
            width: 5px;
            height: 5px;
            border-radius: 50%;
            background: var(--peach-green);
            box-shadow: 0 0 6px var(--peach-green);
        }

        /* Altitude positions corresponding to the 6 orbital plates */
        .hub-0 { top: calc(50% - 150px); }
        .hub-1 { top: calc(50% - 90px); }
        .hub-2 { top: calc(50% - 30px); }
        .hub-3 { top: calc(50% + 30px); }
        .hub-4 { top: calc(50% + 90px); }
        .hub-5 { top: calc(50% + 150px); }

        /* ---------------------------------------------------------------------
           3D CAROUSEL VIEWPORT & SCIENTIFIC SPECIMEN PLATES
           --------------------------------------------------------------------- */
        .carousel-3d-viewport {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            perspective: 1400px;
            perspective-origin: 50% 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 3;
            pointer-events: none;
        }

        .carousel-3d-axis {
            position: relative;
            width: 0;
            height: 0;
            transform-style: preserve-3d;
            will-change: transform;
        }

        /* Distinct Scientific Specimen Plate */
        .specimen-plate {
            position: absolute;
            width: 330px;
            min-height: 220px;
            left: -165px;
            top: -110px;
            border-radius: var(--radius-md);
            padding: 18px 20px;
            background: var(--plate-bg);
            border: 1px solid var(--plate-border);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22), 0 0 25px var(--plate-glow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            transform-style: preserve-3d;
            backface-visibility: hidden;
            pointer-events: auto;
            cursor: grab;
            user-select: none;
            transition: border-color 0.25s ease, box-shadow 0.25s ease;
        }

        .specimen-plate:active { cursor: grabbing; }

        .specimen-plate:hover {
            border-color: var(--peach-green);
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28), 0 0 32px var(--peach-green-shadow);
        }

        /* Articulated Mechanical Support Arm connecting back to the Pillar */
        .plate-support-arm {
            position: absolute;
            top: 50%;
            right: 100%;
            width: 44px;
            height: 6px;
            margin-top: -3px;
            background: linear-gradient(180deg, #37434c 0%, #1c2227 60%, #111518 100%);
            border-top: 1px solid rgba(255, 255, 255, 0.2);
            border-bottom: 1px solid rgba(0, 0, 0, 0.4);
            border-radius: 2px;
            pointer-events: none;
        }
        .plate-support-arm::after {
            content: '';
            position: absolute;
            left: -3px;
            top: -3px;
            width: 8px;
            height: 12px;
            background: #475560;
            border-radius: 2px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        /* Engineering Specimen Header */
        .specimen-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border-card);
        }

        .specimen-id-tag {
            font-family: var(--font-mono);
            font-size: 10.5px;
            font-weight: 700;
            letter-spacing: 0.8px;
            color: var(--peach-green);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .specimen-id-tag::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--peach-green);
            box-shadow: 0 0 6px var(--peach-green);
        }

        .specimen-ref-stamp {
            font-family: var(--font-mono);
            font-size: 9.5px;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }

        /* Specimen Visual Display Area */
        .specimen-canvas-box {
            width: 100%;
            height: 94px;
            background: var(--bg-surface);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .specimen-svg {
            width: 100%;
            height: 100%;
            display: block;
        }

        .specimen-title {
            font-size: 14.5px;
            font-weight: 700;
            color: var(--text-ink);
            letter-spacing: -0.2px;
            margin-bottom: 4px;
        }

        .specimen-desc {
            font-size: 11.5px;
            color: var(--text-body);
            line-height: 1.5;
            margin-bottom: 8px;
        }

        .specimen-telemetry-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 6px;
            border-top: 1px dashed var(--border-card);
            font-family: var(--font-mono);
            font-size: 9.5px;
            color: var(--text-muted);
        }

        .telemetry-highlight {
            font-weight: 700;
            color: var(--peach-green);
        }

        /* Math Proof Slate Special Box */
        .proof-box {
            padding: 8px 12px;
            font-family: 'Times New Roman', serif;
            font-size: 13.5px;
            color: var(--text-ink);
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 4px;
        }
        .proof-math-eq {
            font-weight: 700;
            letter-spacing: 0.4px;
            color: var(--peach-green);
        }
        .proof-math-note {
            font-family: var(--font-mono);
            font-size: 9.5px;
            color: var(--text-muted);
        }

        /* ---------------------------------------------------------------------
           FRONT FACE HERO SECTION (High Graphics & Clean Detailing)
           --------------------------------------------------------------------- */
        .hero-foreground {
            position: relative;
            z-index: 10;
            max-width: 620px;
            padding: 44px 48px;
            border-radius: var(--radius-lg);
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.22), 0 0 35px var(--peach-green-shadow);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            text-align: center;
            margin: 0 20px;
            animation: heroReveal 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes heroReveal {
            0% { opacity: 0; transform: translateY(16px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .hero-arch-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 14px;
            border-radius: var(--radius-sm);
            background: var(--peach-green-soft);
            color: var(--peach-green);
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 22px;
            border: 1px solid var(--peach-green-border);
        }
        .hero-arch-badge-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--peach-green);
            box-shadow: 0 0 6px var(--peach-green);
        }

        .hero-title {
            font-family: var(--font-display);
            font-size: clamp(34px, 4.6vw, 50px);
            font-weight: 700;
            line-height: 1.15;
            letter-spacing: -0.6px;
            color: var(--text-ink);
            margin-bottom: 16px;
        }

        .hero-title .title-accent {
            color: var(--peach-green);
        }

        .hero-subtitle {
            font-size: 15px;
            color: var(--text-body);
            line-height: 1.65;
            margin-bottom: 32px;
            max-width: 500px;
            margin-left: auto;
            margin-right: auto;
        }

        .hero-actions {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            flex-wrap: wrap;
        }

        .btn-high-graphics-cta {
            padding: 13px 32px;
            border-radius: var(--radius-sm);
            font-size: 14.5px;
            font-weight: 700;
            color: #ffffff !important;
            text-decoration: none;
            background: linear-gradient(180deg, #348a68 0%, #2e7d5e 50%, #24664c 100%);
            border: 1px solid rgba(255, 255, 255, 0.22);
            box-shadow: 0 8px 24px var(--peach-green-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.28);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            transition: all 0.24s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: var(--font-sans);
        }

        .btn-high-graphics-cta:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 30px var(--peach-green-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.4);
        }

        .btn-high-graphics-login {
            padding: 13px 28px;
            border-radius: var(--radius-sm);
            font-size: 14.5px;
            font-weight: 600;
            color: var(--text-ink);
            text-decoration: none;
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green-border);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
            display: inline-flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.24s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: var(--font-sans);
        }

        .btn-high-graphics-login:hover {
            border-color: var(--peach-green);
            color: var(--peach-green);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px var(--peach-green-shadow);
        }

        .btn-direct-console {
            margin-top: 18px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 12.5px;
            font-weight: 600;
            color: var(--text-muted);
            text-decoration: none;
            transition: color 0.2s ease;
        }
        .btn-direct-console:hover {
            color: var(--peach-green);
        }

        @media (max-width: 768px) {
            .hero-foreground { padding: 32px 24px; }
            .landing-header { padding: 12px 20px; }
            .specimen-plate { width: 280px; min-height: 190px; left: -140px; top: -95px; padding: 14px; }
        }
    </style>
</head>
<body>

    <canvas id="antigravityFloralCanvas"></canvas>

    <header class="landing-header">
        <a href="/" class="brand-link">
            <div class="brand-logo-pill">V</div>
            <div class="brand-title-group">
                <h1>Visual<span>AI</span></h1>
                <span class="brand-tagline-text">OPEN MULTIMODAL ARCHITECTURE</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme" id="themeToggleBtn">
                <svg id="themeIconSun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                <svg id="themeIconMoon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                <span id="themeToggleText">Dark Mode</span>
            </button>
            <a href="/login" class="nav-btn nav-btn-ghost">Log In</a>
            <a href="/signup" class="nav-btn nav-btn-cta">Get Started</a>
        </div>
    </header>

    <div class="stage-container" id="stageContainer">

        <!-- Physical 3D Pillar from Header to Footer -->
        <div class="center-pole-wrapper">
            <div class="pole-flange-top"></div>
            <div class="center-pole">
                <div class="pole-luminescent-core"></div>

                <!-- 6 Machined Mechanical Collar Hubs anchoring the orbital plate arms -->
                <div class="pole-collar-hub hub-0"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
                <div class="pole-collar-hub hub-1"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
                <div class="pole-collar-hub hub-2"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
                <div class="pole-collar-hub hub-3"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
                <div class="pole-collar-hub hub-4"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
                <div class="pole-collar-hub hub-5"><div class="hub-bolt"></div><div class="hub-indicator"></div><div class="hub-bolt"></div></div>
            </div>
            <div class="pole-flange-bottom"></div>
        </div>

        <!-- 3D Carousel Viewport containing 6 Scientific Specimen Plates -->
        <div class="carousel-3d-viewport">
            <div class="carousel-3d-axis" id="carouselAxis">

                <!-- Specimen 01: Vector Geometry & Coordinate Engine -->
                <div class="specimen-plate" data-index="0">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 01 // GEOMETRY</span>
                        <span class="specimen-ref-stamp">REF: VAI-GEO-01</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <svg viewBox="0 0 280 94" class="specimen-svg">
                            <!-- Cartesian Plane with Coordinate Grid -->
                            <line x1="28" y1="80" x2="255" y2="80" stroke="currentColor" stroke-width="1.2" stroke-opacity="0.35"/>
                            <line x1="28" y1="12" x2="28" y2="80" stroke="currentColor" stroke-width="1.2" stroke-opacity="0.35"/>
                            <!-- Arc Angle -->
                            <path d="M 58 80 A 30 30 0 0 0 52 60" fill="none" stroke="var(--peach-green)" stroke-width="1.5"/>
                            <text x="62" y="72" font-size="8.5" fill="var(--peach-green)" font-family="monospace">θ = 38.6°</text>
                            <!-- Vector Arrow -->
                            <line x1="28" y1="80" x2="168" y2="28" stroke="var(--peach-green)" stroke-width="2.4" stroke-linecap="round"/>
                            <polygon points="175,25 163,26 167,34" fill="var(--peach-green)"/>
                            <!-- Dashed Projections -->
                            <line x1="168" y1="28" x2="168" y2="80" stroke="currentColor" stroke-width="1" stroke-dasharray="3,3" stroke-opacity="0.45"/>
                            <line x1="28" y1="28" x2="168" y2="28" stroke="currentColor" stroke-width="1" stroke-dasharray="3,3" stroke-opacity="0.45"/>
                            <text x="180" y="32" font-size="9.5" font-weight="700" fill="currentColor">v = (4i + 3j)</text>
                            <text x="95" y="90" font-size="8.5" fill="currentColor" opacity="0.6">|vx| = 4.0 m/s</text>
                        </svg>
                    </div>
                    <div class="specimen-title">Visual Diagram RAG</div>
                    <div class="specimen-desc">Ingests vector figures and circuit schematics with 100% textbook evidence grounding.</div>
                    <div class="specimen-telemetry-row">
                        <span>INFERENCE: GEMMA 3 4B</span>
                        <span class="telemetry-highlight">0 CLOUD LEAKS</span>
                    </div>
                </div>

                <!-- Specimen 02: Fourier Signal & Harmonic Waveform Analyzer -->
                <div class="specimen-plate" data-index="1">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 02 // WAVEFORM</span>
                        <span class="specimen-ref-stamp">REF: VAI-SIG-04</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <svg viewBox="0 0 280 94" class="specimen-svg">
                            <!-- Harmonic Waveforms -->
                            <path d="M 12,46 Q 42,12 72,46 T 132,46 T 192,46 T 252,46 T 274,46" fill="none" stroke="var(--peach-green)" stroke-width="2.2"/>
                            <path d="M 12,46 Q 27,24 42,46 T 72,46 T 102,46 T 132,46 T 162,46 T 192,46 T 222,46 T 252,46" fill="none" stroke="var(--peach-green)" stroke-width="1" stroke-opacity="0.35"/>
                            <!-- Discrete Frequency Spectrum Bars -->
                            <rect x="30" y="74" width="6" height="14" fill="var(--peach-green)" rx="1"/>
                            <rect x="42" y="66" width="6" height="22" fill="var(--peach-green)" rx="1"/>
                            <rect x="54" y="54" width="6" height="34" fill="var(--peach-green)" rx="1"/>
                            <rect x="66" y="68" width="6" height="20" fill="var(--peach-green)" rx="1"/>
                            <rect x="78" y="78" width="6" height="10" fill="var(--peach-green)" rx="1"/>
                            <text x="110" y="82" font-size="9" font-family="monospace" fill="currentColor" opacity="0.85">f0: 440.0 Hz | SNR: 34 dB</text>
                        </svg>
                    </div>
                    <div class="specimen-title">Algorithmic 60fps Vector Video</div>
                    <div class="specimen-desc">Transforms static theorems into fluid vector animations synchronized with Whisper speech timestamps.</div>
                    <div class="specimen-telemetry-row">
                        <span>ENGINE: MANIM PIPELINE</span>
                        <span class="telemetry-highlight">SYNC: ±12ms</span>
                    </div>
                </div>

                <!-- Specimen 03: Directed Concept Mastery DAG Tree -->
                <div class="specimen-plate" data-index="2">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 03 // GRAPH MATRIX</span>
                        <span class="specimen-ref-stamp">REF: VAI-DAG-02</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <svg viewBox="0 0 280 94" class="specimen-svg">
                            <!-- Connected Concept Nodes -->
                            <circle cx="44" cy="47" r="14" fill="var(--bg-surface)" stroke="var(--peach-green)" stroke-width="2"/>
                            <text x="44" y="50" text-anchor="middle" font-size="7.5" font-weight="700" fill="var(--peach-green)">CALC</text>
                            
                            <path d="M 58 47 L 116 26" stroke="var(--peach-green)" stroke-width="1.8" stroke-dasharray="2,2"/>
                            <path d="M 58 47 L 116 68" stroke="var(--peach-green)" stroke-width="1.8"/>

                            <circle cx="130" cy="26" r="13" fill="var(--bg-surface)" stroke="currentColor" stroke-width="1.2" stroke-opacity="0.5"/>
                            <text x="130" y="29" text-anchor="middle" font-size="7.5" fill="currentColor" opacity="0.8">DIFF</text>

                            <circle cx="130" cy="68" r="13" fill="var(--peach-green-soft)" stroke="var(--peach-green)" stroke-width="2.2"/>
                            <text x="130" y="71" text-anchor="middle" font-size="7.5" font-weight="700" fill="var(--peach-green)">VECT</text>

                            <path d="M 143 68 L 214 47" stroke="var(--peach-green)" stroke-width="2"/>

                            <circle cx="228" cy="47" r="15" fill="var(--bg-surface)" stroke="var(--peach-green)" stroke-width="2"/>
                            <text x="228" y="50" text-anchor="middle" font-size="7.5" font-weight="700" fill="var(--peach-green)">NAVIER</text>
                        </svg>
                    </div>
                    <div class="specimen-title">Topological Prerequisite Mapping</div>
                    <div class="specimen-desc">Maps foundational concept gaps across prerequisite trees with state-machine loop prevention.</div>
                    <div class="specimen-telemetry-row">
                        <span>GRAPH: 3-STAGE STATE</span>
                        <span class="telemetry-highlight">KILL SWITCH: ARMED</span>
                    </div>
                </div>

                <!-- Specimen 04: Grounded Theorem & LaTeX Proof Slate -->
                <div class="specimen-plate" data-index="3">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 04 // THEOREM VERIFIER</span>
                        <span class="specimen-ref-stamp">REF: VAI-EV-03</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <div class="proof-box">
                            <div class="proof-math-eq">∮_C B · dl = μ₀ (I_enc + ε₀ dΦ_E/dt)</div>
                            <div class="proof-math-note">Step 1: Apply Stokes' Theorem: ∬_S (∇ × B) · dA</div>
                            <div class="proof-math-note" style="color:var(--peach-green); font-weight:600;">Textbook Source: Halliday & Resnick Sec 32.2</div>
                        </div>
                    </div>
                    <div class="specimen-title">Dual-Layer Grounding</div>
                    <div class="specimen-desc">Cross-references each video claim and formula directly against primary source textbook proofs.</div>
                    <div class="specimen-telemetry-row">
                        <span>VERIFICATION: STRICT</span>
                        <span class="telemetry-highlight">HALLUCINATIONS: 0.0%</span>
                    </div>
                </div>

                <!-- Specimen 05: Molecular Orbital Bohr Simulator -->
                <div class="specimen-plate" data-index="4">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 05 // QUANTUM LATTICE</span>
                        <span class="specimen-ref-stamp">REF: VAI-BOHR-01</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <svg viewBox="0 0 280 94" class="specimen-svg">
                            <!-- Nucleus and Concentric Quantum Shells -->
                            <circle cx="140" cy="47" r="8" fill="var(--peach-green)"/>
                            <circle cx="140" cy="47" r="24" fill="none" stroke="currentColor" stroke-width="1" stroke-opacity="0.25"/>
                            <circle cx="140" cy="47" r="40" fill="none" stroke="var(--peach-green)" stroke-width="1.2" stroke-dasharray="3,3"/>
                            <!-- Orbiting Electrons -->
                            <circle cx="164" cy="47" r="3.5" fill="var(--peach-green)"/>
                            <circle cx="112" cy="18" r="3.5" fill="var(--peach-green)"/>
                            <text x="26" y="82" font-size="8.5" font-family="monospace" fill="currentColor" opacity="0.75">n=3, ℓ=1 | E = -13.6/n² eV</text>
                        </svg>
                    </div>
                    <div class="specimen-title">Targeted Remediation</div>
                    <div class="specimen-desc">Diagnoses exact incorrect options and generates dedicated 45-second animated remediation videos.</div>
                    <div class="specimen-telemetry-row">
                        <span>LATENCY: ON-DEMAND</span>
                        <span class="telemetry-highlight">&lt; 60s MANIM RENDER</span>
                    </div>
                </div>

                <!-- Specimen 06: Cognitive Telemetry Gauge -->
                <div class="specimen-plate" data-index="5">
                    <div class="plate-support-arm"></div>
                    <div class="specimen-header">
                        <span class="specimen-id-tag">SPECIMEN 06 // TELEMETRY</span>
                        <span class="specimen-ref-stamp">REF: VAI-MET-05</span>
                    </div>
                    <div class="specimen-canvas-box">
                        <svg viewBox="0 0 280 94" class="specimen-svg">
                            <!-- Calibration Arc Gauge -->
                            <path d="M 52,70 A 38,38 0 1,1 118,70" fill="none" stroke="currentColor" stroke-width="6" stroke-opacity="0.14" stroke-linecap="round"/>
                            <path d="M 52,70 A 38,38 0 1,1 112,60" fill="none" stroke="var(--peach-green)" stroke-width="6" stroke-linecap="round"/>
                            <text x="85" y="48" text-anchor="middle" font-size="15" font-weight="800" fill="var(--text-ink)">98.4%</text>
                            <text x="85" y="62" text-anchor="middle" font-size="7.5" font-weight="700" fill="var(--peach-green)">MASTERY</text>
                            <!-- Cohort Distribution Histogram -->
                            <rect x="156" y="56" width="7" height="18" fill="currentColor" opacity="0.2" rx="1"/>
                            <rect x="168" y="44" width="7" height="30" fill="currentColor" opacity="0.3" rx="1"/>
                            <rect x="180" y="28" width="7" height="46" fill="var(--peach-green)" rx="1"/>
                            <rect x="192" y="48" width="7" height="26" fill="currentColor" opacity="0.2" rx="1"/>
                            <rect x="204" y="62" width="7" height="12" fill="currentColor" opacity="0.15" rx="1"/>
                            <text x="156" y="22" font-size="8.5" font-family="monospace" fill="currentColor" opacity="0.8">DISTRIBUTION: σ=0.14</text>
                        </svg>
                    </div>
                    <div class="specimen-title">Instructor Interventions</div>
                    <div class="specimen-desc">Cohort-wide mastery telemetry, human intervention overrides, and transparent learning analytics.</div>
                    <div class="specimen-telemetry-row">
                        <span>COHORT TELEMETRY</span>
                        <span class="telemetry-highlight">425 TESTS VERIFIED</span>
                    </div>
                </div>

            </div>
        </div>

        <!-- Front Face Hero Console -->
        <div class="hero-foreground">
            <div class="hero-arch-badge">
                <span class="hero-arch-badge-dot"></span>
                <span>OPEN MULTIMODAL LEARNING ARCHITECTURE</span>
            </div>
            <h1 class="hero-title">
                Study With <br><span class="title-accent">Your Vision.</span>
            </h1>
            <p class="hero-subtitle">
                Transform textbook proofs, circuit schematics, and lecture diagrams into interactive concept models and vector video animations.
            </p>
            <div class="hero-actions">
                <a href="/signup" id="btnHeroGetStarted" class="btn-high-graphics-cta">
                    <span>Get Started</span>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </a>
                <a href="/login" id="btnHeroLogin" class="btn-high-graphics-login">
                    <span>Log In</span>
                </a>
            </div>
            <a href="/dashboard" id="btnHeroDemo" class="btn-direct-console">
                <span>Explore Live Assessment Console →</span>
            </a>
        </div>

    </div>

    <script>
    (function init3DPlatePoleCarousel() {
        const axis = document.getElementById('carouselAxis');
        const plates = document.querySelectorAll('.specimen-plate');
        if (!axis || !plates.length) return;

        let currentAngle = 0;
        let targetAngle = 0;
        let isDragging = false;
        let startX = 0;
        let autoDriftSpeed = 0.04;
        let isHovered = false;

        const numPlates = plates.length;
        const radius = Math.min(window.innerWidth * 0.38, 430);

        // Map plate index to vertical elevation offsets matching the column collar hubs
        const verticalOffsets = [-150, -90, -30, 30, 90, 150];

        function updatePlatePositions(baseAngle) {
            plates.forEach((plate, i) => {
                const angleDeg = (i * (360 / numPlates)) + baseAngle;
                const rad = (angleDeg * Math.PI) / 180;
                const verticalOffset = verticalOffsets[i % verticalOffsets.length];

                const x = Math.sin(rad) * radius;
                const z = Math.cos(rad) * radius;

                plate.style.transform = 'translate3d(' + x.toFixed(1) + 'px, ' + verticalOffset + 'px, ' + z.toFixed(1) + 'px) rotateY(' + angleDeg.toFixed(1) + 'deg)';

                // Compute depth scaling & opacity
                const depthNormalized = (z + radius) / (2 * radius); // 0 (back) to 1 (front)
                plate.style.opacity = (0.42 + depthNormalized * 0.58).toFixed(2);
                
                // If plate is behind the pole (z < 0), lower z-index than central column (which is z-index 4)
                if (z > 0) {
                    plate.style.zIndex = 6 + Math.round(depthNormalized * 4);
                } else {
                    plate.style.zIndex = 1 + Math.round(depthNormalized * 2);
                }

                plate.style.filter = depthNormalized < 0.28 ? 'blur(1.2px)' : 'none';
            });
        }

        window.addEventListener('wheel', (e) => {
            targetAngle += e.deltaY * 0.14;
        }, { passive: true });

        window.addEventListener('mousedown', (e) => {
            if (e.target.closest('.hero-actions') || e.target.closest('.landing-header')) return;
            isDragging = true;
            startX = e.clientX;
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - startX;
            targetAngle += deltaX * 0.32;
            startX = e.clientX;
        });

        window.addEventListener('mouseup', () => { isDragging = false; });

        window.addEventListener('touchstart', (e) => {
            if (e.touches.length > 0) {
                startX = e.touches[0].clientX;
            }
        }, { passive: true });

        window.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                const deltaX = e.touches[0].clientX - startX;
                targetAngle += deltaX * 0.40;
                startX = e.touches[0].clientX;
            }
        }, { passive: true });

        plates.forEach(p => {
            p.addEventListener('mouseenter', () => { isHovered = true; });
            p.addEventListener('mouseleave', () => { isHovered = false; });
        });

        function loop() {
            requestAnimationFrame(loop);
            if (!isHovered && !isDragging) {
                targetAngle += autoDriftSpeed;
            }
            currentAngle += (targetAngle - currentAngle) * 0.08;
            updatePlatePositions(currentAngle);
        }

        loop();
    })();
    </script>

    /*CANVAS_SCRIPT*/

</body>
</html>
""".replace("/*COMMON_STYLES*/", COMMON_STYLES).replace("/*CANVAS_SCRIPT*/", CANVAS_ANTIGRAVITY_SCRIPT)

# ---------------------------------------------------------------------------
# 2. SIGN UP PAGE HTML (Clean, Human-built, Zero Emojis)
# ---------------------------------------------------------------------------
SIGNUP_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Get Started | Create Learning Account</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
    <style>
        /*COMMON_STYLES*/

        .auth-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 90px 24px 40px;
            position: relative;
            z-index: 10;
        }

        .auth-card {
            width: 100%;
            max-width: 480px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 38px 42px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.16), 0 0 35px var(--peach-green-shadow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            animation: cardAppear 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes cardAppear {
            0% { opacity: 0; transform: translateY(14px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .auth-header {
            text-align: center;
            margin-bottom: 28px;
        }

        .auth-logo-badge {
            width: 44px;
            height: 44px;
            margin: 0 auto 14px;
            border-radius: var(--radius-sm);
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--peach-green);
            font-size: 22px;
            font-weight: 800;
            box-shadow: 0 4px 14px var(--peach-green-shadow);
        }

        .auth-title {
            font-family: var(--font-display);
            font-size: 26px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
        }

        .auth-subtitle {
            font-size: 13.5px;
            color: var(--text-muted);
        }

        .form-group {
            margin-bottom: 18px;
            text-align: left;
        }

        .form-label {
            display: block;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }

        .form-input {
            width: 100%;
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            background: var(--bg-surface);
            border: 1px solid var(--border-card);
            color: var(--text-ink);
            font-family: var(--font-sans);
            font-size: 14px;
            transition: all 0.2s ease;
            outline: none;
        }

        .form-input:focus {
            border-color: var(--peach-green);
            box-shadow: 0 0 0 3px var(--peach-green-shadow);
        }

        .btn-auth-submit {
            width: 100%;
            padding: 13px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(180deg, #348a68 0%, #2e7d5e 50%, #24664c 100%);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 24px var(--peach-green-shadow);
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.22s ease;
            font-family: var(--font-sans);
        }

        .btn-auth-submit:hover {
            transform: translateY(-1.5px);
            box-shadow: 0 10px 28px var(--peach-green-shadow);
        }

        .auth-footer {
            text-align: center;
            margin-top: 22px;
            font-size: 13px;
            color: var(--text-muted);
        }

        .auth-footer a {
            color: var(--peach-green);
            font-weight: 700;
            text-decoration: none;
        }

        .auth-status-toast {
            margin-top: 14px;
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            display: none;
            text-align: center;
        }
    </style>
</head>
<body>

    <canvas id="antigravityFloralCanvas"></canvas>

    <header class="landing-header">
        <a href="/" class="brand-link">
            <div class="brand-logo-pill">V</div>
            <div class="brand-title-group">
                <h1>Visual<span>AI</span></h1>
                <span class="brand-tagline-text">ACCOUNT INITIALIZATION</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme" id="themeToggleBtn">
                <svg id="themeIconSun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                <svg id="themeIconMoon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                <span id="themeToggleText">Dark Mode</span>
            </button>
            <a href="/login" class="nav-btn nav-btn-ghost">Log In</a>
        </div>
    </header>

    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-header">
                <div class="auth-logo-badge">V</div>
                <h2 class="auth-title">Create Learning Account</h2>
                <p class="auth-subtitle">Configure your personal pedagogical assessment workspace</p>
            </div>

            <form id="signupForm" onsubmit="handleSignup(event)">
                <div class="form-group">
                    <label class="form-label" for="fullName">Full Name</label>
                    <input class="form-input" type="text" id="fullName" placeholder="e.g. Alex Morgan" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="studentId">Student ID / Username</label>
                    <input class="form-input" type="text" id="studentId" placeholder="e.g. student_123" value="student_123" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="subjectFocus">Primary Learning Subject</label>
                    <select class="form-input" id="subjectFocus">
                        <option value="Physics & Mechanics">Physics & Mechanics</option>
                        <option value="Calculus & Analysis">Calculus & Analysis</option>
                        <option value="Computer Science & Algorithms">Computer Science & Algorithms</option>
                        <option value="Biology & Systems">Biology & Systems</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input class="form-input" type="password" id="password" placeholder="Create a secure password" required minlength="4" value="student123">
                </div>

                <button type="submit" id="btnSubmitSignup" class="btn-auth-submit">
                    Create Account & Enter Dashboard →
                </button>

                <div id="signupToast" class="auth-status-toast"></div>
            </form>

            <div class="auth-footer">
                Already registered? <a href="/login">Log in here</a>
            </div>
        </div>
    </div>

    <script>
    function handleSignup(event) {
        event.preventDefault();
        const fullName = document.getElementById('fullName').value.trim();
        const studentId = document.getElementById('studentId').value.trim() || 'student_123';
        const subject = document.getElementById('subjectFocus').value;
        const toast = document.getElementById('signupToast');
        const submitBtn = document.getElementById('btnSubmitSignup');

        submitBtn.disabled = true;
        submitBtn.textContent = 'Configuring Personalized Workspace...';

        const profile = {
            fullName: fullName,
            studentId: studentId,
            subject: subject,
            createdAt: new Date().toISOString()
        };
        localStorage.setItem('visualai_user', JSON.stringify(profile));
        localStorage.setItem('visualai_student_id', studentId);

        toast.style.display = 'block';
        toast.style.background = 'var(--peach-green-soft)';
        toast.style.color = 'var(--peach-green)';
        toast.style.border = '1px solid var(--peach-green-border)';
        toast.textContent = 'Account created successfully. Loading dashboard...';

        setTimeout(() => {
            window.location.href = '/dashboard?user_id=' + encodeURIComponent(studentId);
        }, 500);
    }
    </script>

    /*CANVAS_SCRIPT*/

</body>
</html>
""".replace("/*COMMON_STYLES*/", COMMON_STYLES).replace("/*CANVAS_SCRIPT*/", CANVAS_ANTIGRAVITY_SCRIPT)

# ---------------------------------------------------------------------------
# 3. LOGIN PAGE HTML (Clean, Human-built, Zero Emojis)
# ---------------------------------------------------------------------------
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Log In | Student Assessment Console</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
    <style>
        /*COMMON_STYLES*/

        .auth-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 90px 24px 40px;
            position: relative;
            z-index: 10;
        }

        .auth-card {
            width: 100%;
            max-width: 460px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 38px 42px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.16), 0 0 35px var(--peach-green-shadow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            animation: cardAppear 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes cardAppear {
            0% { opacity: 0; transform: translateY(14px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .auth-header {
            text-align: center;
            margin-bottom: 28px;
        }

        .auth-logo-badge {
            width: 44px;
            height: 44px;
            margin: 0 auto 14px;
            border-radius: var(--radius-sm);
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--peach-green);
            font-size: 22px;
            font-weight: 800;
            box-shadow: 0 4px 14px var(--peach-green-shadow);
        }

        .auth-title {
            font-family: var(--font-display);
            font-size: 26px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
        }

        .auth-subtitle {
            font-size: 13.5px;
            color: var(--text-muted);
        }

        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }

        .form-label {
            display: block;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.6px;
        }

        .form-input {
            width: 100%;
            padding: 12px 16px;
            border-radius: var(--radius-sm);
            background: var(--bg-surface);
            border: 1px solid var(--border-card);
            color: var(--text-ink);
            font-family: var(--font-sans);
            font-size: 14px;
            transition: all 0.2s ease;
            outline: none;
        }

        .form-input:focus {
            border-color: var(--peach-green);
            box-shadow: 0 0 0 3px var(--peach-green-shadow);
        }

        .btn-auth-submit {
            width: 100%;
            padding: 13px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(180deg, #348a68 0%, #2e7d5e 50%, #24664c 100%);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 24px var(--peach-green-shadow);
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.22s ease;
            font-family: var(--font-sans);
        }

        .btn-auth-submit:hover {
            transform: translateY(-1.5px);
            box-shadow: 0 10px 28px var(--peach-green-shadow);
        }

        .btn-quick-demo {
            width: 100%;
            padding: 11px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            font-weight: 600;
            color: var(--text-ink);
            background: var(--bg-surface);
            border: 1px dashed var(--peach-green-border);
            cursor: pointer;
            margin-top: 12px;
            transition: all 0.2s ease;
            font-family: var(--font-sans);
        }
        .btn-quick-demo:hover {
            background: var(--peach-green-soft);
            color: var(--peach-green);
            border-color: var(--peach-green);
        }

        .auth-footer {
            text-align: center;
            margin-top: 22px;
            font-size: 13px;
            color: var(--text-muted);
        }

        .auth-footer a {
            color: var(--peach-green);
            font-weight: 700;
            text-decoration: none;
        }

        .auth-status-toast {
            margin-top: 14px;
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            font-size: 13px;
            display: none;
            text-align: center;
        }
    </style>
</head>
<body>

    <canvas id="antigravityFloralCanvas"></canvas>

    <header class="landing-header">
        <a href="/" class="brand-link">
            <div class="brand-logo-pill">V</div>
            <div class="brand-title-group">
                <h1>Visual<span>AI</span></h1>
                <span class="brand-tagline-text">AUTHENTICATION PORTAL</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme" id="themeToggleBtn">
                <svg id="themeIconSun" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                <svg id="themeIconMoon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                <span id="themeToggleText">Dark Mode</span>
            </button>
            <a href="/signup" class="nav-btn nav-btn-cta">Sign Up</a>
        </div>
    </header>

    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-header">
                <div class="auth-logo-badge">V</div>
                <h2 class="auth-title">Welcome Back</h2>
                <p class="auth-subtitle">Verify your student credentials to enter the learning console</p>
            </div>

            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label class="form-label" for="loginStudentId">Student ID or Username</label>
                    <input class="form-input" type="text" id="loginStudentId" placeholder="e.g. student_123" value="student_123" required>
                </div>

                <div class="form-group">
                    <label class="form-label" for="loginPassword">Password</label>
                    <input class="form-input" type="password" id="loginPassword" placeholder="••••••••" value="password123" required>
                </div>

                <button type="submit" id="btnLoginSubmit" class="btn-auth-submit">
                    Verify & Enter Dashboard →
                </button>

                <button type="button" class="btn-quick-demo" onclick="quickDemoLogin()">
                    Quick Demo Access (student_123)
                </button>

                <div id="loginToast" class="auth-status-toast"></div>
            </form>

            <div class="auth-footer">
                New to VisualAI? <a href="/signup">Create account here</a>
            </div>
        </div>
    </div>

    <script>
    function handleLogin(event) {
        event.preventDefault();
        const studentId = document.getElementById('loginStudentId').value.trim() || 'student_123';
        proceedToDashboard(studentId);
    }

    function quickDemoLogin() {
        document.getElementById('loginStudentId').value = 'student_123';
        proceedToDashboard('student_123');
    }

    function proceedToDashboard(studentId) {
        const toast = document.getElementById('loginToast');
        const submitBtn = document.getElementById('btnLoginSubmit');

        submitBtn.disabled = true;
        submitBtn.textContent = 'Verifying Credentials...';

        localStorage.setItem('visualai_student_id', studentId);
        toast.style.display = 'block';
        toast.style.background = 'var(--peach-green-soft)';
        toast.style.color = 'var(--peach-green)';
        toast.style.border = '1px solid var(--peach-green-border)';
        toast.textContent = 'Verification successful. Launching assessment dashboard...';

        setTimeout(() => {
            window.location.href = '/dashboard?user_id=' + encodeURIComponent(studentId);
        }, 500);
    }
    </script>

    /*CANVAS_SCRIPT*/

</body>
</html>
""".replace("/*COMMON_STYLES*/", COMMON_STYLES).replace("/*CANVAS_SCRIPT*/", CANVAS_ANTIGRAVITY_SCRIPT)

# ---------------------------------------------------------------------------
# API Route Handlers
# ---------------------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
@router.get("/landing", response_class=HTMLResponse)
def get_landing_page() -> HTMLResponse:
    """Render the 3D rotating pole and specimen plates interactive landing page."""
    return HTMLResponse(content=LANDING_HTML)


@router.get("/signup", response_class=HTMLResponse)
def get_signup_page() -> HTMLResponse:
    """Render the student registration and onboarding page."""
    return HTMLResponse(content=SIGNUP_HTML)


@router.get("/login", response_class=HTMLResponse)
def get_login_page() -> HTMLResponse:
    """Render the student login verification page."""
    return HTMLResponse(content=LOGIN_HTML)
