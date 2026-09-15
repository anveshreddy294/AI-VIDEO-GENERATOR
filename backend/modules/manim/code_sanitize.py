"""Sanitize generated Manim scene code for environments without full LaTeX."""

from __future__ import annotations

import re

_LATEX_SYMBOLS = (
    (r"\times", "×"),
    (r"\cdot", "·"),
    (r"\Delta", "Δ"),
    (r"\theta", "θ"),
    (r"\alpha", "α"),
    (r"\beta", "β"),
    (r"\gamma", "γ"),
    (r"\pi", "π"),
    (r"\omega", "ω"),
    (r"\nu", "ν"),
    (r"\leq", "≤"),
    (r"\geq", "≥"),
    (r"\neq", "≠"),
    (r"\approx", "≈"),
    (r"\infty", "∞"),
    (r"\rightarrow", "→"),
    (r"\leftarrow", "←"),
    (r"\Rightarrow", "⇒"),
    (r"\cos", "cos"),
    (r"\sin", "sin"),
    (r"\tan", "tan"),
    (r"\log", "log"),
    (r"\ln", "ln"),
    (r"\sqrt", "√"),
)

_TEX_CALL_RE = re.compile(
    r"(?:MathTex|Tex)\(\s*(r?)([\"'])(.*?)\2([^)]*)\)",
    re.DOTALL,
)

_TEXT_CALL_RE = re.compile(
    r"Text\(\s*(r?)([\"'])(.*?)\2([^)]*)\)",
    re.DOTALL,
)


def has_latex_mobjects(code: str) -> bool:
    return "MathTex(" in code or re.search(r"\bTex\(", code) is not None


def is_latex_render_error(error: str) -> bool:
    markers = (
        "latex error",
        "standalone.cls",
        "tex_to_svg_file",
        "ValueError: latex",
    )
    lower = error.lower()
    return any(m in lower for m in markers)


def latex_to_plain(tex: str) -> str:
    s = tex.replace("\\\\", "\\")
    for src, dst in _LATEX_SYMBOLS:
        s = s.replace(src, dst)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("{", "").replace("}", "").replace("^", "").replace("_", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s or tex


def strip_latex_in_text_literals(code: str) -> str:
    """Replace LaTeX tokens inside Text(...) string literals with plain text."""

    def _repl(match: re.Match[str]) -> str:
        text = match.group(3)
        if "\\" not in text and "$" not in text:
            return match.group(0)
        plain = latex_to_plain(text)
        kwargs = match.group(4)
        return f"Text({plain!r}{kwargs})"

    return _TEXT_CALL_RE.sub(_repl, code)


def strip_latex_mobjects(code: str) -> str:
    """Replace MathTex/Tex with Text so scenes render without a LaTeX install."""

    def _repl(match: re.Match[str]) -> str:
        tex = match.group(3)
        plain = latex_to_plain(tex)
        kwargs = match.group(4).strip()
        if not kwargs:
            kwargs = ', color="#e0e6f0"'
        elif "color=" not in kwargs:
            kwargs = f', color="#e0e6f0"{kwargs}'
        return f'Text({plain!r}{kwargs})'

    code = _TEX_CALL_RE.sub(_repl, code)
    return strip_latex_in_text_literals(code)
