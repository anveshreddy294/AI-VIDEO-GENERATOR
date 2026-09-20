"""VisualAI Dashboard — Interactive Assessment Console & Pipeline Documentation.

Neomorphic Charcoal (#333333) & Peach Green (#32805b) theme on porcelain canvas (#f4f6fa)
with live telemetry, transparent quiz grading, video player with downloads,
Dual-Layer Video RAG, and Anti-Loop Kill Switch protection.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VisualAI — Interactive Assessment Console | STUDY WITH YOUR VISION</title>
    <!-- Google Fonts: Editorial Serif + Humanist Sans -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,600&family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            --font-display: 'Playfair Display', Georgia, serif;

            --bg-page: #f4f6fa;
            --bg-card: #f4f6fa;
            --bg-surface: #ffffff;
            --bg-subtle: #e9edf5;

            --text-ink: #333333;
            --text-body: #4b5563;
            --text-muted: #6b7280;

            /* 🌿 Peach Green & Botanical Color Palette */
            --peach-green: #2e7d5e;
            --peach-green-hover: #24664c;
            --peach-green-soft: #edf6f2;
            --peach-green-border: #9ecab4;
            --peach-green-shadow: rgba(46, 125, 94, 0.32);

            /* 🍑 Warm Peach Accents */
            --peach: #df7456;
            --peach-hover: #c96245;
            --peach-soft: #fdf2ec;
            --peach-border: #f8c8b6;

            /* Compatibility aliases mapping gold directly to peach-green */
            --gold: var(--peach-green);
            --gold-hover: var(--peach-green-hover);
            --gold-soft: var(--peach-green-soft);
            --gold-border: var(--peach-green-border);
            --charcoal: #333333;

            --emerald: #059669;
            --emerald-soft: #ecfdf5;
            --emerald-border: #a7f3d0;

            --rose: #dc2626;
            --rose-soft: #fef2f2;
            --rose-border: #fecaca;

            --amber: #d97706;
            --amber-soft: #fffbeb;
            --amber-border: #fde68a;

            --blue: #2563eb;
            --blue-soft: #eff6ff;
            --blue-border: #bfdbfe;

            /* 🪨 Tactile Neomorphism Shadows (Light Mode) */
            --neo-raised: 7px 7px 16px rgba(180, 192, 210, 0.45), -7px -7px 16px rgba(255, 255, 255, 0.95);
            --neo-raised-sm: 4px 4px 10px rgba(180, 192, 210, 0.4), -4px -4px 10px rgba(255, 255, 255, 0.95);
            --neo-raised-lg: 12px 12px 28px rgba(180, 192, 210, 0.5), -12px -12px 28px rgba(255, 255, 255, 0.95);
            --neo-inset: inset 3px 3px 7px rgba(180, 192, 210, 0.4), inset -3px -3px 7px rgba(255, 255, 255, 0.95);
            --neo-btn: 5px 5px 12px rgba(180, 192, 210, 0.45), -5px -5px 12px rgba(255, 255, 255, 0.9);
            --neo-btn-active: inset 2px 2px 5px rgba(180, 192, 210, 0.5), inset -2px -2px 5px rgba(255, 255, 255, 0.9);
            --border-card: rgba(226, 232, 240, 0.6);

            --radius-sm: 10px;
            --radius-md: 16px;
            --radius-lg: 24px;
        }

        [data-theme="dark"] {
            --bg-page: #18191e;
            --bg-card: #22242c;
            --bg-surface: #262832;
            --bg-subtle: #1f2026;

            --text-ink: #f3f4f6;
            --text-body: #d1d5db;
            --text-muted: #9ca3af;

            /* 🌿 Peach Green & Botanical Color Palette (Dark Mode) */
            --peach-green: #4ecb94;
            --peach-green-hover: #3db882;
            --peach-green-soft: rgba(78, 203, 148, 0.16);
            --peach-green-border: rgba(78, 203, 148, 0.38);
            --peach-green-shadow: rgba(78, 203, 148, 0.28);

            /* 🍑 Warm Peach Accents (Dark Mode) */
            --peach: #f09a80;
            --peach-hover: #e28468;
            --peach-soft: rgba(240, 154, 128, 0.16);
            --peach-border: rgba(240, 154, 128, 0.38);

            /* Compatibility aliases mapping gold directly to peach-green */
            --gold: var(--peach-green);
            --gold-hover: var(--peach-green-hover);
            --gold-soft: var(--peach-green-soft);
            --gold-border: var(--peach-green-border);

            --emerald-soft: rgba(5, 150, 105, 0.15);
            --emerald-border: rgba(5, 150, 105, 0.4);

            --rose-soft: rgba(220, 38, 38, 0.15);
            --rose-border: rgba(220, 38, 38, 0.4);

            --amber-soft: rgba(217, 119, 6, 0.15);
            --amber-border: rgba(217, 119, 6, 0.4);

            --blue-soft: rgba(37, 99, 235, 0.15);
            --blue-border: rgba(37, 99, 235, 0.4);

            /* 🪨 Tactile Neomorphism Shadows (Dark Mode) */
            --neo-raised: 6px 6px 15px #101114, -6px -6px 15px #2c2f3a;
            --neo-raised-sm: 3px 3px 8px #101114, -3px -3px 8px #2c2f3a;
            --neo-raised-lg: 12px 12px 28px #101114, -12px -12px 28px #2c2f3a;
            --neo-inset: inset 3px 3px 6px #101114, inset -3px -3px 6px #2c2f3a;
            --neo-btn: 4px 4px 10px #101114, -4px -4px 10px #2c2f3a;
            --neo-btn-active: inset 2px 2px 5px #101114, inset -2px -2px 5px #2c2f3a;
            --border-card: rgba(255, 255, 255, 0.06);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-sans);
            background-color: var(--bg-page);
            color: var(--text-ink);
            line-height: 1.6;
            min-height: 100vh;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        /* 🌟 Fixed Top Navigation Bar */
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 50;
            background: rgba(244, 246, 250, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-card);
            padding: 14px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.3s ease;
        }

        [data-theme="dark"] .header {
            background: rgba(24, 25, 30, 0.85);
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-monogram {
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background: var(--bg-card);
            box-shadow: var(--neo-raised-sm);
            border: 1px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--peach-green);
            font-size: 20px;
            font-weight: 800;
        }

        .brand-title {
            font-family: var(--font-display);
            font-size: 22px;
            font-weight: 700;
            color: var(--text-ink);
            letter-spacing: -0.3px;
        }

        .brand-title span {
            color: var(--peach-green);
        }

        .brand-tagline {
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            color: var(--peach);
            display: block;
        }

        .nav-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .neo-btn {
            background: var(--bg-card);
            color: var(--text-ink);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 9px 18px;
            font-family: var(--font-sans);
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: var(--neo-btn);
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            text-decoration: none;
        }

        .neo-btn:hover {
            transform: translateY(-1px);
            color: var(--peach-green);
        }

        .neo-btn:active {
            transform: translateY(0);
            box-shadow: var(--neo-btn-active);
        }

        .neo-btn-gold, .neo-btn-peach-green {
            background: linear-gradient(135deg, var(--peach-green), var(--peach-green-hover));
            color: #ffffff;
            border: none;
            box-shadow: 0 4px 14px var(--peach-green-shadow);
        }

        .neo-btn-gold:hover, .neo-btn-peach-green:hover {
            color: #ffffff;
            filter: brightness(1.08);
            transform: translateY(-1px);
            box-shadow: 0 6px 18px var(--peach-green-shadow);
        }

        .neo-btn-peach {
            background: linear-gradient(135deg, var(--peach), var(--peach-hover));
            color: #ffffff;
            border: none;
            box-shadow: 0 4px 14px rgba(223, 116, 86, 0.32);
        }

        .neo-btn-peach:hover {
            color: #ffffff;
            filter: brightness(1.08);
            transform: translateY(-1px);
        }

        .neo-icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--bg-card);
            color: var(--text-ink);
            border: 1px solid var(--border-card);
            box-shadow: var(--neo-btn);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .neo-icon-btn:hover {
            color: var(--peach-green);
        }

        .neo-icon-btn:active {
            box-shadow: var(--neo-btn-active);
        }

        /* 🚀 Main Page Container */
        .container {
            max-width: 1140px;
            margin: 0 auto;
            padding: 104px 24px 60px;
        }

        /* 🏛 Hero Section & Animated Stat Counters */
        .hero {
            text-align: center;
            padding: 30px 10px 40px;
        }

        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 999px;
            background: var(--bg-card);
            box-shadow: var(--neo-raised-sm);
            border: 1px solid var(--peach-green-border);
            font-size: 11px;
            font-weight: 700;
            color: var(--peach-green);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 16px;
        }

        .hero-title {
            font-family: var(--font-display);
            font-size: clamp(32px, 5vw, 48px);
            font-weight: 700;
            color: var(--text-ink);
            line-height: 1.15;
            margin-bottom: 14px;
            letter-spacing: -0.5px;
        }

        .hero-subtitle {
            font-size: 16px;
            color: var(--text-muted);
            max-width: 720px;
            margin: 0 auto 36px;
            line-height: 1.6;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            padding: 22px;
            box-shadow: var(--neo-raised);
            text-align: center;
            transition: transform 0.2s ease;
        }

        .stat-card:hover {
            transform: translateY(-2px);
        }

        .stat-number {
            font-family: var(--font-display);
            font-size: 32px;
            font-weight: 700;
            color: var(--peach-green);
            margin-bottom: 4px;
        }

        .stat-label {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: var(--text-muted);
        }

        /* 🪟 Neomorphic Main Console Card */
        .console-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 36px;
            box-shadow: var(--neo-raised-lg);
            margin-bottom: 50px;
        }

        .console-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 28px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .console-title-area h2 {
            font-family: var(--font-display);
            font-size: 24px;
            font-weight: 700;
            color: var(--text-ink);
        }

        .console-title-area p {
            font-size: 13px;
            color: var(--text-muted);
            margin-top: 2px;
        }

        /* 🎚 Neomorphic Tab Switcher */
        .tab-switcher {
            display: inline-flex;
            background: var(--bg-card);
            box-shadow: var(--neo-inset);
            border-radius: 12px;
            padding: 4px;
            gap: 4px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            padding: 8px 18px;
            border-radius: 10px;
            font-family: var(--font-sans);
            font-size: 13px;
            font-weight: 600;
            color: var(--text-muted);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .tab-btn.active {
            background: var(--bg-surface);
            color: var(--text-ink);
            box-shadow: var(--neo-raised-sm);
        }

        [data-theme="dark"] .tab-btn.active {
            background: #2b2e38;
            color: var(--peach-green);
        }

        /* 📥 Forms & Inset Inputs */
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-label {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-ink);
        }

        .neo-input, .neo-select {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 12px 16px;
            font-family: var(--font-sans);
            font-size: 14px;
            color: var(--text-ink);
            box-shadow: var(--neo-inset);
            outline: none;
            transition: border-color 0.2s ease;
            width: 100%;
        }

        .neo-input:focus, .neo-select:focus {
            border-color: var(--peach-green);
        }

        .dropzone-area {
            border: 2px dashed var(--peach-green-border);
            background: var(--bg-card);
            box-shadow: var(--neo-inset);
            border-radius: var(--radius-md);
            padding: 36px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            margin-bottom: 24px;
        }

        .dropzone-area:hover {
            border-color: var(--peach-green);
            background: var(--peach-green-soft);
        }

        .dropzone-icon {
            font-size: 32px;
            margin-bottom: 8px;
        }

        /* 🚀 Live Pipeline Telemetry Timeline Card */
        .timeline-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            padding: 24px;
            margin: 28px 0;
            box-shadow: var(--neo-raised);
            animation: fadeIn 0.3s ease-out;
        }

        .timeline-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }

        .timeline-title-area {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .timeline-pulse-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--peach-green);
            box-shadow: 0 0 0 0 var(--peach-green-shadow);
            animation: pulse-ring 1.8s infinite;
        }

        @keyframes pulse-ring {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 var(--peach-green-shadow); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 8px rgba(46, 125, 94, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 var(--peach-green-shadow); }
        }

        .progress-bar-bg {
            background: var(--bg-card);
            box-shadow: var(--neo-inset);
            border-radius: 999px;
            height: 10px;
            overflow: hidden;
            margin-bottom: 20px;
        }

        .progress-bar-fill {
            background: linear-gradient(90deg, var(--peach-green), #4ecb94);
            height: 100%;
            border-radius: 999px;
            transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .timeline-stages-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .stage-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 14px;
            border-radius: var(--radius-sm);
            background: var(--bg-surface);
            box-shadow: var(--neo-raised-sm);
            font-size: 13px;
        }

        .stage-icon {
            flex-shrink: 0;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 12px;
        }

        .status-running .stage-icon { background: var(--amber-soft); color: var(--amber); }
        .status-completed .stage-icon { background: var(--emerald-soft); color: var(--emerald); }
        .status-failed .stage-icon { background: var(--rose-soft); color: var(--rose); }

        /* 📋 Diagnostic Assessment Quiz Section */
        .quiz-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            padding: 28px;
            box-shadow: var(--neo-raised);
            margin-top: 28px;
        }

        .quiz-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-card);
        }

        .question-stem {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-ink);
            line-height: 1.5;
            margin-bottom: 20px;
        }

        .options-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 28px;
        }

        .option-item {
            display: flex;
            align-items: flex-start;
            gap: 14px;
            padding: 14px 18px;
            border-radius: var(--radius-sm);
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            box-shadow: var(--neo-raised-sm);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .option-item:hover {
            transform: translateX(2px);
            border-color: var(--peach-green);
        }

        .option-item input[type="radio"] {
            margin-top: 4px;
            accent-color: var(--peach-green);
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .badge-peach-green, .badge-gold { background: var(--peach-green-soft); color: var(--peach-green); border: 1px solid var(--peach-green-border); }
        .badge-peach { background: var(--peach-soft); color: var(--peach); border: 1px solid var(--peach-border); }
        .badge-green { background: var(--emerald-soft); color: var(--emerald); border: 1px solid var(--emerald-border); }
        .badge-rose { background: var(--rose-soft); color: var(--rose); border: 1px solid var(--rose-border); }
        .badge-amber { background: var(--amber-soft); color: var(--amber); border: 1px solid var(--amber-border); }
        .badge-blue { background: var(--blue-soft); color: var(--blue); border: 1px solid var(--blue-border); }

        /* 🔍 Transparent Question Review Cards */
        .review-card {
            border-radius: var(--radius-sm);
            padding: 20px;
            margin-bottom: 16px;
            background: var(--bg-card);
            box-shadow: var(--neo-raised-sm);
            border: 1px solid var(--border-card);
        }

        .review-correct { border-left: 5px solid var(--emerald); }
        .review-incorrect { border-left: 5px solid var(--rose); }

        /* 🎥 Video Target Matrix Cards */
        .target-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 20px;
            box-shadow: var(--neo-raised-sm);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 14px;
        }

        /* 🎥 Video Modal Overlay */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(8px);
            z-index: 100;
            display: none;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .modal-card {
            background: var(--bg-page);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 860px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            padding: 28px;
        }

        .meta-chip {
            background: var(--bg-card);
            box-shadow: var(--neo-raised-sm);
            border: 1px solid var(--border-card);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            color: var(--text-body);
        }

        /* 🗺 Flow Architecture Documentation */
        .flow-section {
            margin-top: 60px;
        }

        .flow-title {
            font-family: var(--font-display);
            font-size: 28px;
            font-weight: 700;
            color: var(--text-ink);
            margin-bottom: 6px;
        }

        .step-card {
            display: flex;
            gap: 24px;
            padding: 24px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            margin-bottom: 16px;
            box-shadow: var(--neo-raised);
        }

        .step-num {
            flex-shrink: 0;
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: var(--bg-card);
            box-shadow: var(--neo-raised-sm);
            border: 1px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: var(--font-display);
            font-size: 20px;
            font-weight: 700;
            color: var(--peach-green);
        }

        /* ❓ FAQ Accordion */
        .faq-item {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            margin-bottom: 12px;
            box-shadow: var(--neo-raised-sm);
            overflow: hidden;
        }

        .faq-btn {
            width: 100%;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: transparent;
            border: none;
            font-family: var(--font-sans);
            font-size: 15px;
            font-weight: 600;
            color: var(--text-ink);
            cursor: pointer;
            text-align: left;
        }

        .faq-btn:hover {
            color: var(--peach-green);
        }

        .faq-content {
            display: none;
            padding: 0 20px 16px;
            font-size: 14px;
            color: var(--text-body);
            line-height: 1.6;
        }

        /* 🏛 Multi-Column Luxury Footer */
        .footer {
            margin-top: 80px;
            padding-top: 40px;
            border-top: 1px solid var(--border-card);
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            font-size: 13px;
            color: var(--text-muted);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>

    <!-- 🌟 Fixed Top Navigation Bar -->
    <header class="header">
        <div class="header-brand">
            <div class="brand-monogram">V</div>
            <div>
                <span class="brand-title">Visual<span>AI</span></span>
                <span class="brand-tagline">STUDY WITH YOUR VISION</span>
            </div>
        </div>
        <div class="nav-actions">
            <button id="themeToggleBtn" class="neo-icon-btn" onclick="toggleTheme()" title="Toggle Theme (Light / Dark)">
                <span id="themeIcon">🌓</span>
            </button>
            <a href="/instructor" target="_blank" class="neo-btn">
                <span>👩‍🏫 Instructor Portal</span>
            </a>
            <a href="/docs" target="_blank" class="neo-btn">
                <span>API Docs</span>
            </a>
            <a href="/health" target="_blank" class="neo-btn">
                <span>System Health</span>
            </a>
        </div>
    </header>

    <main class="container">

        <!-- 🏛 Hero Overview -->
        <section class="hero">
            <div class="hero-badge">Adaptive Pedagogical Pipeline</div>
            <h1 class="hero-title">Study With Your Vision</h1>
            <p class="hero-subtitle">
                Transform static study materials into programmatic, personalized visual lessons grounded strictly in authoritative textbooks without hallucination loops.
            </p>

            <!-- 📊 Animated Statistics Counters -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" data-target="4">0</div>
                    <div class="stat-label">Adaptive Pipeline Phases</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" data-target="60" data-prefix="< " data-suffix="s">0</div>
                    <div class="stat-label">Diagnostic Latency</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" data-target="100" data-suffix="%">0</div>
                    <div class="stat-label">Layer A Ground Truth</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" data-target="0" data-suffix="%">0</div>
                    <div class="stat-label">Hallucination Propagation</div>
                </div>
            </div>
        </section>

        <!-- 🪟 Neomorphic Main Console Card -->
        <section class="console-card">
            <div class="console-header">
                <div class="console-title-area">
                    <h2>Interactive Assessment Control</h2>
                    <p>Execute end-to-end multimodal ingestion, diagnostic profiling, and video synthesis</p>
                </div>
                <div class="tab-switcher">
                    <button class="tab-btn active" id="tabUpload" onclick="switchTab('upload')">📁 Ingest New Material</button>
                    <button class="tab-btn" id="tabExisting" onclick="switchTab('existing')">📚 Existing Course</button>
                </div>
            </div>

            <!-- Pane 1: Upload Material -->
            <div id="paneUpload">
                <div class="dropzone-area" onclick="document.getElementById('fileInput').click()">
                    <div class="dropzone-icon">📄</div>
                    <div style="font-weight:700;font-size:15px;color:var(--text-ink);margin-bottom:4px;">
                        Drop Course PDF, Notes, Images, or Video Here
                    </div>
                    <div style="font-size:13px;color:var(--text-muted);margin-bottom:12px;">
                        Supports PDF, PNG, JPG, TXT, and MP4 (Up to 100MB)
                    </div>
                    <button type="button" class="neo-btn" style="pointer-events:none;">
                        <span>Browse Files</span>
                    </button>
                    <input type="file" id="fileInput" style="display:none;" onchange="handleFileSelected()" />
                </div>
                <div id="selectedFileInfo" style="display:none;margin-bottom:16px;font-size:13px;font-weight:600;color:var(--peach-green);"></div>

                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label" for="studentId">Student Identifier</label>
                        <input type="text" id="studentId" class="neo-input" value="student_1" placeholder="e.g. student_1" />
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="maxQuestions">Diagnostic Questions</label>
                        <input type="number" id="maxQuestions" class="neo-input" value="5" min="1" max="15" />
                    </div>
                </div>
                <button class="neo-btn neo-btn-peach-green" id="btnUpload" onclick="runUpload()" style="width:100%;justify-content:center;padding:14px;">
                    <span>⚡ Ingest Material &amp; Start Diagnostic Assessment</span>
                </button>
            </div>

            <!-- Pane 2: Select Existing Course -->
            <div id="paneExisting" style="display:none;">
                <div class="form-grid">
                    <div class="form-group" style="grid-column:1/-1;">
                        <label class="form-label" for="sourceSelect">Select Ingested Material</label>
                        <select id="sourceSelect" class="neo-select">
                            <option value="">Loading course catalog...</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="studentIdExisting">Student Identifier</label>
                        <input type="text" id="studentIdExisting" class="neo-input" value="student_1" />
                    </div>
                    <div class="form-group">
                        <label class="form-label" for="maxQuestionsExisting">Diagnostic Questions</label>
                        <input type="number" id="maxQuestionsExisting" class="neo-input" value="5" min="1" max="15" />
                    </div>
                </div>
                <button class="neo-btn neo-btn-peach-green" id="btnAssessExisting" onclick="runExistingAssess()" style="width:100%;justify-content:center;padding:14px;">
                    <span>⚡ Generate Diagnostic Quiz from Material</span>
                </button>
            </div>

            <!-- 🚀 Live Pipeline Telemetry Timeline Card -->
            <div id="timelineCard" class="timeline-card" style="display:none;">
                <div class="timeline-header">
                    <div class="timeline-title-area">
                        <span class="timeline-pulse-dot" id="timelinePulse"></span>
                        <span style="font-weight:700;font-size:15px;">Pipeline Execution Telemetry</span>
                    </div>
                    <div style="font-weight:700;font-size:14px;color:var(--peach-green);">
                        <span id="timelineTimer">0.0s</span> &middot; <span id="timelinePercent">0%</span>
                    </div>
                </div>
                <div class="progress-bar-bg">
                    <div id="timelineProgressBar" class="progress-bar-fill" style="width:0%;"></div>
                </div>
                <div id="timelineStagesList" class="timeline-stages-list"></div>
            </div>

            <!-- Status Box -->
            <div id="statusBox" style="display:none;padding:14px;border-radius:var(--radius-sm);margin:20px 0;font-size:14px;font-weight:600;"></div>

            <!-- 📋 Diagnostic Assessment Quiz Section -->
            <div id="quizSection" class="quiz-card" style="display:none;">
                <div class="quiz-header">
                    <div>
                        <span class="badge badge-peach-green" id="lblConceptBadge">CONCEPT</span>
                        <span style="font-size:13px;color:var(--text-muted);margin-left:8px;" id="lblQuestionCounter">Question 1 of 5</span>
                    </div>
                    <span class="badge badge-blue">PHASE 2 DIAGNOSTIC</span>
                </div>
                <div class="question-stem" id="lblQuestionStem"></div>
                <div class="options-list" id="optionsContainer"></div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:12px;color:var(--text-muted);">Options shuffled via Fisher-Yates</span>
                    <button class="neo-btn neo-btn-peach-green" id="btnNextQuestion" onclick="submitCurrentAnswer()">
                        <span>Next Question ➔</span>
                    </button>
                </div>
            </div>

            <!-- 🔍 Detailed Question Review Section -->
            <div id="quizReviewSection" style="display:none;margin-top:28px;">
                <div style="font-family:var(--font-display);font-size:22px;font-weight:700;margin-bottom:6px;">Diagnostic Assessment Review</div>
                <p style="font-size:13px;color:var(--text-muted);margin-bottom:18px;">Inspect your submissions against authoritative textbook ground truth.</p>
                <div id="quizReviewContainer"></div>
            </div>

            <!-- 🎯 Diagnostic Score & Profile Summary -->
            <div id="resultsBox" class="quiz-card" style="display:none;margin-top:28px;">
                <div class="quiz-header">
                    <span style="font-weight:700;font-size:16px;">Student Learning Profile &amp; Knowledge Summary</span>
                    <div id="lblGradeStatus"></div>
                </div>
                <div class="form-grid" style="margin-bottom:16px;">
                    <div class="stat-card" style="padding:16px;">
                        <div class="stat-number" id="lblScore">0.0%</div>
                        <div class="stat-label" id="lblFraction">Score</div>
                    </div>
                    <div class="stat-card" style="padding:16px;">
                        <div class="stat-number" id="lblProfileScore">0.0%</div>
                        <div class="stat-label">Cumulative Mastery</div>
                    </div>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:8px;">Concept Mastery Breakdown</div>
                    <div id="lblMasteries" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
                </div>
                <div id="boxPrereqs" style="display:none;background:var(--amber-soft);border:1px solid var(--amber-border);border-radius:var(--radius-sm);padding:14px;margin-top:14px;color:var(--amber);">
                    <div style="font-weight:700;font-size:13px;margin-bottom:4px;">⚠ Prerequisite Gaps Identified</div>
                    <div id="lblPrereqs" style="font-size:13px;"></div>
                </div>
            </div>

        </section>

        <!-- 🗺 Architectural Pipeline Flow Documentation -->
        <section class="flow-section">
            <div style="margin-bottom:8px;">
                <h2 class="flow-title">The Multimodal Assessment Pipeline</h2>
                <p style="font-size:15px;color:var(--text-muted);">Modular, loosely coupled architecture transforming raw study materials into personalized knowledge graphs and diagnostic quizzes</p>
            </div>

            <div class="step-card" style="margin-top:24px;">
                <div class="step-num">1</div>
                <div>
                    <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--peach-green);margin-bottom:4px;">
                        Step 1 — Multimodal Ingestion &amp; Ground Truth Engine
                    </div>
                    <div style="font-size:17px;font-weight:700;color:var(--text-ink);margin-bottom:6px;">
                        Separated Ingestion Pipelines &amp; Layer A Vectorization
                    </div>
                    <div style="font-size:14px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;">
                        Normalizes study materials into an immutable ground-truth repository. Digital text via PyMuPDF; handwritten notes &amp; scans via OpenCV; diagrams via Gemini Vision; lectures via FFmpeg and Faster-Whisper. Embedded in Qdrant as <strong>Layer A (Authoritative Source)</strong> with strict provenance.
                    </div>
                    <div class="meta-chip">POST /upload?auto_start_assessment=true &middot; Layer A Locked</div>
                </div>
            </div>

            <div class="step-card">
                <div class="step-num">2</div>
                <div>
                    <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--blue);margin-bottom:4px;">
                        Step 2 — Diagnostic Assessment &amp; Knowledge Profiling
                    </div>
                    <div style="font-size:17px;font-weight:700;color:var(--text-ink);margin-bottom:6px;">
                        Prerequisite Concept Pairing &amp; Sequential Grounded Generation
                    </div>
                    <div style="font-size:14px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;">
                        Constructs the KnowledgeGraph prerequisite dependency tree. Generates strict JSON multiple-choice questions sequentially from Layer A chunks using negative prompting. Utilizes Fisher-Yates balanced option shuffling with dynamic explanation tracking to detect Prerequisite Gaps.
                    </div>
                    <div class="meta-chip">POST /assessment/start &amp; /assessment/submit &middot; StudentLearningProfile</div>
                </div>
            </div>

            <!-- 🛡 Solving the Three Generative AI Project Killers Table -->
            <div style="background:var(--bg-card);border:1px solid var(--border-card);border-radius:var(--radius-md);padding:24px;margin-top:24px;box-shadow:var(--neo-raised);">
                <div style="font-weight:700;font-size:16px;color:var(--text-ink);margin-bottom:4px;">Solving the Three Generative AI "Project Killers"</div>
                <div style="font-size:13px;color:var(--text-muted);margin-bottom:18px;">Core architectural safeguards engineered into VisualAI</div>
                <div style="overflow-x:auto;">
                    <table style="width:100%;border-collapse:collapse;font-size:13px;text-align:left;">
                        <thead>
                            <tr style="border-bottom:2px solid var(--border-card);color:var(--text-ink);">
                                <th style="padding:10px 12px;font-weight:700;">The Failure Point</th>
                                <th style="padding:10px 12px;font-weight:700;color:var(--peach-green);">The VisualAI Solution</th>
                                <th style="padding:10px 12px;font-weight:700;color:var(--emerald);">Cognitive &amp; System Impact</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="border-bottom:1px solid var(--border-card);">
                                <td style="padding:12px;font-weight:600;color:var(--rose);">1. Hallucination Loops</td>
                                <td style="padding:12px;"><strong>Dual-Layer RAG:</strong> Generated video scripts (Layer B) are never ground truth. Q&amp;A routes strictly back to the textbook (Layer A).</td>
                                <td style="padding:12px;color:var(--emerald);font-weight:600;">The AI cannot teach an invented fact; errors cannot propagate.</td>
                            </tr>
                            <tr style="border-bottom:1px solid var(--border-card);">
                                <td style="padding:12px;font-weight:600;color:var(--rose);">2. Context Window Overflow</td>
                                <td style="padding:12px;"><strong>Sequential Concept Generation:</strong> Loops through atomic Knowledge Graph concepts sequentially instead of chapter dumps.</td>
                                <td style="padding:12px;color:var(--emerald);font-weight:600;">Eliminates "lost in the middle" memory degradation; ensures strict JSON schemas.</td>
                            </tr>
                            <tr>
                                <td style="padding:12px;font-weight:600;color:var(--rose);">3. False Mastery (Guessing)</td>
                                <td style="padding:12px;"><strong>Prerequisite Pairing &amp; The Kill Switch:</strong> Correct attempts require verification. After 3 fails, the Kill Switch stops AI loops and alerts human instructors.</td>
                                <td style="padding:12px;color:var(--emerald);font-weight:600;">Prevents students from clicking blindly; proves verified conceptual comprehension.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- ❓ FAQ Accordion Section -->
            <div style="margin-top:40px;">
                <h3 style="font-family:var(--font-display);font-size:22px;font-weight:700;margin-bottom:16px;">Frequently Asked Questions</h3>

                <div class="faq-item">
                    <button class="faq-btn" onclick="toggleFaq(this)">
                        <span>How does VisualAI prevent AI hallucinations from propagating?</span>
                        <span>▼</span>
                    </button>
                    <div class="faq-content">
                        VisualAI implements a Dual-Layer RAG architecture. Generated video scripts, animations, and transcripts are indexed into Layer B as generated artifacts. When a student asks a question during playback, the system looks up the scene timestamp in Layer B, follows the foreign key back to Layer A (the uploaded textbook chunk), and synthesizes the answer using strictly ground-truth textbook citations.
                    </div>
                </div>

                <div class="faq-item">
                    <button class="faq-btn" onclick="toggleFaq(this)">
                        <span>Why are quiz questions generated in under one minute?</span>
                        <span>▼</span>
                    </button>
                    <div class="faq-content">
                        By passing parsed in-memory content units directly between ingestion and assessment handoff, we eliminate redundant vector lookups. Furthermore, question synthesis runs with a parallel ThreadPoolExecutor against atomic KnowledgeGraph concepts, drastically reducing end-to-end latency from 3–4 minutes to under 60 seconds.
                    </div>
                </div>

                <div class="faq-item">
                    <button class="faq-btn" onclick="toggleFaq(this)">
                        <span>What is the Anti-Loop Kill Switch?</span>
                        <span>▼</span>
                    </button>
                    <div class="faq-content">
                        If a student fails verification re-tests for the same concept 3 times, the system marks the concept as <code>REQUIRES_HUMAN_FALLBACK</code>. Automated AI video loops are suspended to avoid cognitive fatigue, and an alert is dispatched to the Instructor Intervention Portal.
                    </div>
                </div>
            </div>
        </section>

        <!-- 🏛 Footer -->
        <footer class="footer">
            <div>
                <strong style="color:var(--text-ink);">VisualAI</strong> &middot; <span style="color:var(--peach);font-weight:700;">STUDY WITH YOUR VISION</span> &middot; &copy; 2026 VisualAI Technologies Inc.
            </div>
            <div style="display:flex;gap:16px;">
                <a href="/instructor" target="_blank" style="color:var(--text-muted);text-decoration:none;">👩‍🏫 Instructor Portal</a>
                <a href="/docs" target="_blank" style="color:var(--text-muted);text-decoration:none;">API Docs</a>
                <a href="/health" target="_blank" style="color:var(--text-muted);text-decoration:none;">System Health</a>
                <a href="/sources" target="_blank" style="color:var(--text-muted);text-decoration:none;">Sources Index</a>
            </div>
        </footer>
    </main>

    <script>
        let currentSession = null;
        let activeQuestions = [];
        let currentQuestionIdx = 0;
        let userAnswers = {};
        let activeEventSource = null;
        let timelineStartTime = 0;
        let timelineTimerInterval = null;

        const STAGE_LABELS = {
            'uploading': 'Phase 1: Ingestion — Uploading Course Material',
            'extracting': 'Phase 1: Extraction — Text Blocks & Embedded Diagrams',
            'knowledge_graph': 'Phase 1: Ground Truth — Constructing Concept Knowledge Graph',
            'indexing': 'Phase 1: Ground Truth — Vectorizing Layer A (Authoritative Source)',
            'planning_assessment': 'Phase 2: Diagnostic — Prerequisite Graph Concept Pairing',
            'generating_questions': 'Phase 2: Knowledge Profiling — Sequential Grounded Questions',
            'validating_questions': 'Phase 2: Validation — Negative Distractors & Fisher-Yates Shuffling',
            'assessment_ready': 'Phase 2: Diagnostic Ready — Commencing Knowledge Profiling'
        };

        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // 🌓 Theme Toggle
        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('visualai_theme', newTheme);
            document.getElementById('themeIcon').textContent = newTheme === 'dark' ? '☀️' : '🌓';
        }

        // Initialize Theme
        const savedTheme = localStorage.getItem('visualai_theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);

        // 📊 Animated Statistics Counters
        function initCounters() {
            const counters = document.querySelectorAll('.stat-number');
            counters.forEach(counter => {
                const target = parseFloat(counter.getAttribute('data-target') || '0');
                const prefix = counter.getAttribute('data-prefix') || '';
                const suffix = counter.getAttribute('data-suffix') || '';
                const duration = 1200;
                const start = performance.now();

                function update(now) {
                    const elapsed = now - start;
                    const progress = Math.min(elapsed / duration, 1);
                    const currentVal = Math.floor(progress * target);
                    counter.textContent = `${prefix}${currentVal}${suffix}`;
                    if (progress < 1) {
                        requestAnimationFrame(update);
                    } else {
                        counter.textContent = `${prefix}${target}${suffix}`;
                    }
                }
                requestAnimationFrame(update);
            });
        }

        // ❓ FAQ Accordion Toggle
        function toggleFaq(btn) {
            const content = btn.nextElementSibling;
            const isOpen = content.style.display === 'block';
            document.querySelectorAll('.faq-content').forEach(c => c.style.display = 'none');
            document.querySelectorAll('.faq-btn span:last-child').forEach(s => s.textContent = '▼');
            if (!isOpen) {
                content.style.display = 'block';
                btn.querySelector('span:last-child').textContent = '▲';
            }
        }

        function switchTab(tab) {
            document.getElementById('tabUpload').classList.toggle('active', tab === 'upload');
            document.getElementById('tabExisting').classList.toggle('active', tab === 'existing');
            document.getElementById('paneUpload').style.display = tab === 'upload' ? 'block' : 'none';
            document.getElementById('paneExisting').style.display = tab === 'existing' ? 'block' : 'none';
        }

        function handleFileSelected() {
            const file = document.getElementById('fileInput').files[0];
            const info = document.getElementById('selectedFileInfo');
            if (file) {
                info.style.display = 'block';
                info.textContent = `✓ Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
            }
        }

        async function loadSources() {
            try {
                const res = await fetch('/sources');
                const data = await res.json();
                const select = document.getElementById('sourceSelect');
                select.innerHTML = '';
                if (data.sources && data.sources.length > 0) {
                    data.sources.forEach(s => {
                        const opt = document.createElement('option');
                        opt.value = s.source_id;
                        opt.textContent = `${s.filename} (${s.modality || s.source_type || 'material'})`;
                        select.appendChild(opt);
                    });
                } else {
                    select.innerHTML = '<option value="">No ingested materials yet. Upload one above!</option>';
                }
            } catch (err) {
                console.error('Failed to load sources:', err);
            }
        }

        function resetTimeline() {
            if (stopJobTracking) stopJobTracking();
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (timelineTimerInterval) {
                clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
            }
            const card = document.getElementById('timelineCard');
            card.style.display = 'block';
            document.getElementById('timelineProgressBar').style.width = '0%';
            document.getElementById('timelinePercent').textContent = '0%';
            document.getElementById('timelineTimer').textContent = '0.0s';
            document.getElementById('timelineStagesList').innerHTML = '';

            timelineStartTime = Date.now();
            timelineTimerInterval = setInterval(() => {
                const elapsed = ((Date.now() - timelineStartTime) / 1000).toFixed(1);
                document.getElementById('timelineTimer').textContent = `${elapsed}s`;
            }, 100);
        }

        function updateTimelineEvent(ev) {
            const pct = Math.max(0, Math.min(100, ev.progress_percent || 0));
            document.getElementById('timelineProgressBar').style.width = `${pct}%`;
            document.getElementById('timelinePercent').textContent = `${pct}%`;

            const list = document.getElementById('timelineStagesList');
            let stageElem = document.getElementById(`stage-${ev.stage}`);

            if (!stageElem) {
                stageElem = document.createElement('div');
                stageElem.id = `stage-${ev.stage}`;
                list.appendChild(stageElem);
            }

            stageElem.className = `stage-item status-${ev.status}`;
            let iconHtml = '○';
            if (ev.status === 'running') iconHtml = '⏳';
            else if (ev.status === 'completed') iconHtml = '✓';
            else if (ev.status === 'warning') iconHtml = '⚠️';
            else if (ev.status === 'failed') iconHtml = '✕';

            let metaChips = '';
            if (ev.metadata) {
                for (const [k, v] of Object.entries(ev.metadata)) {
                    const valStr = typeof v === 'object' ? JSON.stringify(v) : String(v);
                    metaChips += `<span class="meta-chip">${escapeHtml(k)}: ${escapeHtml(valStr)}</span>`;
                }
            }

            const label = STAGE_LABELS[ev.stage] || ev.stage;
            stageElem.innerHTML = `
                <div class="stage-icon">${iconHtml}</div>
                <div style="flex:1;">
                    <div style="font-weight:700;color:var(--text-ink);">${escapeHtml(label)}</div>
                    <div style="font-size:12px;color:var(--text-muted);">${escapeHtml(ev.message || '')}</div>
                    ${metaChips ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">${metaChips}</div>` : ''}
                </div>
            `;
        }

        let stopJobTracking = null;
        function trackJobSSE(jobId, onComplete, onError) {
            if (stopJobTracking) stopJobTracking();
            let stopped = false;
            let pollTimer = null;
            let failures = 0;
            const stream = new EventSource(`/pipeline/jobs/${jobId}/events`);
            activeEventSource = stream;
            const stop = () => {
                stopped = true;
                stream.close();
                clearTimeout(pollTimer);
                if (activeEventSource === stream) activeEventSource = null;
                if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
            };
            stopJobTracking = stop;
            const finish = async (error, event) => {
                if (stopped) return;
                stop();
                try {
                    if (error) { if (onError) await onError(error); }
                    else if (onComplete) await onComplete(event);
                } catch (err) {
                    if (onError) onError(err);
                }
            };
            const poll = async () => {
                if (stopped) return;
                try {
                    const res = await fetch(`/pipeline/jobs/${jobId}`, {signal: AbortSignal.timeout(15000)});
                    if (!res.ok) throw new Error(`Job status unavailable (${res.status})`);
                    const data = await res.json();
                    if (stopped) return;
                    failures = 0;
                    if (data.status === 'completed') return finish(null, data);
                    if (data.status === 'failed') return finish(new Error(data.error || 'Job failed'));
                } catch (err) {
                    if (stopped) return;
                    if (++failures >= 5) return finish(new Error(`Progress tracking failed: ${err.message}. Check the job before uploading again.`));
                }
                if (!stopped) pollTimer = setTimeout(poll, 2000);
            };
            stream.onmessage = event => {
                if (stopped || !event.data) return;
                try {
                    const ev = JSON.parse(event.data);
                    updateTimelineEvent(ev);
                    if (ev.terminal && ev.status === 'completed') finish(null, ev);
                    else if (ev.terminal && ev.status === 'failed') finish(new Error(ev.message || 'Job failed'));
                } catch (err) {
                    finish(err);
                }
            };
            stream.onerror = () => {
                stream.close();
                clearTimeout(pollTimer);
                if (!stopped) pollTimer = setTimeout(poll, 0);
            };
            // Poll periodically even if the stream silently stalls.
            pollTimer = setTimeout(poll, 2000);
        }

        async function runUpload() {
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files || fileInput.files.length === 0) {
                alert('Please select a course file to upload.');
                return;
            }

            const studentId = document.getElementById('studentId').value.trim() || 'student_1';
            const maxQ = parseInt(document.getElementById('maxQuestions').value, 10) || 5;

            const btn = document.getElementById('btnUpload');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳ Uploading &amp; Ingesting...</span>';
            resetTimeline();

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            try {
                const res = await fetch(`/pipeline/upload-and-assess?student_id=${encodeURIComponent(studentId)}&max_questions=${maxQ}`, {
                    method: 'POST',
                    body: formData
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                if (data.job_id) {
                    trackJobSSE(data.job_id, async () => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>⚡ Ingest Material &amp; Start Diagnostic Assessment</span>';
                        const resultRes = await fetch(`/pipeline/jobs/${data.job_id}`);
                        if (!resultRes.ok) throw new Error("Cannot retrieve completed assessment");
                        const resultData = await resultRes.json();
                        if (!resultData.result?.assessment?.questions?.length) throw new Error("Completed job has no quiz");
                        startQuiz(resultData.result.assessment);
                        loadSources();
                    }, (err) => {
                        btn.disabled = false;
                        btn.innerHTML = '<span>⚡ Ingest Material &amp; Start Diagnostic Assessment</span>';
                        alert(`Pipeline Error: ${err.message}`);
                    });
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡ Ingest Material &amp; Start Diagnostic Assessment</span>';
                if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
                alert(`Upload failed: ${err.message}`);
            }
        }

        async function runExistingAssess() {
            const select = document.getElementById('sourceSelect');
            const sourceId = select.value;
            if (!sourceId) {
                alert('Please select an ingested course material.');
                return;
            }

            const studentId = document.getElementById('studentIdExisting').value.trim() || 'student_1';
            const maxQ = parseInt(document.getElementById('maxQuestionsExisting').value, 10) || 5;

            const btn = document.getElementById('btnAssessExisting');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳ Generating Diagnostic Questions...</span>';
            resetTimeline();

            try {
                const res = await fetch('/assessment/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_id: sourceId,
                        student_id: studentId,
                        max_questions: maxQ
                    })
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                btn.disabled = false;
                btn.innerHTML = '<span>⚡ Generate Diagnostic Quiz from Material</span>';
                startQuiz(data);
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡ Generate Diagnostic Quiz from Material</span>';
                if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
                alert(`Assessment generation failed: ${err.message}`);
            }
        }

        function startQuiz(session) {
            if (timelineTimerInterval) clearInterval(timelineTimerInterval);
            timelineTimerInterval = null;
            document.getElementById('btnNextQuestion').disabled = false;
            currentSession = session;
            activeQuestions = session.questions || [];
            currentQuestionIdx = 0;
            userAnswers = {};

            document.getElementById('quizSection').style.display = 'block';
            document.getElementById('resultsBox').style.display = 'none';
            document.getElementById('quizReviewSection').style.display = 'none';

            renderCurrentQuestion();
        }

        function renderCurrentQuestion() {
            if (currentQuestionIdx >= activeQuestions.length) {
                submitQuiz();
                return;
            }

            const q = activeQuestions[currentQuestionIdx];
            document.getElementById('lblConceptBadge').textContent = q.concept_name || 'DIAGNOSTIC';
            document.getElementById('lblQuestionCounter').textContent = `Question ${currentQuestionIdx + 1} of ${activeQuestions.length}`;
            document.getElementById('lblQuestionStem').textContent = q.stem;

            const container = document.getElementById('optionsContainer');
            container.innerHTML = '';

            (q.options || []).forEach((opt, idx) => {
                const optId = `opt_${currentQuestionIdx}_${idx}`;
                const isSelected = userAnswers[q.question_id] === idx;

                const label = document.createElement('label');
                label.className = 'option-item';
                label.htmlFor = optId;

                const input = document.createElement('input');
                input.type = 'radio';
                input.name = 'quiz_choice';
                input.id = optId;
                input.value = idx;
                if (isSelected) input.checked = true;
                input.addEventListener('change', () => selectOption(idx));

                const span = document.createElement('span');
                span.style.fontWeight = '600';
                const strong = document.createElement('strong');
                strong.textContent = `${String.fromCharCode(65 + idx)}. `;
                span.appendChild(strong);
                span.appendChild(document.createTextNode(opt.text || ''));

                label.appendChild(input);
                label.appendChild(span);
                container.appendChild(label);
            });

            const nextBtn = document.getElementById('btnNextQuestion');
            nextBtn.innerHTML = currentQuestionIdx === activeQuestions.length - 1
                ? '<span>Submit Diagnostic Assessment ✓</span>'
                : '<span>Next Question ➔</span>';
        }

        function selectOption(idx) {
            const q = activeQuestions[currentQuestionIdx];
            userAnswers[q.question_id] = idx;
        }

        function submitCurrentAnswer() {
            const q = activeQuestions[currentQuestionIdx];
            if (userAnswers[q.question_id] === undefined) {
                alert('Please select an option before proceeding.');
                return;
            }
            currentQuestionIdx++;
            renderCurrentQuestion();
        }

        async function submitQuiz() {
            const btn = document.getElementById('btnNextQuestion');
            btn.disabled = true;
            btn.innerHTML = '<span>Grading Diagnostic Assessment...</span>';

            const payload = {
                session_id: currentSession.session_id,
                answers: Object.entries(userAnswers).map(([qid, idx]) => ({
                    question_id: qid,
                    selected_index: idx
                }))
            };

            try {
                const res = await fetch('/assessment/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                document.getElementById('quizSection').style.display = 'none';
                displayResults(data);
            } catch (err) {
                alert(`Quiz grading error: ${err.message}`);
                btn.disabled = false;
            }
        }

        function displayResults(data) {
            const resultsBox = document.getElementById('resultsBox');
            resultsBox.style.display = 'block';

            const scorePct = data.percentage || 0;
            const scoreEl = document.getElementById('lblScore');
            scoreEl.textContent = `${scorePct.toFixed(1)}%`;
            scoreEl.style.color = scorePct >= 70 ? 'var(--emerald)' : (scorePct >= 50 ? 'var(--amber)' : 'var(--rose)');

            document.getElementById('lblFraction').textContent = `${data.score} / ${data.total} correct`;

            const profileSummary = data.profile_summary || {};
            if (profileSummary.overall_score !== undefined) {
                document.getElementById('lblProfileScore').textContent = `${profileSummary.overall_score.toFixed(1)}%`;
            }

            const statusEl = document.getElementById('lblGradeStatus');
            statusEl.innerHTML = scorePct >= 70
                ? '<span class="badge badge-green">ASSESSMENT PASSED</span>'
                : '<span class="badge badge-amber">NEEDS REVIEW</span>';

            const masteriesEl = document.getElementById('lblMasteries');
            masteriesEl.innerHTML = '';
            (profileSummary.strong_concepts || []).forEach(c => {
                const s = document.createElement('span');
                s.className = 'badge badge-green';
                s.textContent = `✔ ${c} (Strong)`;
                masteriesEl.appendChild(s);
            });
            (profileSummary.weak_concepts || []).forEach(c => {
                const s = document.createElement('span');
                s.className = 'badge badge-amber';
                s.textContent = `⚠ ${c} (Needs Review)`;
                masteriesEl.appendChild(s);
            });

            const prereqsBox = document.getElementById('boxPrereqs');
            if (data.prerequisite_gaps && data.prerequisite_gaps.length > 0) {
                prereqsBox.style.display = 'block';
                const prereqEl = document.getElementById('lblPrereqs');
                prereqEl.innerHTML = '';
                data.prerequisite_gaps.forEach(g => {
                    const row = document.createElement('div');
                    row.textContent = `• ${g}`;
                    prereqEl.appendChild(row);
                });
            } else {
                prereqsBox.style.display = 'none';
            }

            // Question-by-Question Review
            const reviewSection = document.getElementById('quizReviewSection');
            const reviewContainer = document.getElementById('quizReviewContainer');
            reviewContainer.innerHTML = '';

            if (data.results && data.results.length > 0) {
                reviewSection.style.display = 'block';
                data.results.forEach((qr, idx) => {
                    const originalQ = activeQuestions.find(q => q.question_id === qr.question_id) || {};
                    const isCorrect = qr.correct;

                    const reviewCard = document.createElement('div');
                    reviewCard.className = `review-card ${isCorrect ? 'review-correct' : 'review-incorrect'}`;

                    const headerRow = document.createElement('div');
                    headerRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;';

                    const qTitle = document.createElement('span');
                    qTitle.style.cssText = 'font-weight:700;font-size:14px;';
                    qTitle.textContent = `Question ${idx + 1}: ${originalQ.concept_name || 'Concept'}`;

                    const badge = document.createElement('span');
                    badge.className = `badge ${isCorrect ? 'badge-green' : 'badge-rose'}`;
                    badge.textContent = isCorrect ? 'CORRECT' : 'INCORRECT';

                    headerRow.appendChild(qTitle);
                    headerRow.appendChild(badge);

                    const stemDiv = document.createElement('div');
                    stemDiv.style.cssText = 'font-size:14px;color:var(--text-ink);margin-bottom:12px;font-weight:600;';
                    stemDiv.textContent = originalQ.stem;

                    const optsContainer = document.createElement('div');
                    optsContainer.style.marginBottom = '12px';

                    (originalQ.options || []).forEach((opt, optIdx) => {
                        const isUserChoice = optIdx === qr.selected_index;
                        const isCorrectAnswer = optIdx === qr.correct_index;

                        const optDiv = document.createElement('div');
                        let optStyle = 'padding:8px 12px;border-radius:6px;margin-bottom:6px;background:var(--bg-page);font-size:13px;display:flex;justify-content:space-between;align-items:center;';

                        let badgeText = '';
                        let badgeClass = '';

                        if (isCorrectAnswer) {
                            optStyle += 'border:1px solid var(--emerald-border);background:var(--emerald-soft);color:#065f46;font-weight:600;';
                            badgeText = '✓ Authoritative Correct';
                            badgeClass = 'badge badge-green';
                        }
                        if (isUserChoice && !isCorrectAnswer) {
                            optStyle += 'border:1px solid var(--rose-border);background:var(--rose-soft);color:#991b1b;font-weight:600;';
                            badgeText = '✕ Your Choice (Incorrect)';
                            badgeClass = 'badge badge-rose';
                        } else if (isUserChoice && isCorrectAnswer) {
                            badgeText = '✓ Your Choice (Correct)';
                            badgeClass = 'badge badge-green';
                        }

                        optDiv.style.cssText = optStyle;

                        const textSpan = document.createElement('span');
                        const prefix = document.createElement('strong');
                        prefix.textContent = `${String.fromCharCode(65 + optIdx)}. `;
                        textSpan.appendChild(prefix);
                        textSpan.appendChild(document.createTextNode(opt.text || ''));
                        optDiv.appendChild(textSpan);

                        if (badgeText) {
                            const b = document.createElement('span');
                            b.className = badgeClass;
                            b.textContent = badgeText;
                            optDiv.appendChild(b);
                        }

                        optsContainer.appendChild(optDiv);
                    });

                    reviewCard.appendChild(headerRow);
                    reviewCard.appendChild(stemDiv);
                    reviewCard.appendChild(optsContainer);

                    if (qr.misconception) {
                        const miscDiv = document.createElement('div');
                        miscDiv.style.cssText = 'font-size:12px;color:var(--rose);margin-bottom:6px;';
                        const mStrong = document.createElement('strong');
                        mStrong.textContent = 'Diagnosed Misconception: ';
                        miscDiv.appendChild(mStrong);
                        miscDiv.appendChild(document.createTextNode(qr.misconception));
                        reviewCard.appendChild(miscDiv);
                    }

                    if (qr.explanation) {
                        const expDiv = document.createElement('div');
                        expDiv.style.cssText = 'font-size:12px;color:var(--text-muted);background:var(--bg-page);padding:8px 12px;border-radius:6px;';
                        const expStrong = document.createElement('strong');
                        expStrong.textContent = 'Explanation: ';
                        expDiv.appendChild(expStrong);
                        expDiv.appendChild(document.createTextNode(qr.explanation));
                        reviewCard.appendChild(expDiv);
                    }

                    reviewContainer.appendChild(reviewCard);
                });
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            loadSources();
            initCounters();
        });
    </script>
</body>
</html>
"""


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
@router.api_route("/dashboard", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard():
    """VisualAI dashboard — Interactive test runner and complete pipeline documentation."""
    return HTMLResponse(content=DASHBOARD_HTML)
