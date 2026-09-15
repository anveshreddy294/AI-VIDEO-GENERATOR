from pathlib import Path
p = Path("frontend/src/components/VideoPlayer.jsx")
s = p.read_text(encoding="utf-8")
a = s.index("  function drawCanvas(")
b = s.index("  const showFallbackCanvas", a)
function = s[a:b]
s = s[:a] + s[b:]
i = s.index("export default")
s = s[:i] + function + "\n" + s[i:]
p.write_text(s, encoding="utf-8")
