"""Stamp the content hash of js/mock.js into index.html (MOCK_VERSION) so GitHub Pages caching
never serves an old module with a new page. Run after editing js/mock.js.
    python3 tools/stamp_version.py
"""
import hashlib, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
h = hashlib.sha1((ROOT / "js/mock.js").read_bytes()).hexdigest()[:10]
p = ROOT / "index.html"
s = p.read_text(encoding="utf-8")
s2 = re.sub(r'const MOCK_VERSION = "[^"]*";', f'const MOCK_VERSION = "{h}";', s)
assert s2 != s or f'"{h}"' in s, "MOCK_VERSION marker not found"
p.write_text(s2, encoding="utf-8", newline="")
print("MOCK_VERSION", h)
