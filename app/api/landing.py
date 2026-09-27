"""VisualAI - Landing, Authentication, and 3D Interactive Pedagogical Showcase.

Features:
- Central vertical pole extending from header to footer with glowing orbital nodes.
- 3D interactive helical plates containing study features rotating in 3D around the pole on scroll and drag.
- Front-face hero section with high-graphics typography, Get Started and Login buttons.
- Dedicated Sign-Up (/signup) and Login (/login) pages with instant validation and seamless redirection to /dashboard.
- Matching botanical floral theme + Antigravity interactive cursor particle animation.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["landing"])

# ---------------------------------------------------------------------------
# Common CSS Styles & Themes (Matching Dashboard Palette)
# ---------------------------------------------------------------------------
COMMON_STYLES = """
    :root {
        --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        --font-display: 'Playfair Display', Georgia, serif;

        --bg-page: #f4f6fa;
        --bg-card: rgba(244, 246, 250, 0.90);
        --bg-surface: rgba(248, 249, 250, 0.94);
        --bg-subtle: #e9edf5;

        --text-ink: #333333;
        --text-body: #4b5563;
        --text-muted: #6b7280;

        /* Peach Green & Botanical Color Palette */
        --peach-green: #2e7d5e;
        --peach-green-hover: #24664c;
        --peach-green-soft: #edf6f2;
        --peach-green-border: #9ecab4;
        --peach-green-shadow: rgba(46, 125, 94, 0.35);

        /* Warm Peach Accents */
        --peach: #df7456;
        --peach-hover: #c96245;
        --peach-soft: #fdf2ec;
        --peach-border: #f8c8b6;

        --border-card: rgba(226, 232, 240, 0.7);
        --radius-sm: 4px;
        --radius-md: 10px;
        --radius-lg: 18px;

        /* 3D Plate styling */
        --plate-bg: rgba(255, 255, 255, 0.88);
        --plate-border: rgba(46, 125, 94, 0.35);
        --plate-glow: rgba(46, 125, 94, 0.18);

        /* Botanical Floral Background Pattern (Light Mode) */
        --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%232e7d5e%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.11%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%23df7456%27%20fill-opacity%3D%270.25%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
    }

    [data-theme="dark"] {
        --bg-page: #14161b;
        --bg-card: rgba(26, 29, 36, 0.90);
        --bg-surface: rgba(30, 34, 42, 0.94);
        --bg-subtle: #1f232c;

        --text-ink: #f3f4f6;
        --text-body: #d1d5db;
        --text-muted: #9ca3af;

        /* Peach Green & Botanical Color Palette (Dark Mode) */
        --peach-green: #4ecb94;
        --peach-green-hover: #3db882;
        --peach-green-soft: rgba(78, 203, 148, 0.16);
        --peach-green-border: rgba(78, 203, 148, 0.45);
        --peach-green-shadow: rgba(78, 203, 148, 0.35);

        /* Warm Peach Accents (Dark Mode) */
        --peach: #f09a80;
        --peach-hover: #e28468;
        --peach-soft: rgba(240, 154, 128, 0.16);
        --peach-border: rgba(240, 154, 128, 0.45);

        --border-card: rgba(255, 255, 255, 0.08);

        /* 3D Plate styling (Dark Mode) */
        --plate-bg: rgba(26, 29, 36, 0.88);
        --plate-border: rgba(78, 203, 148, 0.45);
        --plate-glow: rgba(78, 203, 148, 0.22);

        /* Botanical Floral Background Pattern (Dark Mode) */
        --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%234ecb94%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.13%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%23f09a80%27%20fill-opacity%3D%270.28%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
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
        padding: 16px 36px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: var(--bg-card);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
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
        width: 40px;
        height: 40px;
        border-radius: 8px;
        background: var(--bg-surface);
        border: 1.5px solid var(--peach-green-border);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--peach-green);
        font-size: 20px;
        font-weight: 800;
        box-shadow: 0 4px 12px var(--peach-green-shadow);
    }

    .brand-title-group h1 {
        font-family: var(--font-display);
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: var(--text-ink);
    }
    .brand-title-group h1 span { color: var(--peach-green); }
    .brand-tagline-text {
        font-size: 9.5px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 1.4px;
        color: var(--peach);
        display: block;
    }

    .nav-buttons {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .nav-btn {
        padding: 9px 18px;
        border-radius: var(--radius-sm);
        font-size: 13.5px;
        font-weight: 600;
        text-decoration: none;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        border: 1px solid transparent;
    }

    .nav-btn-ghost {
        background: transparent;
        color: var(--text-ink);
        border-color: var(--border-card);
    }
    .nav-btn-ghost:hover {
        background: var(--bg-surface);
        color: var(--peach-green);
        border-color: var(--peach-green-border);
    }

    .nav-btn-cta {
        background: linear-gradient(135deg, var(--peach-green) 0%, var(--peach-green-hover) 100%);
        color: #ffffff !important;
        box-shadow: 0 4px 16px var(--peach-green-shadow);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .nav-btn-cta:hover {
        transform: translateY(-1.5px);
        box-shadow: 0 6px 20px var(--peach-green-shadow);
    }
"""

# ---------------------------------------------------------------------------
# Antigravity Canvas Script (Shared across Landing, Login, Signup)
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
            radius: 190,
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

        window.addEventListener('touchmove', function(e) {
            if (e.touches && e.touches.length > 0) {
                mouse.targetX = e.touches[0].clientX;
                mouse.targetY = e.touches[0].clientY;
                mouse.active = true;
            }
        }, { passive: true });

        function getPalette() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            return {
                petals: isDark
                    ? ['rgba(78, 203, 148, 0.45)', 'rgba(240, 154, 128, 0.48)', 'rgba(167, 243, 208, 0.35)', 'rgba(253, 226, 216, 0.35)']
                    : ['rgba(46, 125, 94, 0.35)', 'rgba(223, 116, 86, 0.38)', 'rgba(92, 184, 138, 0.30)', 'rgba(235, 148, 122, 0.30)'],
                pollen: isDark ? 'rgba(78, 203, 148, 0.65)' : 'rgba(46, 125, 94, 0.50)',
                center: isDark ? 'rgba(240, 154, 128, 0.70)' : 'rgba(223, 116, 86, 0.60)',
                line: isDark ? 'rgba(78, 203, 148, 0.12)' : 'rgba(46, 125, 94, 0.08)'
            };
        }

        class FloralParticle {
            constructor() {
                this.reset(true);
            }

            reset(initial) {
                this.x = Math.random() * (width || 1200);
                this.y = initial ? Math.random() * (height || 800) : (height + 25 + Math.random() * 40);
                this.size = 5 + Math.random() * 11;
                const randType = Math.random();
                this.type = randType > 0.55 ? 'petal' : (randType > 0.25 ? 'flower' : 'pollen');

                this.vx = (Math.random() - 0.5) * 0.45;
                this.vy = -(0.25 + Math.random() * 0.55);
                this.rotation = Math.random() * Math.PI * 2;
                this.rotSpeed = (Math.random() - 0.5) * 0.022;
                this.tilt = Math.random() * Math.PI;
                this.tiltSpeed = (Math.random() - 0.5) * 0.025;

                this.phase = Math.random() * Math.PI * 2;
                this.phaseSpeed = 0.012 + Math.random() * 0.018;

                this.fx = 0;
                this.fy = 0;
                this.colorIdx = Math.floor(Math.random() * 4);
            }

            update(time, palette) {
                this.phase += this.phaseSpeed;
                this.rotation += this.rotSpeed;
                this.tilt += this.tiltSpeed;

                this.x += this.vx + Math.sin(this.phase) * 0.4;
                this.y += this.vy;

                if (mouse.x > -1000 && mouse.y > -1000) {
                    const dx = this.x - mouse.x;
                    const dy = this.y - mouse.y;
                    const dist = Math.hypot(dx, dy);
                    const maxDist = mouse.radius;

                    if (dist < maxDist && dist > 1) {
                        const factor = 1 - dist / maxDist;
                        const angle = Math.atan2(dy, dx);
                        const swirl = angle + Math.PI * 0.38;
                        const push = factor * 4.4;
                        this.fx += Math.cos(angle) * push + Math.cos(swirl) * push * 0.4;
                        this.fy += Math.sin(angle) * push + Math.sin(swirl) * push * 0.4;
                        this.rotation += factor * 0.06;
                    }
                }

                this.x += this.fx;
                this.y += this.fy;
                this.fx *= 0.92;
                this.fy *= 0.92;

                if (this.y < -35) this.y = height + 25;
                if (this.y > height + 45) this.y = -25;
                if (this.x < -35) this.x = width + 25;
                if (this.x > width + 35) this.x = -25;
            }

            draw(ctx, palette) {
                ctx.save();
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation);
                const scaleY = Math.cos(this.tilt);
                ctx.scale(1, Math.abs(scaleY) < 0.12 ? 0.12 : scaleY);

                const color = palette.petals[this.colorIdx];
                ctx.fillStyle = color;
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.1;

                if (this.type === 'flower') {
                    const r = this.size * 0.62;
                    for (let i = 0; i < 5; i++) {
                        const a = (i * Math.PI * 2) / 5;
                        ctx.beginPath();
                        ctx.ellipse(Math.cos(a) * r, Math.sin(a) * r, r * 0.72, r * 0.42, a, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    ctx.beginPath();
                    ctx.arc(0, 0, r * 0.34, 0, Math.PI * 2);
                    ctx.fillStyle = palette.center;
                    ctx.fill();
                } else if (this.type === 'petal') {
                    const s = this.size;
                    ctx.beginPath();
                    ctx.moveTo(0, -s);
                    ctx.bezierCurveTo(s * 0.72, -s * 0.45, s * 0.75, s * 0.55, 0, s);
                    ctx.bezierCurveTo(-s * 0.75, s * 0.55, -s * 0.72, -s * 0.45, 0, -s);
                    ctx.fill();
                } else {
                    const pr = this.size * 0.32;
                    ctx.beginPath();
                    ctx.arc(0, 0, pr, 0, Math.PI * 2);
                    ctx.fillStyle = palette.pollen;
                    ctx.fill();
                }

                ctx.restore();
            }
        }

        const count = Math.min(55, Math.max(25, Math.floor((width * height) / 24000)));
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
                    if (distCursor < 210) {
                        for (let j = i + 1; j < particles.length; j++) {
                            const p2 = particles[j];
                            const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
                            if (d < 85) {
                                ctx.beginPath();
                                ctx.moveTo(p1.x, p1.y);
                                ctx.lineTo(p2.x, p2.y);
                                ctx.strokeStyle = palette.line;
                                ctx.lineWidth = (1 - d / 85) * 1.3;
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
        const icon = document.getElementById('themeToggleText');
        if (icon) icon.textContent = next === 'dark' ? '☀️ Light' : '🌙 Dark';
    }

    (function() {
        const saved = localStorage.getItem('visualai_theme');
        if (saved) {
            document.documentElement.setAttribute('data-theme', saved);
            const icon = document.getElementById('themeToggleText');
            if (icon) icon.textContent = saved === 'dark' ? '☀️ Light' : '🌙 Dark';
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
    <title>VisualAI — Study With Your Vision | Multimodal AI Learning & Video Remediation</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
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

        /* The Luminous Center Vertical Pole */
        .center-pole-wrapper {
            position: absolute;
            top: 0;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 32px;
            pointer-events: none;
            z-index: 2;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .center-pole {
            width: 8px;
            height: 100%;
            background: linear-gradient(180deg, 
                rgba(46, 125, 94, 0.05) 0%, 
                var(--peach-green) 15%, 
                var(--peach) 50%, 
                var(--peach-green) 85%, 
                rgba(46, 125, 94, 0.05) 100%);
            box-shadow: 0 0 20px var(--peach-green-shadow), 0 0 45px rgba(223, 116, 86, 0.35);
            border-radius: 999px;
            position: relative;
        }

        .pole-node {
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            width: 24px;
            height: 6px;
            border-radius: 999px;
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green);
            box-shadow: 0 0 15px var(--peach-green);
        }
        .node-1 { top: 18%; }
        .node-2 { top: 38%; }
        .node-3 { top: 58%; }
        .node-4 { top: 78%; }

        /* 3D Rotating Plates Cylinder */
        .carousel-3d-viewport {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            perspective: 1300px;
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

        /* Rotating Study Plates */
        .study-plate {
            position: absolute;
            width: 310px;
            min-height: 190px;
            left: -155px;
            top: -95px;
            border-radius: var(--radius-lg);
            padding: 22px;
            background: var(--plate-bg);
            border: 1.5px solid var(--plate-border);
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.16), 0 0 25px var(--plate-glow);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            transform-style: preserve-3d;
            backface-visibility: hidden;
            pointer-events: auto;
            cursor: grab;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            user-select: none;
        }

        .study-plate:active {
            cursor: grabbing;
        }

        .study-plate:hover {
            border-color: var(--peach-green);
            box-shadow: 0 25px 55px rgba(0, 0, 0, 0.22), 0 0 35px var(--peach-green-shadow);
        }

        .plate-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }

        .plate-icon-pill {
            width: 38px;
            height: 38px;
            border-radius: 10px;
            background: var(--peach-green-soft);
            color: var(--peach-green);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            border: 1px solid var(--peach-green-border);
        }

        .plate-badge {
            font-size: 10.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            padding: 4px 10px;
            border-radius: 999px;
            background: var(--peach-soft);
            color: var(--peach);
            border: 1px solid var(--peach-border);
        }

        .plate-title {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
            letter-spacing: -0.2px;
        }

        .plate-desc {
            font-size: 12.5px;
            color: var(--text-body);
            line-height: 1.55;
            margin-bottom: 12px;
        }

        .plate-metric-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 10px;
            border-top: 1px dashed var(--border-card);
            font-size: 11.5px;
            color: var(--text-muted);
        }

        .plate-metric-highlight {
            font-weight: 700;
            color: var(--peach-green);
        }

        /* Front Face Hero Card */
        .hero-foreground {
            position: relative;
            z-index: 10;
            max-width: 640px;
            padding: 42px 46px;
            border-radius: 24px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            box-shadow: 0 30px 70px rgba(0, 0, 0, 0.18), 0 0 40px var(--peach-green-shadow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            text-align: center;
            margin: 0 20px;
            animation: heroFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes heroFadeIn {
            0% { opacity: 0; transform: translateY(20px) scale(0.97); }
            100% { opacity: 1; transform: translateY(0) scale(1); }
        }

        .hero-superbadge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            border-radius: 999px;
            background: var(--peach-green-soft);
            color: var(--peach-green);
            font-size: 11px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 20px;
            border: 1px solid var(--peach-green-border);
        }

        .hero-title {
            font-family: var(--font-display);
            font-size: clamp(34px, 5vw, 52px);
            font-weight: 700;
            line-height: 1.15;
            letter-spacing: -0.8px;
            color: var(--text-ink);
            margin-bottom: 16px;
        }

        .hero-title .gradient-text {
            background: linear-gradient(135deg, var(--peach-green) 0%, #3db882 45%, var(--peach) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            font-size: 15.5px;
            color: var(--text-body);
            line-height: 1.65;
            margin-bottom: 34px;
            max-width: 520px;
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
            position: relative;
            padding: 14px 34px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff !important;
            text-decoration: none;
            background: linear-gradient(135deg, var(--peach-green) 0%, #35926c 50%, var(--peach) 100%);
            background-size: 200% 200%;
            border: 1px solid rgba(255, 255, 255, 0.25);
            box-shadow: 0 8px 26px var(--peach-green-shadow), 0 0 20px rgba(223, 116, 86, 0.3);
            display: inline-flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            overflow: hidden;
        }

        .btn-high-graphics-cta:hover {
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 12px 34px var(--peach-green-shadow), 0 0 30px rgba(223, 116, 86, 0.45);
            background-position: right center;
        }

        .btn-high-graphics-login {
            padding: 14px 28px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 600;
            color: var(--text-ink);
            text-decoration: none;
            background: var(--bg-surface);
            border: 1.5px solid var(--border-card);
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
            display: inline-flex;
            align-items: center;
            gap: 9px;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .btn-high-graphics-login:hover {
            border-color: var(--peach-green);
            color: var(--peach-green);
            transform: translateY(-2px);
            box-shadow: 0 6px 22px var(--peach-green-shadow);
        }

        .btn-demo-link {
            padding: 10px 18px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: color 0.2s ease;
            width: 100%;
            justify-content: center;
            margin-top: 10px;
        }
        .btn-demo-link:hover {
            color: var(--peach-green);
        }

        .scroll-interaction-hint {
            position: absolute;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            z-index: 10;
            background: var(--bg-card);
            padding: 6px 16px;
            border-radius: 999px;
            border: 1px solid var(--border-card);
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
            user-select: none;
        }

        .scroll-icon-wheel {
            width: 14px;
            height: 22px;
            border: 2px solid var(--peach-green);
            border-radius: 10px;
            position: relative;
        }

        .scroll-icon-wheel::before {
            content: '';
            position: absolute;
            top: 4px;
            left: 50%;
            transform: translateX(-50%);
            width: 3px;
            height: 5px;
            background: var(--peach);
            border-radius: 2px;
            animation: mouseScroll 1.6s infinite ease-in-out;
        }

        @keyframes mouseScroll {
            0% { opacity: 1; transform: translate(-50%, 0); }
            100% { opacity: 0; transform: translate(-50%, 8px); }
        }

        @media (max-width: 768px) {
            .hero-foreground { padding: 32px 24px; }
            .landing-header { padding: 12px 20px; }
            .study-plate { width: 260px; min-height: 175px; left: -130px; top: -87px; padding: 16px; }
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
                <span class="brand-tagline-text">STUDY WITH YOUR VISION</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme">
                <span id="themeToggleText">🌙 Dark</span>
            </button>
            <a href="/login" class="nav-btn nav-btn-ghost">Log In</a>
            <a href="/signup" class="nav-btn nav-btn-cta">Get Started</a>
        </div>
    </header>

    <div class="stage-container" id="stageContainer">

        <div class="center-pole-wrapper">
            <div class="center-pole">
                <div class="pole-node node-1"></div>
                <div class="pole-node node-2"></div>
                <div class="pole-node node-3"></div>
                <div class="pole-node node-4"></div>
            </div>
        </div>

        <div class="carousel-3d-viewport">
            <div class="carousel-3d-axis" id="carouselAxis">

                <div class="study-plate" data-index="0">
                    <div class="plate-header">
                        <div class="plate-icon-pill">📐</div>
                        <span class="plate-badge">Gemma 3 Vision</span>
                    </div>
                    <div class="plate-title">Visual Diagram RAG</div>
                    <div class="plate-desc">Ingests charts, circuit diagrams, and mathematical figures with 100% textbook evidence grounding.</div>
                    <div class="plate-metric-row">
                        <span>Local Inference</span>
                        <span class="plate-metric-highlight">0 Cloud Leaks</span>
                    </div>
                </div>

                <div class="study-plate" data-index="1">
                    <div class="plate-header">
                        <div class="plate-icon-pill">🎬</div>
                        <span class="plate-badge">Manim Engine</span>
                    </div>
                    <div class="plate-title">Algorithmic 60fps Video</div>
                    <div class="plate-desc">Transforms static theorems into fluid vector animations synchronized with Whisper speech timestamps.</div>
                    <div class="plate-metric-row">
                        <span>Resolution</span>
                        <span class="plate-metric-highlight">1080p Vector</span>
                    </div>
                </div>

                <div class="study-plate" data-index="2">
                    <div class="plate-header">
                        <div class="plate-icon-pill">🧬</div>
                        <span class="plate-badge">Mastery Graph</span>
                    </div>
                    <div class="plate-title">Prerequisite Mapping</div>
                    <div class="plate-desc">Maps foundational gaps across concept trees with authoritative 3-stage mastery state machines.</div>
                    <div class="plate-metric-row">
                        <span>Loop Prevention</span>
                        <span class="plate-metric-highlight">Kill-Switch Safe</span>
                    </div>
                </div>

                <div class="study-plate" data-index="3">
                    <div class="plate-header">
                        <div class="plate-icon-pill">⚡</div>
                        <span class="plate-badge">Micro-Lessons</span>
                    </div>
                    <div class="plate-title">Targeted Remediation</div>
                    <div class="plate-desc">Diagnoses exact incorrect options and generates dedicated 45-second animated remediation videos.</div>
                    <div class="plate-metric-row">
                        <span>Latency</span>
                        <span class="plate-metric-highlight">&lt; 60s On-Demand</span>
                    </div>
                </div>

                <div class="study-plate" data-index="4">
                    <div class="plate-header">
                        <div class="plate-icon-pill">🛡️</div>
                        <span class="plate-badge">Offline Stack</span>
                    </div>
                    <div class="plate-title">100% Local Intelligence</div>
                    <div class="plate-desc">Zero dependence on external OpenRouter endpoints or rate-limits. Operates offline via Ollama.</div>
                    <div class="plate-metric-row">
                        <span>Architecture</span>
                        <span class="plate-metric-highlight">Gemma3 + Llama3.2</span>
                    </div>
                </div>

                <div class="study-plate" data-index="5">
                    <div class="plate-header">
                        <div class="plate-icon-pill">📊</div>
                        <span class="plate-badge">Human-in-Loop</span>
                    </div>
                    <div class="plate-title">Instructor Interventions</div>
                    <div class="plate-desc">Cohort-wide mastery telemetry, human intervention overrides, and transparent learning analytics.</div>
                    <div class="plate-metric-row">
                        <span>Telemetry</span>
                        <span class="plate-metric-highlight">Live Telemetry</span>
                    </div>
                </div>

            </div>
        </div>

        <div class="hero-foreground">
            <div class="hero-superbadge">🌿 Next-Gen Visual Pedagogical Engine</div>
            <h1 class="hero-title">
                Study With <br><span class="gradient-text">Your Vision</span>
            </h1>
            <p class="hero-subtitle">
                Transform textbook proofs, diagrams, and coursework into interactive concept graphs and algorithmic video animations tailored to your exact learning gaps.
            </p>
            <div class="hero-actions">
                <a href="/signup" id="btnHeroGetStarted" class="btn-high-graphics-cta">
                    <span>Get Started</span>
                    <span>→</span>
                </a>
                <a href="/login" id="btnHeroLogin" class="btn-high-graphics-login">
                    <span>👤</span>
                    <span>Log In</span>
                </a>
            </div>
            <a href="/dashboard" id="btnHeroDemo" class="btn-demo-link">
                <span>⚡ Explore Live Assessment Dashboard →</span>
            </a>
        </div>

        <div class="scroll-interaction-hint">
            <div class="scroll-icon-wheel"></div>
            <span>Scroll or drag anywhere to rotate 3D study plates around the central pole</span>
        </div>

    </div>

    <script>
    (function init3DPlatePoleCarousel() {
        const axis = document.getElementById('carouselAxis');
        const plates = document.querySelectorAll('.study-plate');
        if (!axis || !plates.length) return;

        let currentAngle = 0;
        let targetAngle = 0;
        let isDragging = false;
        let startX = 0;
        let autoDriftSpeed = 0.05;

        const numPlates = plates.length;
        const radius = Math.min(window.innerWidth * 0.36, 420);

        function updatePlatePositions(baseAngle) {
            plates.forEach((plate, i) => {
                const angleDeg = (i * (360 / numPlates)) + baseAngle;
                const rad = (angleDeg * Math.PI) / 180;
                const verticalOffset = (i - 2.5) * 58;

                const x = Math.sin(rad) * radius;
                const z = Math.cos(rad) * radius;

                plate.style.transform = 'translate3d(' + x.toFixed(1) + 'px, ' + verticalOffset.toFixed(1) + 'px, ' + z.toFixed(1) + 'px) rotateY(' + angleDeg.toFixed(1) + 'deg)';

                const depthNormalized = (z + radius) / (2 * radius);
                plate.style.opacity = Math.max(0.35, depthNormalized * 1.05);
                plate.style.zIndex = Math.round(depthNormalized * 10);
            });
        }

        window.addEventListener('wheel', (e) => {
            targetAngle += e.deltaY * 0.16;
        }, { passive: true });

        window.addEventListener('mousedown', (e) => {
            if (e.target.closest('.hero-actions') || e.target.closest('.landing-header')) return;
            isDragging = true;
            startX = e.clientX;
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const deltaX = e.clientX - startX;
            targetAngle += deltaX * 0.35;
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
                targetAngle += deltaX * 0.45;
                startX = e.touches[0].clientX;
            }
        }, { passive: true });

        function loop() {
            requestAnimationFrame(loop);
            targetAngle += autoDriftSpeed;
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
# 2. SIGN UP PAGE HTML
# ---------------------------------------------------------------------------
SIGNUP_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Get Started | Create Learning Account</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
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
            border-radius: 20px;
            padding: 36px 40px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.16), 0 0 35px var(--peach-green-shadow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            animation: cardAppear 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes cardAppear {
            0% { opacity: 0; transform: translateY(16px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .auth-header {
            text-align: center;
            margin-bottom: 28px;
        }

        .auth-logo-badge {
            width: 48px;
            height: 48px;
            margin: 0 auto 14px;
            border-radius: 12px;
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--peach-green);
            font-size: 24px;
            font-weight: 800;
            box-shadow: 0 6px 18px var(--peach-green-shadow);
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
            font-size: 12.5px;
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
            padding: 14px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(135deg, var(--peach-green) 0%, #35926c 50%, var(--peach) 100%);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 24px var(--peach-green-shadow);
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.25s ease;
        }

        .btn-auth-submit:hover {
            transform: translateY(-1.5px);
            box-shadow: 0 10px 30px var(--peach-green-shadow);
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
                <span class="brand-tagline-text">STUDY WITH YOUR VISION</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme">
                <span id="themeToggleText">🌙 Dark</span>
            </button>
            <a href="/login" class="nav-btn nav-btn-ghost">Log In</a>
        </div>
    </header>

    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-header">
                <div class="auth-logo-badge">V</div>
                <h2 class="auth-title">Create Your Account</h2>
                <p class="auth-subtitle">Start your visual pedagogical learning journey today</p>
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
                    Get Started & Enter Dashboard →
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
        toast.textContent = 'Account created successfully! Launching dashboard...';

        setTimeout(() => {
            window.location.href = '/dashboard?user_id=' + encodeURIComponent(studentId);
        }, 600);
    }
    </script>

    /*CANVAS_SCRIPT*/

</body>
</html>
""".replace("/*COMMON_STYLES*/", COMMON_STYLES).replace("/*CANVAS_SCRIPT*/", CANVAS_ANTIGRAVITY_SCRIPT)

# ---------------------------------------------------------------------------
# 3. LOGIN PAGE HTML
# ---------------------------------------------------------------------------
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Log In | Student Assessment Console</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
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
            border-radius: 20px;
            padding: 38px 40px;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.16), 0 0 35px var(--peach-green-shadow);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            animation: cardAppear 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        @keyframes cardAppear {
            0% { opacity: 0; transform: translateY(16px); }
            100% { opacity: 1; transform: translateY(0); }
        }

        .auth-header {
            text-align: center;
            margin-bottom: 28px;
        }

        .auth-logo-badge {
            width: 48px;
            height: 48px;
            margin: 0 auto 14px;
            border-radius: 12px;
            background: var(--bg-surface);
            border: 1.5px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--peach-green);
            font-size: 24px;
            font-weight: 800;
            box-shadow: 0 6px 18px var(--peach-green-shadow);
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
            font-size: 12.5px;
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
            padding: 14px;
            border-radius: var(--radius-sm);
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(135deg, var(--peach-green) 0%, #35926c 50%, var(--peach) 100%);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 24px var(--peach-green-shadow);
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.25s ease;
        }

        .btn-auth-submit:hover {
            transform: translateY(-1.5px);
            box-shadow: 0 10px 30px var(--peach-green-shadow);
        }

        .btn-quick-demo {
            width: 100%;
            padding: 11px;
            border-radius: var(--radius-sm);
            font-size: 13.5px;
            font-weight: 600;
            color: var(--text-ink);
            background: var(--bg-surface);
            border: 1px dashed var(--peach-green-border);
            cursor: pointer;
            margin-top: 12px;
            transition: all 0.2s ease;
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
                <span class="brand-tagline-text">STUDY WITH YOUR VISION</span>
            </div>
        </a>
        <div class="nav-buttons">
            <button class="nav-btn nav-btn-ghost" onclick="toggleTheme()" title="Toggle Theme">
                <span id="themeToggleText">🌙 Dark</span>
            </button>
            <a href="/signup" class="nav-btn nav-btn-cta">Sign Up</a>
        </div>
    </header>

    <div class="auth-container">
        <div class="auth-card">
            <div class="auth-header">
                <div class="auth-logo-badge">V</div>
                <h2 class="auth-title">Welcome Back</h2>
                <p class="auth-subtitle">Enter your student ID to resume your learning session</p>
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
                    ⚡ 1-Click Demo Login (student_123)
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
        toast.textContent = 'Verification successful! Loading learning dashboard...';

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
    """Render the 3D rotating pole and plates interactive landing page."""
    return HTMLResponse(content=LANDING_HTML)


@router.get("/signup", response_class=HTMLResponse)
def get_signup_page() -> HTMLResponse:
    """Render the student registration and onboarding page."""
    return HTMLResponse(content=SIGNUP_HTML)


@router.get("/login", response_class=HTMLResponse)
def get_login_page() -> HTMLResponse:
    """Render the student login verification page."""
    return HTMLResponse(content=LOGIN_HTML)
