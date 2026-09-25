"""VisualAI Dashboard - Interactive Assessment Console & Pipeline Documentation.

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
    <title>VisualAI - Interactive Assessment Console | STUDY WITH YOUR VISION</title>
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
            --bg-surface: #f8f9fa;
            --bg-subtle: #e9edf5;

            --text-ink: #333333;
            --text-body: #4b5563;
            --text-muted: #6b7280;

            /*  Peach Green & Botanical Color Palette */
            --peach-green: #2e7d5e;
            --peach-green-hover: #24664c;
            --peach-green-soft: #edf6f2;
            --peach-green-border: #9ecab4;
            --peach-green-shadow: rgba(46, 125, 94, 0.32);

            /*  Warm Peach Accents */
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

            /*  Tactile Neomorphism Shadows (Light Mode) */
            --neo-raised: none;
            --neo-raised-sm: none;
            --neo-raised-lg: none;
            --neo-inset: none;
            --neo-btn: none;
            --neo-btn-active: none;
            --border-card: rgba(226, 232, 240, 0.6);

            --radius-sm: 2px;
            --radius-md: 4px;
            --radius-lg: 4px;

            /* Elegant Botanical Floral Background Pattern (Light Mode) */
            --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%232e7d5e%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.11%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%23df7456%27%20fill-opacity%3D%270.25%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M72%2C80%20C58%2C76%2048%2C84%2042%2C80%20C48%2C76%2058%2C84%2072%2C80%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M88%2C80%20C102%2C84%20112%2C76%20118%2C80%20C112%2C84%20102%2C76%2088%2C80%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M74%2C74%20C62%2C64%2056%2C70%2052%2C66%20C60%2C60%2068%2C66%2074%2C74%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M86%2C86%20C98%2C96%20104%2C90%20108%2C94%20C100%2C100%2092%2C94%2086%2C86%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M74%2C86%20C64%2C98%2070%2C104%2066%2C108%20C60%2C100%2066%2C92%2074%2C86%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M86%2C74%20C96%2C62%2090%2C56%2094%2C52%20C100%2C60%2094%2C68%2086%2C74%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.05%27/%3E%3Cpath%20d%3D%27M80%2C42%20Q80%2C20%2050%2C20%20Q20%2C20%2020%2C50%20Q20%2C80%2042%2C80%27/%3E%3Cpath%20d%3D%27M80%2C118%20Q80%2C140%20110%2C140%20Q140%2C140%20140%2C110%20Q140%2C80%20118%2C80%27/%3E%3Cpath%20d%3D%27M34%2C26%20C30%2C16%2042%2C14%2046%2C24%20C40%2C28%2036%2C28%2034%2C26%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.08%27/%3E%3Cpath%20d%3D%27M126%2C134%20C130%2C144%20118%2C146%20114%2C136%20C120%2C132%20124%2C132%20126%2C134%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.08%27/%3E%3Cpath%20d%3D%27M14%2C64%20C4%2C60%206%2C48%2016%2C52%20C18%2C58%2016%2C62%2014%2C64%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.08%27/%3E%3Cpath%20d%3D%27M146%2C96%20C156%2C100%20154%2C112%20144%2C108%20C142%2C102%20144%2C98%20146%2C96%20Z%27%20fill%3D%27%232e7d5e%27%20fill-opacity%3D%270.08%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
        }

        [data-theme="dark"] {
            --bg-page: #18191e;
            --bg-card: #22242c;
            --bg-surface: #262832;
            --bg-subtle: #1f2026;

            --text-ink: #f3f4f6;
            --text-body: #d1d5db;
            --text-muted: #9ca3af;

            /*  Peach Green & Botanical Color Palette (Dark Mode) */
            --peach-green: #4ecb94;
            --peach-green-hover: #3db882;
            --peach-green-soft: rgba(78, 203, 148, 0.16);
            --peach-green-border: rgba(78, 203, 148, 0.38);
            --peach-green-shadow: rgba(78, 203, 148, 0.28);

            /*  Warm Peach Accents (Dark Mode) */
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

            /*  Tactile Neomorphism Shadows (Dark Mode) */
            --neo-raised: none;
            --neo-raised-sm: none;
            --neo-raised-lg: none;
            --neo-inset: none;
            --neo-btn: none;
            --neo-btn-active: none;
            --border-card: rgba(255, 255, 255, 0.06);

            /* Elegant Botanical Floral Background Pattern (Dark Mode) */
            --floral-bg: url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27160%27%20height%3D%27160%27%20viewBox%3D%270%200%20160%20160%27%3E%3Cg%20fill%3D%27none%27%20stroke%3D%27%234ecb94%27%20stroke-width%3D%271.2%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%20opacity%3D%270.13%27%3E%3Ccircle%20cx%3D%2780%27%20cy%3D%2780%27%20r%3D%275%27%20fill%3D%27%23f09a80%27%20fill-opacity%3D%270.28%27%20stroke%3D%27none%27/%3E%3Cpath%20d%3D%27M80%2C72%20C76%2C58%2084%2C48%2080%2C42%20C76%2C48%2084%2C58%2080%2C72%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M80%2C88%20C84%2C102%2076%2C112%2080%2C118%20C84%2C112%2076%2C102%2080%2C88%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M72%2C80%20C58%2C76%2048%2C84%2042%2C80%20C48%2C76%2058%2C84%2072%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M88%2C80%20C102%2C84%20112%2C76%20118%2C80%20C112%2C84%20102%2C76%2088%2C80%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M74%2C74%20C62%2C64%2056%2C70%2052%2C66%20C60%2C60%2068%2C66%2074%2C74%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M86%2C86%20C98%2C96%20104%2C90%20108%2C94%20C100%2C100%2092%2C94%2086%2C86%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M74%2C86%20C64%2C98%2070%2C104%2066%2C108%20C60%2C100%2066%2C92%2074%2C86%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M86%2C74%20C96%2C62%2090%2C56%2094%2C52%20C100%2C60%2094%2C68%2086%2C74%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.06%27/%3E%3Cpath%20d%3D%27M80%2C42%20Q80%2C20%2050%2C20%20Q20%2C20%2020%2C50%20Q20%2C80%2042%2C80%27/%3E%3Cpath%20d%3D%27M80%2C118%20Q80%2C140%20110%2C140%20Q140%2C140%20140%2C110%20Q140%2C80%20118%2C80%27/%3E%3Cpath%20d%3D%27M34%2C26%20C30%2C16%2042%2C14%2046%2C24%20C40%2C28%2036%2C28%2034%2C26%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.10%27/%3E%3Cpath%20d%3D%27M126%2C134%20C130%2C144%20118%2C146%20114%2C136%20C120%2C132%20124%2C132%20126%2C134%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.10%27/%3E%3Cpath%20d%3D%27M14%2C64%20C4%2C60%206%2C48%2016%2C52%20C18%2C58%2016%2C62%2014%2C64%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.10%27/%3E%3Cpath%20d%3D%27M146%2C96%20C156%2C100%20154%2C112%20144%2C108%20C142%2C102%20144%2C98%20146%2C96%20Z%27%20fill%3D%27%234ecb94%27%20fill-opacity%3D%270.10%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%270%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%270%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3Ccircle%20cx%3D%27160%27%20cy%3D%27160%27%20r%3D%2710%27%20stroke-dasharray%3D%273%2C3%27/%3E%3C/g%3E%3C/svg%3E");
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

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
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        /*  Fixed Top Navigation Bar */
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 50;
            background: var(--bg-card);
            -webkit-border-bottom: 1px solid var(--border-card);
            padding: 14px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.3s ease;
        }

        [data-theme="dark"] .header {
            background: var(--bg-card);
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-monogram {
            width: 42px;
            height: 42px;
            border-radius: var(--radius-sm);
            background: var(--bg-card);
            
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
            
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            text-decoration: none;
        }

        .neo-btn:hover {
            color: var(--peach-green);
        }

        .neo-btn:active {
            transform: translateY(0);
            
        }

        .neo-btn-gold, .neo-btn-peach-green {
            background: var(--peach-green);
            color: #ffffff;
            border: none;
            
        }

        .neo-btn-gold:hover, .neo-btn-peach-green:hover {
            color: #ffffff;
            filter: brightness(1.08);
            
        }

        .neo-btn-peach {
            background: var(--peach);
            color: #ffffff;
            border: none;
            
        }

        .neo-btn-peach:hover {
            color: #ffffff;
            filter: brightness(1.08);
            }

        .neo-icon-btn {
            width: 40px;
            height: 40px;
            border-radius: var(--radius-sm);
            background: var(--bg-card);
            color: var(--text-ink);
            border: 1px solid var(--border-card);
            
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
            
        }

        /* Model Switcher & Fallback UI */
        .model-switch-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 6px 12px;
            font-size: 12px;
            font-family: var(--font-sans);
            color: var(--text-ink);
        }

        .model-pill-label {
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
        }

        .header-model-select {
            background: transparent;
            border: none;
            color: var(--peach-green);
            font-weight: 700;
            font-size: 12px;
            font-family: var(--font-sans);
            cursor: pointer;
            outline: none;
        }

        .header-fallback-badge {
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 2px;
            background: var(--peach-green-soft);
            color: var(--peach-green);
            border: 1px solid var(--peach-green-border);
        }

        .model-card-box {
            background: var(--bg-surface);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 14px 16px;
            margin-bottom: 16px;
        }

        .model-card-header {
            margin-bottom: 10px;
        }

        .model-card-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            font-weight: 700;
            color: var(--text-ink);
        }

        .model-card-desc {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 3px;
        }

        .model-card-controls {
            display: flex;
            gap: 14px;
            align-items: flex-end;
        }

        .chain-display-box {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 8px 12px;
            font-size: 12px;
            font-weight: 600;
            color: var(--peach-green);
            display: flex;
            align-items: center;
            gap: 6px;
            min-height: 38px;
            box-sizing: border-box;
        }

        /*  Main Page Container */
        .container {
            max-width: 1140px;
            margin: 0 auto;
            padding: 104px 24px 60px;
        }

        /*  Hero Section & Animated Stat Counters */
        .hero {
            text-align: center;
            padding: 30px 10px 40px;
        }

        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: var(--radius-sm);
            background: var(--bg-card);
            
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
            
            text-align: center;
            transition: transform 0.2s ease;
        }

        .stat-card:hover {
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

        /*  Neomorphic Main Console Card */
        .console-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 36px;
            
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

        /*  Neomorphic Tab Switcher */
        .tab-switcher {
            display: inline-flex;
            background: var(--bg-card);
            
            border-radius: var(--radius-sm);
            padding: 4px;
            gap: 4px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            padding: 8px 18px;
            border-radius: var(--radius-sm);
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
            
        }

        [data-theme="dark"] .tab-btn.active {
            background: #2b2e38;
            color: var(--peach-green);
        }

        /*  Forms & Inset Inputs */
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

        /*  Live Pipeline Telemetry Timeline Card */
        .timeline-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            padding: 24px;
            margin: 28px 0;
            
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
            width: 8px;
            height: 8px;
            border-radius: var(--radius-sm);
            background: var(--peach-green);
            animation: pulse-ring 1.8s infinite;
        }
        @keyframes pulse-ring {
            0%, 100% { opacity: 0.4; }
            50% { opacity: 1.0; }
        }

        .progress-bar-bg {
            background: var(--bg-card);
            
            border-radius: var(--radius-sm);
            height: 10px;
            overflow: hidden;
            margin-bottom: 20px;
        }

        .progress-bar-fill {
            background: var(--peach-green);
            height: 100%;
            border-radius: var(--radius-sm);
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

        /*  Diagnostic Assessment Quiz Section */
        .quiz-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-md);
            padding: 28px;
            
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
            
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .option-item:hover {
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
            border-radius: var(--radius-sm);
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

        /*  Transparent Question Review Cards */
        .review-card {
            border-radius: var(--radius-sm);
            padding: 20px;
            margin-bottom: 16px;
            background: var(--bg-card);
            
            border: 1px solid var(--border-card);
        }

        .review-correct { border: 1px solid var(--emerald); }
        .review-incorrect { border: 1px solid var(--rose); }

        /*  Video Target Matrix Cards */
        .target-card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 20px;
            
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 14px;
        }

        /*  Video Modal Overlay */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.75);
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
            
            padding: 28px;
        }

        .meta-chip {
            background: var(--bg-card);
            
            border: 1px solid var(--border-card);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 11px;
            color: var(--text-body);
        }

        /*  Flow Architecture Documentation */
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
            
        }

        .step-num {
            flex-shrink: 0;
            width: 44px;
            height: 44px;
            border-radius: var(--radius-sm);
            background: var(--bg-card);
            
            border: 1px solid var(--peach-green-border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: var(--font-display);
            font-size: 20px;
            font-weight: 700;
            color: var(--peach-green);
        }

        /*  FAQ Accordion */
        .faq-item {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            margin-bottom: 12px;
            
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

        /*  Multi-Column Luxury Footer */
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

        /*  Remedial Video & Dual-Layer RAG Styles */
        .video-target-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-sm);
            padding: 14px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            
            transition: all 0.2s ease;
        }
        .video-target-card:hover {
            
        }
        .video-rag-grid {
            display: grid;
            grid-template-columns: 1.1fr 0.9fr;
            gap: 20px;
            align-items: start;
        }
        @media (max-width: 900px) {
            .video-rag-grid {
                grid-template-columns: 1fr !important;
            }
            .video-target-card {
                flex-direction: column;
                align-items: flex-start;
            }
        }
        .pulse-dot {
            animation: pulseAnim 1.5s infinite;
        }
        @keyframes pulseAnim {
            0% { opacity: 0.3; transform: scale(0.8); }
            50% { opacity: 1; transform: scale(1.1); }
            100% { opacity: 0.3; transform: scale(0.8); }
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; transform: translateY(0); }
        }
    
        /* Skeleton loaders for state transitions */
        .skeleton {
            background: #e5e7eb;
            border-radius: var(--radius-sm);
            animation: skeleton-pulse 1.5s ease-in-out infinite;
        }
        [data-theme="dark"] .skeleton {
            background: #2d3748;
        }
        @keyframes skeleton-pulse {
            0%, 100% { opacity: 0.6; }
            50% { opacity: 0.3; }
        }

        /* Antigravity Floral Interactive Background Canvas */
        #antigravityFloralCanvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none;
            z-index: 0;
        }

        .container {
            position: relative;
            z-index: 1;
        }
    
    </style>
</head>
<body>

    <!-- Antigravity Floral Interactive Background Canvas -->
    <canvas id="antigravityFloralCanvas"></canvas>

    <!--  Fixed Top Navigation Bar -->
    <header class="header">
        <div class="header-brand">
            <div class="brand-monogram">V</div>
            <div>
                <span class="brand-title">Visual<span>AI</span></span>
                <span class="brand-tagline">STUDY WITH YOUR VISION</span>
            </div>
        </div>
        <div class="nav-actions">
            <div class="model-switch-pill" title="Current Active LLM &amp; Automatic Fallback Routing">
                <span class="model-pill-label">Model:</span>
                <select id="headerModelSelect" class="header-model-select" onchange="switchModel(this.value)">
                    <option value="llama3.2:3b">llama3.2:3b (Ollama)</option>
                    <option value="mock">mock (Deterministic)</option>
                </select>
                <span id="headerFallbackBadge" class="header-fallback-badge" title="Automatic Fallback Routing Active">Fallback: ON</span>
            </div>
            <button id="themeToggleBtn" class="neo-icon-btn" onclick="toggleTheme()" title="Toggle Theme (Light / Dark)">
                <span id="themeIcon">Dark</span>
            </button>
            <a href="/" class="neo-btn">
                <span>Landing Page</span>
            </a>
            <a href="/instructor" target="_blank" class="neo-btn">
                <span> Instructor Portal</span>
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

        <!--  Hero Overview -->
        <section class="hero">
            <div class="hero-badge">Adaptive Pedagogical Pipeline</div>
            <h1 class="hero-title">Study With Your Vision</h1>
            <p class="hero-subtitle">
                Transform static study materials into programmatic, personalized visual lessons grounded strictly in authoritative textbooks without hallucination loops.
            </p>

            <!--  Animated Statistics Counters -->
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

        <!--  Neomorphic Main Console Card -->
        <section class="console-card">
            <div class="console-header">
                <div class="console-title-area">
                    <h2>Interactive Assessment Control</h2>
                    <p>Execute end-to-end multimodal ingestion, diagnostic profiling, and video synthesis</p>
                </div>
                <div class="tab-switcher">
                    <button class="tab-btn active" id="tabUpload" onclick="switchTab('upload')"> Ingest New Material</button>
                    <button class="tab-btn" id="tabExisting" onclick="switchTab('existing')"> Existing Course</button>
                </div>
            </div>

            <!-- Pane 1: Upload Material -->
            <div id="paneUpload">
                <div class="dropzone-area" onclick="document.getElementById('fileInput').click()">
                    <div class="dropzone-icon"></div>
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

                <div class="model-card-box">
                    <div class="model-card-header">
                        <div class="model-card-title">
                            <span>Active AI Model &amp; Automatic Fallback</span>
                            <span id="modelChainBadge" class="header-fallback-badge">Fallback Active</span>
                        </div>
                        <div class="model-card-desc">
                            If the active model cannot provide the info, times out, or lacks vision support, the next model in the fallback chain will automatically generate the info.
                        </div>
                    </div>
                    <div class="model-card-controls">
                        <div class="form-group" style="flex:1;margin-bottom:0;">
                            <label class="form-label" for="formModelSelect">Select Active Model</label>
                            <select id="formModelSelect" class="neo-select" onchange="switchModel(this.value)">
                                <option value="llama3.2:3b">llama3.2:3b (Ollama Local)</option>
                                <option value="mock">mock (Deterministic Fallback)</option>
                            </select>
                        </div>
                        <div class="form-group" style="flex:1;margin-bottom:0;">
                            <label class="form-label">Fallback Routing Order</label>
                            <div id="fallbackChainDisplay" class="chain-display-box">
                                llama3.2:3b &rarr; mock
                            </div>
                        </div>
                    </div>
                </div>

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
                    <span> Ingest Material &amp; Start Diagnostic Assessment</span>
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
                    <span> Generate Diagnostic Quiz from Material</span>
                </button>
            </div>

            <!--  Live Pipeline Telemetry Timeline Card -->
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

            <!--  Diagnostic Assessment Quiz Section -->
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
                        <span>Next Question</span>
                    </button>
                </div>
            </div>

            <!--  Detailed Question Review Section -->
            <div id="quizReviewSection" style="display:none;margin-top:28px;">
                <div style="font-family:var(--font-display);font-size:22px;font-weight:700;margin-bottom:6px;">Diagnostic Assessment Review</div>
                <p style="font-size:13px;color:var(--text-muted);margin-bottom:18px;">Inspect your submissions against authoritative textbook ground truth.</p>
                <div id="quizReviewContainer"></div>
            </div>

            <!--  Diagnostic Score & Profile Summary -->
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
                    <div style="font-weight:700;font-size:13px;margin-bottom:4px;"> Prerequisite Gaps Identified</div>
                    <div id="lblPrereqs" style="font-size:13px;"></div>
                </div>
            </div>

            <!--  Step 3 & 4: Remedial Video Generation & Dual-Layer Video RAG -->
            <div id="videoSection" class="quiz-card" style="display:none;margin-top:28px;">
                <div class="quiz-header" style="border-bottom:1px solid var(--border-card);padding-bottom:12px;margin-bottom:16px;">
                    <div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:20px;"></span>
                            <span style="font-weight:700;font-size:18px;color:var(--text-ink);">Personalized Remedial Video Lessons</span>
                        </div>
                        <p style="font-size:13px;color:var(--text-muted);margin:4px 0 0 0;">
                            Programmatic Manim animations + natural voiceover tailored to your diagnosed knowledge gaps
                        </p>
                    </div>
                    <span class="badge badge-peach-green">STEP 3 VIDEO ENGINE</span>
                </div>

                <!-- Video Generation Cards for Diagnosed Gaps -->
                <div id="videoTargetsContainer">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <span style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--text-muted);">
                            Diagnosed Gaps Eligible for Video Generation
                        </span>
                        <span style="font-size:12px;color:var(--peach-green);font-weight:600;" id="lblTargetsCount"></span>
                    </div>
                    <div id="videoTargetsList" style="display:flex;flex-direction:column;gap:10px;margin-bottom:18px;"></div>
                </div>

                <!-- Live Generation Status / Progress -->
                <div id="videoGenStatusBox" style="display:none;background:var(--bg-surface);border:1px solid var(--peach-green-border);border-radius:var(--radius-sm);padding:16px;margin-bottom:18px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <span style="font-weight:700;font-size:14px;color:var(--peach-green);" id="lblVideoGenStage">
                             Initializing Video Engine...
                        </span>
                        <span class="badge badge-peach-green" id="lblVideoGenProgress">0%</span>
                    </div>
                    <div class="progress-bar-track" style="height:8px;background:var(--bg-subtle);border-radius:4px;overflow:hidden;">
                        <div id="videoGenProgressBar" class="progress-bar-fill" style="width:0%;height:100%;background: var(--peach-green);transition:width 0.4s ease;"></div>
                    </div>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:8px;" id="lblVideoGenDetails">
                        Composing Manim scene scripts, rendering animations, and synthesizing voiceover...
                    </div>
                </div>

                <!-- Active Video Player & Dual-Layer Video RAG Container -->
                <div id="activeVideoPlayerBox" style="display:none;margin-top:24px;padding-top:20px;border-top:1px solid var(--border-card);">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;">
                        <div>
                            <span style="font-weight:700;font-size:16px;color:var(--text-ink);" id="activeVideoTitle">Remedial Lesson</span>
                            <span class="badge badge-green" style="margin-left:6px;">READY</span>
                        </div>
                        <div style="display:flex;gap:8px;">
                            <a id="btnDownloadVideo" href="#" target="_blank" class="neo-btn neo-btn-peach-green" style="padding:6px 14px;font-size:12px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;">
                                <span> Download MP4</span>
                            </a>
                        </div>
                    </div>

                    <div class="video-rag-grid">
                        <!-- Left: Video Player -->
                        <div>
                            <div style="background:#000;border-radius:var(--radius-sm);overflow:hidden;">
                                <video id="remedialVideoPlayer" controls style="width:100%;display:block;aspect-ratio:16/9;outline:none;" preload="metadata">
                                    <source id="videoSource" src="" type="video/mp4">
                                    Your browser does not support HTML5 video streaming.
                                </video>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--text-muted);">
                                <span>Manim + Edge-TTS · 720p · 30 FPS</span>
                                <span id="lblPlaybackTime">Time: 0:00</span>
                            </div>
                        </div>

                        <!-- Right: Dual-Layer Video RAG Assistant (Step 4) -->
                        <div style="background:var(--bg-surface);border:1px solid var(--border-card);border-radius:var(--radius-sm);padding:16px;display:flex;flex-direction:column;gap:12px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div style="display:flex;align-items:center;gap:6px;">
                                    <span style="font-size:18px;"></span>
                                    <strong style="font-size:14px;color:var(--text-ink);">Dual-Layer Video RAG Assistant</strong>
                                </div>
                                <span class="badge badge-blue" style="font-size:10px;">STEP 4 GROUNDED</span>
                            </div>
                            <div style="font-size:12px;color:var(--text-muted);line-height:1.4;">
                                Ask any question. Answers are verified against <strong>Layer A</strong> (textbook ground truth) and synchronized to <strong>Layer B</strong> (current video scene).
                            </div>

                            <div style="display:flex;gap:6px;">
                                <input type="text" id="qaQuestionInput" placeholder="e.g. Can you explain this concept in simpler terms?" class="neo-input" style="flex:1;font-size:13px;padding:8px 12px;" onkeydown="if(event.key==='Enter')askVideoRAG()">
                                <button class="neo-btn neo-btn-peach-green" id="btnAskRAG" onclick="askVideoRAG()" style="padding:8px 14px;font-size:12px;white-space:nowrap;">
                                    <span>Ask Question</span>
                                </button>
                            </div>

                            <div id="ragLoading" style="display:none;font-size:12px;color:var(--peach-green);font-weight:600;padding:4px 0;">
                                <span class="pulse-dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--peach-green);margin-right:6px;"></span>
                                Searching Layer A source chunks &amp; current video scene...
                            </div>

                            <div id="ragAnswerBox" style="display:none;max-height:240px;overflow-y:auto;background:var(--bg-page);border:1px solid var(--border-card);border-radius:6px;padding:12px;font-size:12px;line-height:1.5;color:var(--text-ink);">
                                <div id="ragAnswerText" style="margin-bottom:8px;font-size:13px;"></div>
                                <div id="ragCitationsBox" style="font-size:11px;color:var(--text-muted);border-top:1px solid var(--border-card);padding-top:6px;"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!--  Step 5: Personalized Adaptive Learning & Mastery Loop -->
            <div id="adaptiveLearningPanel" class="quiz-card" style="display:none;margin-top:28px;">
                <div class="quiz-header" style="border-bottom:1px solid var(--border-card);padding-bottom:12px;margin-bottom:16px;">
                    <div>
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:20px;">🎯</span>
                            <span style="font-weight:700;font-size:18px;color:var(--text-ink);">Personalized Adaptive Learning</span>
                        </div>
                        <p style="font-size:13px;color:var(--text-muted);margin:4px 0 0 0;">
                            Deterministic mastery state machine driving grounded diagnostic review, video remediation, and practice reassessment
                        </p>
                    </div>
                    <span class="badge badge-peach-green" id="lblAdaptiveBadge">ADAPTIVE LOOP</span>
                </div>

                <!-- Compact Learner Progress / Roadmap Component -->
                <div id="adaptiveRoadmapWidget" style="background:var(--bg-surface);border:1px solid var(--border-card);border-radius:var(--radius-sm);padding:16px;margin-bottom:20px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
                        <span style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--text-muted);">
                            Curriculum Mastery Roadmap
                        </span>
                        <div id="roadmapStatusPill" class="badge badge-blue">Analyzing Path...</div>
                    </div>
                    <div id="roadmapConceptsContainer" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));gap:10px;"></div>
                </div>

                <!-- Dynamic Action Guidance Card -->
                <div id="adaptiveActionCard" style="background:var(--bg-card);border:1px solid var(--peach-green-border);border-radius:var(--radius-sm);padding:20px;display:flex;flex-direction:column;gap:14px;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
                        <div>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span class="badge badge-peach-green" id="lblActionBadge">ACTION</span>
                                <h4 id="lblActionTitle" style="font-size:16px;font-weight:700;color:var(--text-ink);margin:0;">Recommended Next Step</h4>
                            </div>
                            <p id="lblActionDesc" style="font-size:13px;color:var(--text-muted);margin:6px 0 0 0;">Evaluating your learning state...</p>
                        </div>
                        <div id="actionControlsContainer" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                            <!-- Required Action Buttons (dynamically managed) -->
                            <button id="btnStartReview" class="neo-btn neo-btn-peach" style="display:none;" onclick="triggerAdaptiveRemediation()">
                                <span>Start Personalized Review</span>
                            </button>
                            <button id="btnTakeAssessmentAgain" class="neo-btn neo-btn-peach-green" style="display:none;" onclick="triggerReassessmentQuestion()">
                                <span>Take Assessment Again</span>
                            </button>
                            <button id="btnNextQuestion" class="neo-btn neo-btn-peach-green" style="display:none;" onclick="triggerNextReassessmentQuestion()">
                                <span>Next Question</span>
                            </button>
                            <button id="btnContinueNextConcept" class="neo-btn neo-btn-peach-green" style="display:none;" onclick="triggerContinueNextConcept()">
                                <span>Continue to Next Concept</span>
                            </button>
                        </div>
                    </div>

                    <!-- Adaptive Reassessment Question Box -->
                    <div id="adaptiveQuestionBox" style="display:none;background:var(--bg-surface);border:1px solid var(--border-card);border-radius:var(--radius-sm);padding:18px;margin-top:10px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                            <div>
                                <span class="badge badge-peach-green" id="lblReassessConceptBadge">CONCEPT</span>
                                <span class="badge badge-amber" id="lblReassessDifficultyBadge" style="margin-left:6px;">INTERMEDIATE</span>
                            </div>
                            <span class="badge badge-blue">GROUNDED REASSESSMENT</span>
                        </div>
                        <div class="question-stem" id="lblReassessStem" style="margin-bottom:16px;font-size:15px;font-weight:600;color:var(--text-ink);"></div>
                        <div class="options-list" id="reassessOptionsContainer" style="margin-bottom:18px;"></div>
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:12px;color:var(--text-muted);">Authoritative server-side evaluation · Zero answer leakage</span>
                            <button class="neo-btn neo-btn-peach-green" id="btnSubmitAnswer" onclick="submitReassessmentAnswer()">
                                <span>Submit Answer</span>
                            </button>
                        </div>
                    </div>

                    <!-- Adaptive Feedback Notice -->
                    <div id="adaptiveFeedbackBox" style="display:none;padding:12px 16px;border-radius:var(--radius-sm);font-size:13px;font-weight:600;"></div>

                    <!-- Why this review was chosen (Misconception Intelligence) -->
                    <div id="misconceptionReviewCard" style="display:none;background:var(--bg-surface);border:1px solid var(--border-card);border-radius:var(--radius-sm);padding:14px 16px;margin-top:10px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <span style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:0.5px;">
                                Why this review was chosen
                            </span>
                            <span id="lblMisconceptionStatus" class="badge badge-amber">Under review</span>
                        </div>
                        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:10px;font-size:12px;">
                            <div>
                                <span style="color:var(--text-muted);display:block;margin-bottom:2px;">Detected learning gap:</span>
                                <strong id="lblDetectedGap" style="color:var(--text-ink);">-</strong>
                            </div>
                            <div>
                                <span style="color:var(--text-muted);display:block;margin-bottom:2px;">Evidence:</span>
                                <strong id="lblEvidenceAttempts" style="color:var(--text-ink);">-</strong>
                            </div>
                            <div>
                                <span style="color:var(--text-muted);display:block;margin-bottom:2px;">Teaching approach:</span>
                                <strong id="lblTeachingApproach" style="color:var(--peach-green);">-</strong>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </section>

        <!--  Architectural Pipeline Flow Documentation -->
        <section class="flow-section">
            <div style="margin-bottom:8px;">
                <h2 class="flow-title">The Multimodal Assessment Pipeline</h2>
                <p style="font-size:15px;color:var(--text-muted);">Modular, loosely coupled architecture transforming raw study materials into personalized knowledge graphs and diagnostic quizzes</p>
            </div>

            <div class="step-card" style="margin-top:24px;">
                <div class="step-num">1</div>
                <div>
                    <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--peach-green);margin-bottom:4px;">
                        Step 1 - Multimodal Ingestion &amp; Ground Truth Engine
                    </div>
                    <div style="font-size:17px;font-weight:700;color:var(--text-ink);margin-bottom:6px;">
                        Separated Ingestion Pipelines &amp; Layer A Vectorization
                    </div>
                    <div style="font-size:14px;color:var(--text-muted);line-height:1.6;margin-bottom:12px;">
                        Normalizes study materials into an immutable ground-truth repository. Digital text via PyMuPDF; handwritten notes &amp; scans via OpenCV; diagrams via Vision Engine; lectures via FFmpeg and Faster-Whisper. Embedded in Qdrant as <strong>Layer A (Authoritative Source)</strong> with strict provenance.
                    </div>
                    <div class="meta-chip">POST /upload?auto_start_assessment=true &middot; Layer A Locked</div>
                </div>
            </div>

            <div class="step-card">
                <div class="step-num">2</div>
                <div>
                    <div style="font-size:12px;font-weight:700;text-transform:uppercase;color:var(--blue);margin-bottom:4px;">
                        Step 2 - Diagnostic Assessment &amp; Knowledge Profiling
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

            <!--  Solving the Three Generative AI Project Killers Table -->
            <div style="background:var(--bg-card);border:1px solid var(--border-card);border-radius:var(--radius-md);padding:24px;margin-top:24px;">
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

            <!--  FAQ Accordion Section -->
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
                        By passing parsed in-memory content units directly between ingestion and assessment handoff, we eliminate redundant vector lookups. Furthermore, question synthesis runs with a parallel ThreadPoolExecutor against atomic KnowledgeGraph concepts, drastically reducing end-to-end latency from 3-4 minutes to under 60 seconds.
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

        <!--  Footer -->
        <footer class="footer">
            <div>
                <strong style="color:var(--text-ink);">VisualAI</strong> &middot; <span style="color:var(--peach);font-weight:700;">STUDY WITH YOUR VISION</span> &middot; &copy; 2026 VisualAI Technologies Inc.
            </div>
            <div style="display:flex;gap:16px;">
                <a href="/instructor" target="_blank" style="color:var(--text-muted);text-decoration:none;"> Instructor Portal</a>
                <a href="/docs" target="_blank" style="color:var(--text-muted);text-decoration:none;">API Docs</a>
                <a href="/health" target="_blank" style="color:var(--text-muted);text-decoration:none;">System Health</a>
                <a href="/sources" target="_blank" style="color:var(--text-muted);text-decoration:none;">Sources Index</a>
                <a href="#terms" onclick="openModal('tosModal'); return false;" style="color:var(--text-muted);text-decoration:none;">Terms of Service</a>
                <a href="#privacy" onclick="openModal('privacyModal'); return false;" style="color:var(--text-muted);text-decoration:none;">Privacy Policy</a>
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
        let activeModelData = null;

        async function loadModelOptions() {
            try {
                const res = await fetch('/api/models');
                if (!res.ok) return;
                const data = await res.json();
                activeModelData = data;
                renderModelOptions(data);
            } catch (err) {
                console.warn('Could not fetch model options:', err);
            }
        }

        function renderModelOptions(data) {
            const headerSelect = document.getElementById('headerModelSelect');
            const formSelect = document.getElementById('formModelSelect');
            const chainDisplay = document.getElementById('fallbackChainDisplay');
            const badge = document.getElementById('headerFallbackBadge');

            if (data.available_models) {
                if (headerSelect) {
                    headerSelect.innerHTML = '';
                    data.available_models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.name;
                        const label = m.name + (m.provider === 'mock' ? ' (Fast Mock)' : ' (Ollama)');
                        opt.textContent = label + (m.supports_vision ? ' + Vision' : '');
                        if (m.name === data.active_model) opt.selected = true;
                        headerSelect.appendChild(opt);
                    });
                }
                if (formSelect) {
                    formSelect.innerHTML = '';
                    data.available_models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.name;
                        const label = m.name + (m.provider === 'mock' ? ' (Fast Deterministic Mock)' : ' (Ollama Local)');
                        opt.textContent = label + (m.supports_vision ? ' + Vision Support' : '');
                        if (m.name === data.active_model) opt.selected = true;
                        formSelect.appendChild(opt);
                    });
                }
            }

            if (chainDisplay && data.fallback_chain) {
                const chainNames = data.fallback_chain.map(c => c.model);
                chainDisplay.innerHTML = chainNames.map((name, idx) => {
                    const isFirst = idx === 0;
                    return `<span style="color:${isFirst ? 'var(--peach-green)' : 'var(--text-muted)'};font-weight:${isFirst ? '700' : '500'};">${escapeHtml(name)}</span>`;
                }).join(' <span style="color:var(--text-muted);">&rarr;</span> ');
            }

            if (badge) {
                badge.textContent = data.enable_fallback ? 'Fallback: ON' : 'Fallback: OFF';
                badge.style.background = data.enable_fallback ? 'var(--peach-green-soft)' : 'var(--rose-soft)';
                badge.style.color = data.enable_fallback ? 'var(--peach-green)' : 'var(--rose)';
                badge.style.borderColor = data.enable_fallback ? 'var(--peach-green-border)' : 'var(--rose-border)';
            }
        }

        async function switchModel(modelName) {
            if (!modelName) return;
            const headerSelect = document.getElementById('headerModelSelect');
            const formSelect = document.getElementById('formModelSelect');

            if (headerSelect) headerSelect.disabled = true;
            if (formSelect) formSelect.disabled = true;

            try {
                const res = await fetch('/api/models/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: modelName })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Failed to switch model');

                activeModelData = data;
                renderModelOptions(data);
            } catch (err) {
                alert(`Could not switch model: ${err.message}`);
                if (activeModelData) renderModelOptions(activeModelData);
            } finally {
                if (headerSelect) headerSelect.disabled = false;
                if (formSelect) formSelect.disabled = false;
            }
        }

        const STAGE_LABELS = {
            'uploading': 'Phase 1: Ingestion - Uploading Course Material',
            'extracting': 'Phase 1: Extraction - Text Blocks & Embedded Diagrams',
            'knowledge_graph': 'Phase 1: Ground Truth - Constructing Concept Knowledge Graph',
            'indexing': 'Phase 1: Ground Truth - Vectorizing Layer A (Authoritative Source)',
            'planning_assessment': 'Phase 2: Diagnostic - Prerequisite Graph Concept Pairing',
            'generating_questions': 'Phase 2: Knowledge Profiling - Sequential Grounded Questions',
            'validating_questions': 'Phase 2: Validation - Negative Distractors & Fisher-Yates Shuffling',
            'assessment_ready': 'Phase 2: Diagnostic Ready - Commencing Knowledge Profiling'
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

        // Dark Theme Toggle
        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('visualai_theme', newTheme);
            document.getElementById('themeIcon').textContent = newTheme === 'dark' ? 'Light' : 'Dark';
        }

        // Initialize Theme
        const savedTheme = localStorage.getItem('visualai_theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);

        //  Animated Statistics Counters
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

        //  FAQ Accordion Toggle
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
                info.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
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
            const statusBox = document.getElementById('statusBox');
            if (statusBox) statusBox.style.display = 'none';
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
            if (ev.status === 'running') iconHtml = '';
            else if (ev.status === 'completed') iconHtml = '•';
            else if (ev.status === 'warning') iconHtml = '️';
            else if (ev.status === 'failed') iconHtml = '[x]';

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
            const WATCHDOG_INTERVAL_MS = 3000;
            const stream = new EventSource(`/pipeline/jobs/${jobId}/events`);
            activeEventSource = stream;
            const stop = () => {
                stopped = true;
                if (pollTimer) {
                    clearTimeout(pollTimer);
                    pollTimer = null;
                }
                stream.close();
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
                    if (data.status === 'failed' || data.status === 'cancelled') return finish(new Error(data.error || `Job ${data.status}`));
                } catch (err) {
                    if (stopped) return;
                    if (++failures >= 5) return finish(new Error(`Progress tracking failed: ${err.message}. Check the job before uploading again.`));
                }
                if (!stopped) {
                    clearTimeout(pollTimer);
                    pollTimer = setTimeout(poll, WATCHDOG_INTERVAL_MS);
                }
            };
            stream.onmessage = event => {
                if (stopped || !event.data) return;
                try {
                    const ev = JSON.parse(event.data);
                    updateTimelineEvent(ev);
                    // Defer watchdog polling when active SSE events arrive
                    if (!stopped) {
                        clearTimeout(pollTimer);
                        pollTimer = setTimeout(poll, WATCHDOG_INTERVAL_MS);
                    }
                    if (ev.terminal && ev.status === 'completed') finish(null, ev);
                    else if (ev.terminal && (ev.status === 'failed' || ev.status === 'cancelled')) finish(new Error(ev.message || `Job ${ev.status}`));
                } catch (err) {
                    finish(err);
                }
            };
            stream.onerror = () => {
                stream.close();
                clearTimeout(pollTimer);
                if (!stopped) pollTimer = setTimeout(poll, 500);
            };
            // Watchdog poll runs only if SSE does not deliver within interval
            pollTimer = setTimeout(poll, WATCHDOG_INTERVAL_MS);
        }

        window.addEventListener('beforeunload', () => {
            if (stopJobTracking) stopJobTracking();
        });

        const VISION_ERROR_MESSAGES = {
            'VISION_TIMEOUT': 'Visual understanding took too long. Please retry.',
            'VISION_RATE_LIMIT': 'Visual service temporarily unavailable. Please retry shortly.',
            'VISION_INVALID_RESPONSE': 'Visual provider returned an unusable result. Please retry.',
            'VISION_AUTH_FAILED': 'Visual service configuration unavailable.',
            'VISION_PROVIDER_FAILED': 'Visual understanding could not be completed.',
            'VISION_STRUCTURED_OUTPUT_UNAVAILABLE': 'Structured visual output is not supported by current provider.',
            'VISION_FALLBACK_UNAVAILABLE': 'Vision fallback service is currently unavailable.'
        };

        function mapPipelineError(rawMsg) {
            if (!rawMsg) return 'Pipeline execution failed. Please retry.';
            for (const [code, userMsg] of Object.entries(VISION_ERROR_MESSAGES)) {
                if (rawMsg.includes(code)) {
                    return userMsg;
                }
            }
            return rawMsg;
        }

        function showPipelineError(errMessage, jobId) {
            if (timelineTimerInterval) clearInterval(timelineTimerInterval);
            timelineTimerInterval = null;
            const userMsg = mapPipelineError(errMessage);
            const statusBox = document.getElementById('statusBox');
            if (statusBox) {
                statusBox.style.display = 'block';
                statusBox.style.background = '#fef2f2';
                statusBox.style.border = '1px solid #f87171';
                statusBox.style.color = '#991b1b';
                statusBox.innerHTML = `
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
                        <div>
                            <strong>Pipeline Notice:</strong> <span>${escapeHtml(userMsg)}</span>
                        </div>
                        ${jobId ? `<button class="neo-btn neo-btn-peach-green" id="btnRetryExtraction" onclick="retryJob('${escapeHtml(jobId)}')" style="padding:6px 14px;font-size:13px;white-space:nowrap;"><span> Retry Extraction</span></button>` : ''}
                    </div>
                `;
            }
        }

        async function retryJob(jobId) {
            const retryBtn = document.getElementById('btnRetryExtraction');
            if (retryBtn) {
                retryBtn.disabled = true;
                retryBtn.innerHTML = '<span> Retrying...</span>';
            }
            const statusBox = document.getElementById('statusBox');
            if (statusBox) statusBox.style.display = 'none';

            const btn = document.getElementById('btnUpload');
            btn.disabled = true;
            btn.innerHTML = '<span> Retrying Extraction...</span>';
            resetTimeline();

            try {
                const res = await fetch(`/pipeline/jobs/${encodeURIComponent(jobId)}/retry`, {
                    method: 'POST'
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                if (data.job_id) {
                    trackJobSSE(data.job_id, async () => {
                        btn.disabled = false;
                        btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                        const resultRes = await fetch(`/pipeline/jobs/${data.job_id}`);
                        if (!resultRes.ok) throw new Error("Cannot retrieve completed assessment");
                        const resultData = await resultRes.json();
                        if (!resultData.result?.assessment?.questions?.length) throw new Error("Completed job has no quiz");
                        startQuiz(resultData.result.assessment);
                        loadSources();
                    }, (err) => {
                        btn.disabled = false;
                        btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                        showPipelineError(err.message, data.job_id);
                    });
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                showPipelineError(`Retry failed: ${err.message}`, jobId);
            }
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
            btn.innerHTML = '<span> Uploading &amp; Ingesting...</span>';
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
                        btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                        const resultRes = await fetch(`/pipeline/jobs/${data.job_id}`);
                        if (!resultRes.ok) throw new Error("Cannot retrieve completed assessment");
                        const resultData = await resultRes.json();
                        if (!resultData.result?.assessment?.questions?.length) throw new Error("Completed job has no quiz");
                        startQuiz(resultData.result.assessment);
                        loadSources();
                    }, (err) => {
                        btn.disabled = false;
                        btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                        showPipelineError(err.message, data.job_id);
                    });
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span> Ingest Material &amp; Start Diagnostic Assessment</span>';
                if (timelineTimerInterval) clearInterval(timelineTimerInterval);
                timelineTimerInterval = null;
                showPipelineError(err.message, null);
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
            btn.innerHTML = '<span> Generating Diagnostic Questions...</span>';
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
                btn.innerHTML = '<span> Generate Diagnostic Quiz from Material</span>';
                startQuiz(data);
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span> Generate Diagnostic Quiz from Material</span>';
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
            const vidSec = document.getElementById('videoSection');
            if (vidSec) vidSec.style.display = 'none';
            const vidPlayer = document.getElementById('activeVideoPlayerBox');
            if (vidPlayer) vidPlayer.style.display = 'none';

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
                ? '<span>Submit Diagnostic Assessment</span>'
                : '<span>Next Question</span>';
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
                s.textContent = `${c} (Mastered)`;
                masteriesEl.appendChild(s);
            });
            (profileSummary.weak_concepts || []).forEach(c => {
                const s = document.createElement('span');
                s.className = 'badge badge-amber';
                s.textContent = ` ${c} (Needs Review)`;
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

            // Render Step 3 Remedial Video Targets & Dual-Layer Video RAG
            displayVideoTargets(data);

            // Step 5: Authoritative Adaptive Learning State & Roadmap Sync
            if (currentSession && currentSession.source_id) {
                syncAdaptiveLearning(currentSession.source_id);
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
                            badgeText = 'Authoritative Correct';
                            badgeClass = 'badge badge-green';
                        }
                        if (isUserChoice && !isCorrectAnswer) {
                            optStyle += 'border:1px solid var(--rose-border);background:var(--rose-soft);color:#991b1b;font-weight:600;';
                            badgeText = '[x] Your Choice (Incorrect)';
                            badgeClass = 'badge badge-rose';
                        } else if (isUserChoice && isCorrectAnswer) {
                            badgeText = 'Your Choice (Correct)';
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

        // =========================================================================
        //  Step 3: Video Engine Handlers & Step 4: Dual-Layer Video RAG Assistant
        // =========================================================================
        let currentActiveVideoJobId = null;
        let currentActiveVideoConceptId = null;
        let videoPollInterval = null;

        function displayVideoTargets(data) {
            const videoSec = document.getElementById('videoSection');
            if (!videoSec) return;

            const listEl = document.getElementById('videoTargetsList');
            listEl.innerHTML = '';

            let targets = [];
            if (data.video_target_matrix && Array.isArray(data.video_target_matrix.targets) && data.video_target_matrix.targets.length > 0) {
                targets = data.video_target_matrix.targets;
            } else if (data.profile_summary) {
                const weakNames = data.profile_summary.weak_concepts || [];
                const weakIds = data.profile_summary.weak_concept_ids || [];
                targets = weakNames.map((name, i) => ({
                    concept_id: weakIds[i] || `CONCEPT_${name.toUpperCase().replace(/[^A-Z0-9_]/g, '_')}`,
                    concept_name: name,
                    target_seconds: 45,
                    difficulty: 'intermediate',
                    score: 0.0,
                    directive: `Remedial visual lesson targeting diagnosed prerequisite gap in ${name}`,
                    chunk_ids: [],
                    source_content_ids: []
                }));
            }

            // If score was passing, offer concept reinforcement animations for covered concepts
            if (targets.length === 0 && currentSession && currentSession.questions) {
                const seen = new Set();
                currentSession.questions.forEach(q => {
                    if (q.concept_id && !seen.has(q.concept_id)) {
                        seen.add(q.concept_id);
                        targets.push({
                            concept_id: q.concept_id,
                            concept_name: q.concept_name || q.concept_id,
                            target_seconds: 45,
                            difficulty: 'intermediate',
                            score: 100.0,
                            directive: `Concept reinforcement visual lesson for ${q.concept_name || q.concept_id}`,
                            chunk_ids: [],
                            source_content_ids: []
                        });
                    }
                });
            }

            if (targets.length === 0) {
                videoSec.style.display = 'none';
                return;
            }

            videoSec.style.display = 'block';
            document.getElementById('lblTargetsCount').textContent = `${targets.length} Target${targets.length > 1 ? 's' : ''} Ready`;

            targets.forEach(tgt => {
                const card = document.createElement('div');
                card.className = 'video-target-card';

                const infoDiv = document.createElement('div');
                infoDiv.style.flex = '1';

                const titleRow = document.createElement('div');
                titleRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;';

                const icon = document.createElement('span');
                icon.textContent = '';
                titleRow.appendChild(icon);

                const nameStrong = document.createElement('strong');
                nameStrong.style.cssText = 'font-size:14px;color:var(--text-ink);';
                nameStrong.textContent = tgt.concept_name || tgt.concept_id;
                titleRow.appendChild(nameStrong);

                const durBadge = document.createElement('span');
                durBadge.className = 'badge badge-peach-green';
                durBadge.style.fontSize = '11px';
                durBadge.textContent = `${tgt.target_seconds || 45}s · Manim & Voice`;
                titleRow.appendChild(durBadge);

                infoDiv.appendChild(titleRow);

                const descDiv = document.createElement('div');
                descDiv.style.cssText = 'font-size:12px;color:var(--text-muted);';
                descDiv.textContent = tgt.directive || `Personalized visual remediation on ${tgt.concept_name}`;
                infoDiv.appendChild(descDiv);

                const btn = document.createElement('button');
                btn.className = 'neo-btn neo-btn-peach-green';
                btn.id = `btnGen_${tgt.concept_id}`;
                btn.style.cssText = 'padding:8px 16px;font-size:12px;white-space:nowrap;';
                btn.innerHTML = '<span> Start Personalized Review</span>';
                // Authoritative remediation path flows through Step 5E AdaptiveLearningService
                btn.onclick = () => {
                    if (adaptiveState.sourceId || (currentSession && currentSession.source_id)) {
                        triggerAdaptiveRemediation();
                    } else {
                        triggerVideoGeneration(tgt.concept_id, tgt.concept_name, tgt.target_seconds, tgt.chunk_ids, tgt.source_content_ids);
                    }
                };

                card.appendChild(infoDiv);
                card.appendChild(btn);
                listEl.appendChild(card);
            });
        }

        async function triggerVideoGeneration(conceptId, conceptName, targetSeconds, chunkIds, sourceContentIds) {
            // Adaptive remediation must never use legacy /video/generate directly
            if (adaptiveState.sourceId || (currentSession && currentSession.source_id)) {
                return triggerAdaptiveRemediation();
            }

            const btn = document.getElementById(`btnGen_${conceptId}`);
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span> Enqueuing Video Job...</span>';
            }

            const studentId = currentSession ? (currentSession.student_id || 'student_1') : (document.getElementById('studentId')?.value.trim() || 'student_1');
            const sourceId = currentSession ? currentSession.source_id : (document.getElementById('sourceSelect')?.value || 'SRC_DEFAULT');

            const statusBox = document.getElementById('videoGenStatusBox');
            statusBox.style.display = 'block';
            document.getElementById('lblVideoGenStage').textContent = ` Initializing Video Engine for "${conceptName}"...`;
            document.getElementById('videoGenProgressBar').style.width = '15%';
            document.getElementById('lblVideoGenProgress').textContent = '15%';
            document.getElementById('lblVideoGenDetails').textContent = 'Submitting job to bounded background queue...';

            try {
                const res = await fetch('/video/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: studentId,
                        source_id: sourceId,
                        concept_id: conceptId,
                        concept_name: conceptName,
                        target_seconds: targetSeconds || 45,
                        difficulty: 'intermediate',
                        chunk_ids: chunkIds || [],
                        source_content_ids: sourceContentIds || [],
                        force: true
                    })
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                const jobId = data.job_id;
                pollVideoJob(jobId, conceptId, conceptName, btn);
            } catch (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span> Generate Video Lesson</span>';
                }
                document.getElementById('lblVideoGenStage').textContent = '[Failed] Video Generation Failed';
                document.getElementById('lblVideoGenDetails').textContent = err.message;
                alert(`Video generation error: ${err.message}`);
            }
        }

        function pollVideoJob(jobId, conceptId, conceptName, btn) {
            if (videoPollInterval) clearInterval(videoPollInterval);

            const stagesMap = {
                'QUEUED': { pct: '20%', desc: 'Waiting in bounded queue slot...' },
                'PLANNING': { pct: '35%', desc: 'LLM decomposing concept into declarative Manim scene plans...' },
                'RENDERING': { pct: '60%', desc: 'Compiling mathematical equations and rendering Manim animations...' },
                'GENERATING_AUDIO': { pct: '78%', desc: 'Synthesizing educational voiceover with Edge-TTS...' },
                'ALIGNING': { pct: '88%', desc: 'Whisper aligning audio timing to visual scene timestamps...' },
                'COMPOSITING': { pct: '94%', desc: 'FFmpeg multiplexing video stream, audio track, and captions...' },
                'COMPLETED': { pct: '100%', desc: 'Remedial video lesson completed!' }
            };

            videoPollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/video/status/${encodeURIComponent(jobId)}`);
                    if (!res.ok) return;
                    const job = await res.json();

                    const st = (job.status || '').toUpperCase();
                    const stageInfo = stagesMap[st] || { pct: '50%', desc: job.stage || 'Rendering video lesson...' };

                    document.getElementById('videoGenProgressBar').style.width = stageInfo.pct;
                    document.getElementById('lblVideoGenProgress').textContent = stageInfo.pct;
                    document.getElementById('lblVideoGenStage').textContent = ` ${conceptName}: ${st.replace(/_/g, ' ')}`;
                    document.getElementById('lblVideoGenDetails').textContent = stageInfo.desc;

                    if (st === 'COMPLETED') {
                        clearInterval(videoPollInterval);
                        videoPollInterval = null;

                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span>Video Ready (Re-generate)</span>';
                        }

                        // Load and display video player
                        const playerBox = document.getElementById('activeVideoPlayerBox');
                        playerBox.style.display = 'block';
                        document.getElementById('activeVideoTitle').textContent = `${conceptName} - Remedial Video Lesson`;

                        const videoEl = document.getElementById('remedialVideoPlayer');
                        const sourceEl = document.getElementById('videoSource');
                        sourceEl.src = `/video/${encodeURIComponent(jobId)}/stream?t=${Date.now()}`;
                        videoEl.load();

                        document.getElementById('btnDownloadVideo').href = `/video/${encodeURIComponent(jobId)}`;

                        currentActiveVideoJobId = jobId;
                        currentActiveVideoConceptId = conceptId;

                        videoEl.ontimeupdate = () => {
                            const cur = videoEl.currentTime || 0;
                            const mins = Math.floor(cur / 60);
                            const secs = Math.floor(cur % 60);
                            document.getElementById('lblPlaybackTime').textContent = `Time: ${mins}:${secs < 10 ? '0' : ''}${secs}`;
                        };

                        document.getElementById('videoGenStatusBox').style.display = 'none';
                        playerBox.scrollIntoView({ behavior: 'smooth' });

                        // Step 5: Refresh adaptive learning next-action after video lesson completes
                        const activeSourceId = currentSession ? currentSession.source_id : (document.getElementById('sourceSelect')?.value || null);
                        if (activeSourceId) {
                            syncAdaptiveLearning(activeSourceId);
                        }
                    } else if (st === 'FAILED') {
                        clearInterval(videoPollInterval);
                        videoPollInterval = null;
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span> Retry Generation</span>';
                        }
                        document.getElementById('lblVideoGenStage').textContent = '[Failed] Generation Failed';
                        document.getElementById('lblVideoGenDetails').textContent = job.error_message || 'Video compositor encountered an error.';
                    }
                } catch (e) {
                    console.error('Error polling video job:', e);
                }
            }, 2500);
        }

        async function askVideoRAG() {
            const input = document.getElementById('qaQuestionInput');
            const q = input.value.trim();
            if (!q) return;

            const btn = document.getElementById('btnAskRAG');
            btn.disabled = true;

            const loading = document.getElementById('ragLoading');
            loading.style.display = 'block';

            const answerBox = document.getElementById('ragAnswerBox');
            answerBox.style.display = 'none';

            const videoEl = document.getElementById('remedialVideoPlayer');
            const curTime = (videoEl && !isNaN(videoEl.currentTime)) ? videoEl.currentTime : 0;

            const studentId = currentSession ? (currentSession.student_id || 'student_1') : 'student_1';
            const sourceId = currentSession ? currentSession.source_id : (document.getElementById('sourceSelect')?.value || 'SRC_DEFAULT');

            try {
                const res = await fetch('/qa/answer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: studentId,
                        source_id: sourceId,
                        question: q,
                        video_id: currentActiveVideoJobId || undefined,
                        current_timestamp: curTime > 0 ? curTime : undefined,
                        active_concept_id: currentActiveVideoConceptId || undefined
                    })
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || JSON.stringify(data));

                loading.style.display = 'none';
                answerBox.style.display = 'block';

                const answerTextEl = document.getElementById('ragAnswerText');
                answerTextEl.textContent = data.answer;

                const citBox = document.getElementById('ragCitationsBox');
                citBox.innerHTML = '';

                if (data.citations && data.citations.length > 0) {
                    const citHeader = document.createElement('div');
                    citHeader.style.cssText = 'font-weight:700;margin-bottom:4px;color:var(--text-ink);';
                    citHeader.textContent = 'Authoritative Ground Truth Citations:';
                    citBox.appendChild(citHeader);

                    data.citations.forEach(c => {
                        const citItem = document.createElement('div');
                        citItem.style.cssText = 'margin-bottom:4px;display:flex;align-items:center;gap:6px;';

                        const layerBadge = document.createElement('span');
                        layerBadge.className = c.layer === 'B' ? 'badge badge-blue' : 'badge badge-peach-green';
                        layerBadge.style.fontSize = '10px';
                        layerBadge.textContent = c.layer === 'B' ? 'LAYER B (VIDEO)' : 'LAYER A (TEXTBOOK)';
                        citItem.appendChild(layerBadge);

                        const quote = document.createElement('span');
                        quote.style.fontStyle = 'italic';
                        quote.textContent = `"${(c.quote || '').slice(0, 90)}${c.quote && c.quote.length > 90 ? '...' : ''}"`;
                        citItem.appendChild(quote);

                        if (c.timestamp_start !== null && c.timestamp_start !== undefined && videoEl) {
                            const jumpBtn = document.createElement('button');
                            jumpBtn.className = 'neo-btn neo-btn-peach-green';
                            jumpBtn.style.cssText = 'padding:2px 8px;font-size:10px;margin-left:auto;';
                            jumpBtn.innerHTML = `<span>▶ ${Math.floor(c.timestamp_start)}s</span>`;
                            jumpBtn.onclick = () => {
                                videoEl.currentTime = c.timestamp_start;
                                videoEl.play();
                            };
                            citItem.appendChild(jumpBtn);
                        }

                        citBox.appendChild(citItem);
                    });
                } else {
                    citBox.textContent = 'Grounded strictly in Layer A vector index with zero hallucination loops.';
                }
            } catch (err) {
                loading.style.display = 'none';
                answerBox.style.display = 'block';
                document.getElementById('ragAnswerText').textContent = `Error getting answer: ${err.message}`;
            } finally {
                btn.disabled = false;
            }
        }

        // =========================================================================
        //  Step 5: Client-Side Presentation State Layer & Adaptive Learning Loop
        // =========================================================================
        const adaptiveState = {
            sourceId: null,
            userId: 'student_default',
            nextAction: null,
            roadmap: null,
            currentQuestion: null,
            selectedOptionIdx: null,
            activeJobId: null,
            remediationPollInterval: null,
            isSubmitting: false,
            isGeneratingReassessment: false,
            isRequestingRemediation: false,
            hasAnsweredReassessment: false,
            lastAnsweredQuestionId: null
        };

        function cancelAllPolling() {
            if (videoPollInterval) {
                clearInterval(videoPollInterval);
                videoPollInterval = null;
            }
            if (adaptiveState.remediationPollInterval) {
                clearInterval(adaptiveState.remediationPollInterval);
                adaptiveState.remediationPollInterval = null;
            }
            if (typeof stopJobTracking === 'function' && stopJobTracking) {
                try { stopJobTracking(); } catch (e) {}
            }
        }

        function showInlineError(elementId, message) {
            const el = document.getElementById(elementId);
            if (el) {
                el.style.display = 'block';
                el.className = 'badge badge-rose';
                el.style.padding = '12px 16px';
                el.textContent = message;
            } else {
                console.error(message);
            }
        }

        function getActiveUserId() {
            const sid = (currentSession && currentSession.student_id) ||
                document.getElementById('studentId')?.value.trim() ||
                document.getElementById('studentIdExisting')?.value.trim() ||
                'student_default';
            return sid || 'student_default';
        }

        async function syncAdaptiveLearning(sourceId) {
            if (!sourceId) return;
            adaptiveState.sourceId = sourceId;
            adaptiveState.userId = getActiveUserId();

            // Store safe active navigation context for refresh rehydration
            try {
                sessionStorage.setItem('visualai.active_source.' + adaptiveState.userId, sourceId);
            } catch (e) {}

            const panel = document.getElementById('adaptiveLearningPanel');
            if (panel) panel.style.display = 'block';

            await Promise.all([
                fetchAdaptiveRoadmap(sourceId),
                fetchNextLearningAction(sourceId)
            ]);
        }

        async function fetchAdaptiveRoadmap(sourceId) {
            try {
                const res = await fetch(`/api/learning/${encodeURIComponent(sourceId)}/roadmap?user_id=${encodeURIComponent(adaptiveState.userId)}`);
                if (!res.ok) {
                    if (res.status === 404) return;
                    console.warn(`Roadmap returned HTTP ${res.status}`);
                    return;
                }
                const data = await res.json();
                adaptiveState.roadmap = data;
                renderAdaptiveRoadmap(data);
            } catch (err) {
                console.error('Error fetching adaptive roadmap:', err);
            }
        }

        function renderAdaptiveRoadmap(roadmap) {
            const container = document.getElementById('roadmapConceptsContainer');
            if (!container) return;
            container.innerHTML = '';

            const statusPill = document.getElementById('roadmapStatusPill');
            if (statusPill) {
                const pct = roadmap.overall_progress_percent !== undefined ? roadmap.overall_progress_percent : 0;
                statusPill.textContent = `${pct.toFixed(0)}% Overall Progress`;
            }

            const activeConceptId = roadmap.current_next_action ? roadmap.current_next_action.concept_id : null;

            const categoryConfigs = [
                { key: 'mastered_concepts', label: 'Mastered', badgeClass: 'badge-green', icon: '✓' },
                { key: 'weak_concepts', label: 'Needs Review', badgeClass: 'badge-amber', icon: '⚠' },
                { key: 'remediating_concepts', label: 'Remediating', badgeClass: 'badge-amber', icon: '▶' },
                { key: 'reassessing_concepts', label: 'Reassessing', badgeClass: 'badge-blue', icon: '↻' },
                { key: 'needs_support_concepts', label: 'Needs Support', badgeClass: 'badge-rose', icon: '!' },
                { key: 'unassessed_concepts', label: 'Not Yet Assessed', badgeClass: 'badge-blue', icon: '○' }
            ];

            const totalKnown = (roadmap.mastered_concepts?.length || 0) +
                               (roadmap.weak_concepts?.length || 0) +
                               (roadmap.remediating_concepts?.length || 0) +
                               (roadmap.reassessing_concepts?.length || 0) +
                               (roadmap.needs_support_concepts?.length || 0) +
                               (roadmap.unassessed_concepts?.length || 0);

            if (statusPill && totalKnown > 0) {
                const masteredCount = roadmap.mastered_concepts?.length || 0;
                const calcPct = Math.round((masteredCount / totalKnown) * 100);
                statusPill.textContent = `${calcPct}% Overall Progress`;
            }

            categoryConfigs.forEach(cat => {
                const rawItems = roadmap[cat.key] || [];
                rawItems.forEach(item => {
                    const cid = typeof item === 'string' ? item : (item.concept_id || item.id);
                    const cname = typeof item === 'string' ? item : (item.concept_name || item.name || cid);
                    const isActive = cid === activeConceptId;
                    const card = document.createElement('div');
                    card.style.cssText = `background:var(--bg-card);border:1px solid ${isActive ? 'var(--peach-green)' : 'var(--border-card)'};border-radius:var(--radius-sm);padding:10px 12px;display:flex;flex-direction:column;gap:6px;position:relative;`;

                    const topRow = document.createElement('div');
                    topRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';

                    const nameSpan = document.createElement('strong');
                    nameSpan.style.cssText = 'font-size:13px;color:var(--text-ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px;';
                    nameSpan.textContent = cname;
                    nameSpan.title = cname;

                    const b = document.createElement('span');
                    b.className = `badge ${cat.badgeClass}`;
                    b.style.fontSize = '10px';
                    b.textContent = `${cat.icon} ${cat.label}`;

                    topRow.appendChild(nameSpan);
                    topRow.appendChild(b);
                    card.appendChild(topRow);

                    if (isActive) {
                        const activeTag = document.createElement('div');
                        activeTag.style.cssText = 'font-size:11px;font-weight:700;color:var(--peach-green);';
                        activeTag.textContent = '★ Active Focus Concept';
                        card.appendChild(activeTag);
                    }

                    // Expose safe learner-facing misconception journey tag
                    const journeyItem = (roadmap.misconception_journey || []).find(j => (j.concept_id || j.id) === cid) ||
                                        (roadmap.concept_summaries || []).find(s => (s.concept_id || s.id) === cid);
                    if (journeyItem) {
                        if (journeyItem.misconception_status === 'CORRECTED') {
                            const corBadge = document.createElement('div');
                            corBadge.style.cssText = 'font-size:10px;font-weight:700;color:var(--peach-green);margin-top:2px;';
                            corBadge.textContent = '✓ Gap Corrected';
                            card.appendChild(corBadge);
                        } else if (journeyItem.active_misconception_label) {
                            const gapBadge = document.createElement('div');
                            gapBadge.style.cssText = 'font-size:10px;font-weight:600;color:var(--amber, #f59e0b);margin-top:2px;';
                            gapBadge.textContent = `Gap: ${journeyItem.active_misconception_label}`;
                            card.appendChild(gapBadge);
                        }
                    }

                    container.appendChild(card);
                });
            });

            if (container.children.length === 0) {
                container.innerHTML = '<div style="font-size:12px;color:var(--text-muted);grid-column:1/-1;">No curriculum concepts detected yet.</div>';
            }
        }

        async function fetchNextLearningAction(sourceId) {
            try {
                const res = await fetch(`/api/learning/${encodeURIComponent(sourceId)}/next-action?user_id=${encodeURIComponent(adaptiveState.userId)}`);
                if (!res.ok) {
                    if (res.status === 404) return;
                    console.warn(`Next-action returned HTTP ${res.status}`);
                    return;
                }
                const data = await res.json();
                adaptiveState.nextAction = data;

                // Refresh rehydration checks
                if (data.metadata) {
                    // Active remediation running in background
                    if (data.metadata.active_remediation_job_id &&
                        !['READY', 'FAILED', 'CANCELLED'].includes((data.metadata.active_remediation_status || '').toUpperCase()) &&
                        !adaptiveState.remediationPollInterval) {
                        adaptiveState.activeJobId = data.metadata.active_remediation_job_id;
                        pollAdaptiveRemediationJob(sourceId, data.metadata.active_remediation_job_id);
                    }

                    // Completed video ready for viewing
                    if (data.metadata.video_ready && data.metadata.stream_url) {
                        const playerBox = document.getElementById('activeVideoPlayerBox');
                        if (playerBox) {
                            playerBox.style.display = 'block';
                            document.getElementById('activeVideoTitle').textContent = `${data.concept_name || data.concept_id || 'Concept'} - Remedial Lesson`;
                            const videoEl = document.getElementById('remedialVideoPlayer');
                            const sourceEl = document.getElementById('videoSource');
                            if (sourceEl && (!sourceEl.src || !sourceEl.src.includes(data.metadata.stream_url))) {
                                sourceEl.src = `${data.metadata.stream_url}?t=${Date.now()}`;
                                videoEl.load();
                            }
                        }
                    }

                    // Restore pending uncompleted reassessment question
                    if (data.metadata.pending_question && !adaptiveState.currentQuestion && !adaptiveState.hasAnsweredReassessment) {
                        renderReassessmentQuestion(data.metadata.pending_question);
                    }
                }

                renderAdaptiveAction(data);
            } catch (err) {
                console.error('Error fetching next learning action:', err);
            }
        }

        function renderAdaptiveAction(action) {
            const titleEl = document.getElementById('lblActionTitle');
            const descEl = document.getElementById('lblActionDesc');
            const badgeEl = document.getElementById('lblActionBadge');

            const btnStartReview = document.getElementById('btnStartReview');
            const btnTakeAssessmentAgain = document.getElementById('btnTakeAssessmentAgain');
            const btnNextQuestion = document.getElementById('btnNextQuestion');
            const btnContinueNextConcept = document.getElementById('btnContinueNextConcept');
            const questionBox = document.getElementById('adaptiveQuestionBox');
            const feedbackBox = document.getElementById('adaptiveFeedbackBox');

            // Reset action buttons visibility
            btnStartReview.style.display = 'none';
            btnTakeAssessmentAgain.style.display = 'none';
            btnNextQuestion.style.display = 'none';
            btnContinueNextConcept.style.display = 'none';

            if (!action || !action.action_type) {
                titleEl.textContent = 'Learning Path in Progress';
                descEl.textContent = 'Continue your diagnostic assessment or explore course material.';
                return;
            }

            badgeEl.textContent = action.action_type;
            const conceptLabel = action.concept_name || action.concept_id || 'Concept';

            switch (action.action_type) {
                case 'REMEDIATE':
                    badgeEl.className = 'badge badge-amber';
                    titleEl.textContent = `Concept needs review: ${conceptLabel}`;
                    descEl.textContent = action.reason || 'Your recent assessment indicates a diagnosed gap. Watch a tailored remediation lesson to build solid ground truth.';
                    btnStartReview.style.display = 'inline-flex';
                    btnStartReview.disabled = false;
                    btnStartReview.innerHTML = '<span>Start Personalized Review</span>';
                    questionBox.style.display = 'none';
                    break;

                case 'REASSESS':
                    badgeEl.className = 'badge badge-peach-green';
                    titleEl.textContent = `Practice Assessment: ${conceptLabel}`;
                    descEl.textContent = action.reason || 'You reviewed the remediation lesson. Verify your understanding with grounded practice questions.';

                    const attemptsCount = action.metadata ? (action.metadata.reassessment_attempts_count || 0) : 0;
                    const hasAnswered = adaptiveState.hasAnsweredReassessment || (attemptsCount > 0);

                    if (adaptiveState.currentQuestion) {
                        // Current question is visible and answering in progress
                        questionBox.style.display = 'block';
                        btnTakeAssessmentAgain.style.display = 'none';
                        btnNextQuestion.style.display = 'none';
                    } else if (hasAnswered) {
                        // At least one question answered, policy requires additional evidence -> show Next Question!
                        btnNextQuestion.style.display = 'inline-flex';
                        btnNextQuestion.disabled = false;
                        btnNextQuestion.innerHTML = '<span>Next Question</span>';
                        btnTakeAssessmentAgain.style.display = 'none';
                        questionBox.style.display = 'none';
                    } else {
                        // Fresh reassessment entry -> prompt learner to take assessment again
                        btnTakeAssessmentAgain.style.display = 'inline-flex';
                        btnTakeAssessmentAgain.disabled = false;
                        btnTakeAssessmentAgain.innerHTML = '<span>Take Assessment Again</span>';
                        btnNextQuestion.style.display = 'none';
                        questionBox.style.display = 'none';
                    }
                    break;

                case 'ASSESS':
                    badgeEl.className = 'badge badge-blue';
                    titleEl.textContent = `Ready for Next Focus: ${conceptLabel}`;
                    descEl.textContent = action.reason || 'Prerequisites are mastered! Proceed to the next curriculum concept.';
                    btnContinueNextConcept.style.display = 'inline-flex';
                    btnContinueNextConcept.disabled = false;
                    btnContinueNextConcept.innerHTML = '<span>Continue to Next Concept</span>';
                    questionBox.style.display = 'none';
                    break;

                case 'NEEDS_SUPPORT':
                    badgeEl.className = 'badge badge-rose';
                    titleEl.textContent = `Concept needs additional support: ${conceptLabel}`;
                    descEl.textContent = action.reason || 'Multiple remediation attempts completed. We recommend consulting your instructor or reviewing foundational course material.';
                    questionBox.style.display = 'none';
                    if (feedbackBox) {
                        feedbackBox.style.display = 'block';
                        feedbackBox.className = 'badge badge-rose';
                        feedbackBox.style.padding = '12px';
                        feedbackBox.textContent = 'This concept needs additional support. Instructor assistance recommended before further attempts.';
                    }
                    break;

                case 'COMPLETE':
                    badgeEl.className = 'badge badge-green';
                    titleEl.textContent = '🎉 Learning Path Complete!';
                    descEl.textContent = action.reason || 'Outstanding achievement! You have mastered all concepts in this curriculum.';
                    questionBox.style.display = 'none';
                    if (feedbackBox) {
                        feedbackBox.style.display = 'block';
                        feedbackBox.className = 'badge badge-green';
                        feedbackBox.style.padding = '14px';
                        feedbackBox.textContent = '✓ All course concepts fully mastered according to authoritative ground truth evaluation.';
                    }
                    break;

                default:
                    titleEl.textContent = `Current Step: ${action.action_type}`;
                    descEl.textContent = action.reason || '';
                    break;
            }

            // Misconception Intelligence Presentation ("Why this review was chosen")
            const misCard = document.getElementById('misconceptionReviewCard');
            if (misCard) {
                const whyChosen = action.why_chosen || (action.metadata && action.metadata.why_chosen);
                const misLabel = action.active_misconception_label || (whyChosen && whyChosen.detected_learning_gap);
                if (whyChosen || misLabel) {
                    misCard.style.display = 'block';
                    const gapEl = document.getElementById('lblDetectedGap');
                    const evEl = document.getElementById('lblEvidenceAttempts');
                    const approachEl = document.getElementById('lblTeachingApproach');
                    const statusBadge = document.getElementById('lblMisconceptionStatus');

                    if (gapEl) gapEl.textContent = (whyChosen && whyChosen.detected_learning_gap) || misLabel || 'Diagnosed conceptual gap';
                    if (evEl) evEl.textContent = (whyChosen && whyChosen.evidence) || (action.evidence_attempt_ids ? `${action.evidence_attempt_ids.length} assessment attempts` : 'Assessment evidence');
                    if (approachEl) approachEl.textContent = (whyChosen && whyChosen.teaching_approach) || (action.strategy_used ? action.strategy_used.replace(/_/g, ' ') : 'Targeted review');

                    const statusVal = (whyChosen && whyChosen.status) || (action.misconception_status === 'CORRECTED' ? 'Corrected' : 'Under review');
                    if (statusBadge) {
                        statusBadge.textContent = statusVal;
                        if (statusVal.toLowerCase() === 'corrected') {
                            statusBadge.className = 'badge badge-green';
                        } else {
                            statusBadge.className = 'badge badge-amber';
                        }
                    }
                } else {
                    misCard.style.display = 'none';
                }
            }
        }

        async function triggerAdaptiveRemediation() {
            if (adaptiveState.isRequestingRemediation) return;
            const sourceId = adaptiveState.sourceId;
            if (!sourceId) return;

            const btn = document.getElementById('btnStartReview');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>Preparing your explanation...</span>';
            }
            adaptiveState.isRequestingRemediation = true;

            const statusBox = document.getElementById('videoGenStatusBox');
            statusBox.style.display = 'block';
            document.getElementById('lblVideoGenStage').textContent = 'Preparing personalized explanation...';
            document.getElementById('videoGenProgressBar').style.width = '20%';
            document.getElementById('lblVideoGenProgress').textContent = '20%';
            document.getElementById('lblVideoGenDetails').textContent = 'Submitting remediation request to Step 5E orchestrator...';

            try {
                const res = await fetch(`/api/learning/${encodeURIComponent(sourceId)}/remediation?user_id=${encodeURIComponent(adaptiveState.userId)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        concept_id: adaptiveState.nextAction ? adaptiveState.nextAction.concept_id : null,
                        force: false
                    })
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    const msg = (errData.detail && errData.detail.message) || errData.detail || 'Remediation request rejected';
                    throw new Error(msg);
                }

                const data = await res.json();
                const jobId = data.remediation_job_id || data.job_id;
                adaptiveState.activeJobId = jobId;

                pollAdaptiveRemediationJob(sourceId, jobId);
            } catch (err) {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>Start Personalized Review</span>';
                }
                adaptiveState.isRequestingRemediation = false;
                document.getElementById('lblVideoGenStage').textContent = 'Remediation request could not start';
                document.getElementById('lblVideoGenDetails').textContent = err.message;
                showInlineError('adaptiveFeedbackBox', `Remediation error: ${err.message}`);
            }
        }

        function pollAdaptiveRemediationJob(sourceId, jobId) {
            if (adaptiveState.remediationPollInterval) {
                clearInterval(adaptiveState.remediationPollInterval);
                adaptiveState.remediationPollInterval = null;
            }

            adaptiveState.remediationPollInterval = setInterval(async () => {
                try {
                    const res = await fetch(`/api/learning/${encodeURIComponent(sourceId)}/remediation/${encodeURIComponent(jobId)}?user_id=${encodeURIComponent(adaptiveState.userId)}`);
                    if (!res.ok) {
                        if (res.status === 404) {
                            clearInterval(adaptiveState.remediationPollInterval);
                            adaptiveState.remediationPollInterval = null;
                            adaptiveState.isRequestingRemediation = false;
                        }
                        return;
                    }

                    const data = await res.json();
                    const st = (data.status || '').toUpperCase();

                    document.getElementById('lblVideoGenStage').textContent = `Generating learning video... [${st}]`;
                    if (data.progress_percent !== undefined && data.progress_percent !== null) {
                        const pct = Math.max(20, Math.min(100, data.progress_percent));
                        document.getElementById('videoGenProgressBar').style.width = `${pct}%`;
                        document.getElementById('lblVideoGenProgress').textContent = `${pct}%`;
                    }

                    if (st === 'READY') {
                        clearInterval(adaptiveState.remediationPollInterval);
                        adaptiveState.remediationPollInterval = null;
                        adaptiveState.isRequestingRemediation = false;

                        // Display video player using safe stream URL
                        const playerBox = document.getElementById('activeVideoPlayerBox');
                        playerBox.style.display = 'block';
                        document.getElementById('activeVideoTitle').textContent = `${data.concept_id} - Remedial Lesson`;

                        const videoEl = document.getElementById('remedialVideoPlayer');
                        const sourceEl = document.getElementById('videoSource');
                        if (data.stream_url) {
                            sourceEl.src = `${data.stream_url}?t=${Date.now()}`;
                            videoEl.load();
                        }

                        document.getElementById('videoGenStatusBox').style.display = 'none';
                        playerBox.scrollIntoView({ behavior: 'smooth' });

                        // Sync authoritative next action -> expect REASSESS
                        await syncAdaptiveLearning(sourceId);
                    } else if (st === 'FAILED' || st === 'CANCELLED') {
                        clearInterval(adaptiveState.remediationPollInterval);
                        adaptiveState.remediationPollInterval = null;
                        adaptiveState.isRequestingRemediation = false;

                        const btn = document.getElementById('btnStartReview');
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span>Start Personalized Review</span>';
                        }
                        document.getElementById('lblVideoGenStage').textContent = 'Video explanation failed';
                        document.getElementById('lblVideoGenDetails').textContent = data.failure_message || data.error_message || 'Video compositor encountered an error.';
                    }
                } catch (e) {
                    console.error('Error polling adaptive remediation job:', e);
                }
            }, 2500);
        }

        async function triggerReassessmentQuestion() {
            if (adaptiveState.isGeneratingReassessment) return;
            const sourceId = adaptiveState.sourceId;
            if (!sourceId) return;

            const btn = document.getElementById('btnTakeAssessmentAgain');
            btn.disabled = true;
            btn.innerHTML = '<span>Preparing next practice question...</span>';
            adaptiveState.isGeneratingReassessment = true;

            const conceptId = adaptiveState.nextAction ? adaptiveState.nextAction.concept_id : null;
            const url = `/api/learning/${encodeURIComponent(sourceId)}/reassessment/generate?user_id=${encodeURIComponent(adaptiveState.userId)}${conceptId ? `&concept_id=${encodeURIComponent(conceptId)}` : ''}`;

            try {
                const res = await fetch(url, { method: 'POST' });
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    const msg = (errData.detail && errData.detail.message) || errData.detail || 'Reassessment question generation failed';
                    throw new Error(msg);
                }

                const question = await res.json();
                renderReassessmentQuestion(question);
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>Take Assessment Again</span>';
                showInlineError('adaptiveFeedbackBox', `Could not generate practice question: ${err.message}`);
            } finally {
                adaptiveState.isGeneratingReassessment = false;
            }
        }

        async function triggerNextReassessmentQuestion() {
            if (adaptiveState.isGeneratingReassessment) return;
            const sourceId = adaptiveState.sourceId;
            if (!sourceId) return;

            const btn = document.getElementById('btnNextQuestion');
            btn.disabled = true;
            btn.innerHTML = '<span>Preparing next practice question...</span>';
            adaptiveState.isGeneratingReassessment = true;

            const conceptId = adaptiveState.nextAction ? adaptiveState.nextAction.concept_id : null;
            const prevQid = adaptiveState.lastAnsweredQuestionId || (adaptiveState.currentQuestion ? adaptiveState.currentQuestion.question_id : null);
            let url = `/api/learning/${encodeURIComponent(sourceId)}/reassessment/generate?user_id=${encodeURIComponent(adaptiveState.userId)}`;
            if (conceptId) url += `&concept_id=${encodeURIComponent(conceptId)}`;
            if (prevQid) url += `&previous_question_id=${encodeURIComponent(prevQid)}`;

            try {
                const res = await fetch(url, { method: 'POST' });
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    const msg = (errData.detail && errData.detail.message) || errData.detail || 'Next practice question generation failed';
                    throw new Error(msg);
                }

                const question = await res.json();
                btn.style.display = 'none';
                renderReassessmentQuestion(question);
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>Next Question</span>';
                showInlineError('adaptiveFeedbackBox', `Could not load next question: ${err.message}`);
            } finally {
                adaptiveState.isGeneratingReassessment = false;
            }
        }

        function renderReassessmentQuestion(q) {
            adaptiveState.currentQuestion = q;
            adaptiveState.selectedOptionIdx = null;

            const box = document.getElementById('adaptiveQuestionBox');
            box.style.display = 'block';

            document.getElementById('lblReassessConceptBadge').textContent = q.concept_name || q.concept_id || 'PRACTICE';
            document.getElementById('lblReassessDifficultyBadge').textContent = (q.difficulty || 'intermediate').toUpperCase();
            document.getElementById('lblReassessStem').textContent = q.stem;

            const container = document.getElementById('reassessOptionsContainer');
            container.innerHTML = '';

            (q.options || []).forEach((opt, idx) => {
                const optId = `reassess_opt_${idx}`;
                const label = document.createElement('label');
                label.className = 'option-item';
                label.htmlFor = optId;

                const input = document.createElement('input');
                input.type = 'radio';
                input.name = 'reassessment_choice';
                input.id = optId;
                input.value = idx;
                input.addEventListener('change', () => {
                    adaptiveState.selectedOptionIdx = idx;
                });

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

            const submitBtn = document.getElementById('btnSubmitAnswer');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>Submit Answer</span>';

            const feedbackBox = document.getElementById('adaptiveFeedbackBox');
            if (feedbackBox) feedbackBox.style.display = 'none';

            box.scrollIntoView({ behavior: 'smooth' });
        }

        async function submitReassessmentAnswer() {
            if (adaptiveState.isSubmitting) return;
            if (adaptiveState.selectedOptionIdx === null || adaptiveState.selectedOptionIdx === undefined) {
                showInlineError('adaptiveFeedbackBox', 'Please select an answer choice before submitting.');
                return;
            }
            if (!adaptiveState.currentQuestion) return;

            const sourceId = adaptiveState.sourceId;
            const q = adaptiveState.currentQuestion;

            const submitBtn = document.getElementById('btnSubmitAnswer');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span>Checking your understanding...</span>';
            adaptiveState.isSubmitting = true;

            const attemptId = `ATT_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;

            const payload = {
                attempt_id: attemptId,
                question_id: q.question_id,
                concept_id: q.concept_id,
                assessment_type: 'REASSESSMENT',
                selected_answer: adaptiveState.selectedOptionIdx,
                response_time_seconds: 15.0
            };

            try {
                const res = await fetch(`/api/learning/${encodeURIComponent(sourceId)}/assessment/submit?user_id=${encodeURIComponent(adaptiveState.userId)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    const msg = (errData.detail && errData.detail.message) || errData.detail || 'Assessment submission failed';
                    throw new Error(msg);
                }

                const result = await res.json();

                // Save answered question state and clear active currentQuestion
                adaptiveState.lastAnsweredQuestionId = q.question_id;
                adaptiveState.currentQuestion = null;
                adaptiveState.hasAnsweredReassessment = true;

                // Show safe feedback in the feedback box
                const feedbackBox = document.getElementById('adaptiveFeedbackBox');
                if (feedbackBox) {
                    feedbackBox.style.display = 'block';
                    feedbackBox.className = result.is_correct ? 'badge badge-green' : 'badge badge-rose';
                    feedbackBox.style.padding = '12px 16px';
                    feedbackBox.textContent = result.is_correct
                        ? `✓ Correct! ${result.explanation || 'Great job applying the concept.'}`
                        : `✗ Not quite. ${result.explanation || 'Review the explanation to reinforce your understanding.'}`;
                }

                // Hide question box until next question is loaded
                document.getElementById('adaptiveQuestionBox').style.display = 'none';

                // Re-sync authoritative next action and roadmap
                await syncAdaptiveLearning(sourceId);
            } catch (err) {
                showInlineError('adaptiveFeedbackBox', `Submission error: ${err.message}`);
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<span>Submit Answer</span>';
            } finally {
                adaptiveState.isSubmitting = false;
            }
        }

        async function triggerContinueNextConcept() {
            const nextAct = adaptiveState.nextAction;
            if (!nextAct || !nextAct.concept_id) return;
            const sourceId = adaptiveState.sourceId;

            // Generate diagnostic quiz for the next focus concept or prompt learner
            const btn = document.getElementById('btnContinueNextConcept');
            btn.disabled = true;
            btn.innerHTML = '<span>Loading Next Assessment...</span>';

            try {
                const res = await fetch('/assessment/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_id: sourceId,
                        student_id: adaptiveState.userId,
                        max_questions: 3
                    })
                });

                if (!res.ok) throw new Error('Could not start assessment for next concept');
                const data = await res.json();
                btn.disabled = false;
                btn.innerHTML = '<span>Continue to Next Concept</span>';
                startQuiz(data);
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '<span>Continue to Next Concept</span>';
                showInlineError('adaptiveFeedbackBox', `Next assessment error: ${err.message}`);
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            loadSources();
            initCounters();
            loadModelOptions();

            // Refresh state rehydration from safe client-side navigation context
            const activeUser = getActiveUserId();
            const savedSource = sessionStorage.getItem('visualai.active_source.' + activeUser);
            if (savedSource) {
                adaptiveState.sourceId = savedSource;
                syncAdaptiveLearning(savedSource);
            }

            const srcSelect = document.getElementById('sourceSelect');
            if (srcSelect) {
                srcSelect.addEventListener('change', () => {
                    const selectedSource = srcSelect.value;
                    if (selectedSource) {
                        syncAdaptiveLearning(selectedSource);
                    }
                });
            }

            window.addEventListener('beforeunload', cancelAllPolling);
        });
    
        function openModal(id) {
            const el = document.getElementById(id);
            if (el) el.style.display = 'flex';
        }
        function closeModal(id) {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        }
    
    </script>

    <!-- Terms of Service Modal -->
    <div id="tosModal" class="modal-overlay" onclick="if(event.target===this)closeModal('tosModal')">
        <div class="modal-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 style="font-size:20px;font-weight:700;">Terms of Service</h3>
                <button class="neo-btn" onclick="closeModal('tosModal')">Close</button>
            </div>
            <div style="font-size:14px;color:var(--text-body);line-height:1.6;">
                <p style="margin-bottom:12px;">VisualAI provides grounded educational assessment and programmatic video generation based strictly on user-supplied course materials.</p>
                <p style="margin-bottom:12px;">1. Ground Truth Integrity: All diagnostic questions and video explanations are derived from verified Layer A source chunks.</p>
                <p style="margin-bottom:12px;">2. User Data Scope: Ingested documents and student learning profiles remain isolated to the designated student identifier.</p>
                <p>3. Anti-Loop Protection: Learning sessions employ deterministic safeguards to avoid cognitive fatigue and loop cycles.</p>
            </div>
        </div>
    </div>

    <!-- Privacy Policy Modal -->
    <div id="privacyModal" class="modal-overlay" onclick="if(event.target===this)closeModal('privacyModal')">
        <div class="modal-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 style="font-size:20px;font-weight:700;">Privacy Policy</h3>
                <button class="neo-btn" onclick="closeModal('privacyModal')">Close</button>
            </div>
            <div style="font-size:14px;color:var(--text-body);line-height:1.6;">
                <p style="margin-bottom:12px;">VisualAI respects user privacy and enforces strict data boundary controls.</p>
                <p style="margin-bottom:12px;">1. Ingestion Isolation: Uploaded materials are processed locally and never shared across student identities.</p>
                <p style="margin-bottom:12px;">2. Telemetry and Analytics: Learning performance metrics are used solely to generate targeted remediation videos.</p>
                <p>3. Retention: Artifacts and profiles are securely stored under verified runtime paths.</p>
            </div>
        </div>
    </div>

    <!-- Antigravity Floral Cursor Interaction Animation Script -->
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

        window.addEventListener('touchmove', function(e) {
            if (e.touches && e.touches.length > 0) {
                mouse.targetX = e.touches[0].clientX;
                mouse.targetY = e.touches[0].clientY;
                mouse.active = true;
            }
        }, { passive: true });

        window.addEventListener('touchend', function() {
            mouse.active = false;
            mouse.targetX = -2000;
            mouse.targetY = -2000;
        }, { passive: true });

        function getPalette() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            return {
                isDark: isDark,
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

        const count = Math.min(58, Math.max(28, Math.floor((width * height) / 24000)));
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
    </script>
    
</body>
</html>
"""


@router.api_route("/dashboard", methods=["GET", "HEAD"], response_class=HTMLResponse)
def dashboard():
    """VisualAI dashboard - Interactive test runner and complete pipeline documentation."""
    return HTMLResponse(content=DASHBOARD_HTML)
