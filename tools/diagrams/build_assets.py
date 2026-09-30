"""Build assets/aws-icons.svg (sprite of icons used by diagrams) and diagrams/index.json (manifest).

Run after adding/editing any diagrams/<QID>.json or js/diagram.js:
    python3 tools/diagrams/build_assets.py [path/to/icon-pack/svg]

Icon source: official AWS Architecture Icons (svg/ folder of github.com/harmalh/aws-mermaid-icons,
which repackages the AWS asset package). Only icons referenced by a spec are copied into the sprite.
Without the icon pack (e.g. on another PC) icons already present in assets/aws-icons.svg are reused, so
edits to js/diagram.js or the specs can still be re-versioned; only brand-new icons need the pack.
The manifest `version` is a content hash of the module, sprite and specs; index.html appends it as
?v= to every diagram request so GitHub Pages caching never mixes old and new files.
"""
import hashlib, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ICON_DIR = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/diag/aws-mermaid-icons/svg")
SPECS = ROOT / "diagrams"
SPRITE = ROOT / "assets/aws-icons.svg"
MODULE = ROOT / "js/diagram.js"
OLD = {}


def old_symbols():
    """<symbol> elements of the current sprite by icon name (fallback when the icon pack is absent)."""
    if not SPRITE.exists():
        return {}
    text = SPRITE.read_text(encoding="utf-8")
    return {m.group(1): m.group(0) for m in re.finditer(r'<symbol id="i-([^"]+)".*?</symbol>', text, re.S)}


def symbol(name):
    if not (ICON_DIR / f"{name}.svg").exists():
        return OLD[name]
    raw = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8")
    vb = re.search(r'viewBox="([^"]+)"', raw).group(1)
    inner = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.S).group(1)
    inner = re.sub(r"<title>.*?</title>", "", inner, flags=re.S)
    inner = re.sub(r"<desc>.*?</desc>", "", inner, flags=re.S)
    # keep internal references working but make ids unique per icon
    ids = set(re.findall(r'\sid="([^"]+)"', inner))
    referenced = {i for i in ids if f"#{i}" in inner}
    for i in referenced:
        inner = inner.replace(f'id="{i}"', f'id="i-{name}--{i}"').replace(f"#{i})", f"#i-{name}--{i})").replace(f'"#{i}"', f'"#i-{name}--{i}"')
    inner = re.sub(r'\sid="(?!i-)[^"]*"', "", inner)
    inner = re.sub(r"\s+", " ", inner).strip()
    return f'<symbol id="i-{name}" viewBox="{vb}">{inner}</symbol>'


def main():
    specs = sorted(p for p in SPECS.glob("Q*.json"))
    used, ids = set(), []
    for p in specs:
        spec = json.loads(p.read_text(encoding="utf-8"))
        assert spec["id"] == p.stem, f"{p.name}: id mismatch"
        ids.append(spec["id"])
        used |= {n["icon"] for n in spec.get("nodes", [])}
    OLD.update(old_symbols())
    missing = [u for u in used if not (ICON_DIR / f"{u}.svg").exists() and u not in OLD]
    if missing:
        sys.exit(f"missing icons: {missing}")
    SPRITE.parent.mkdir(exist_ok=True)
    SPRITE.write_text('<svg xmlns="http://www.w3.org/2000/svg">' + "".join(symbol(u) for u in sorted(used)) + "</svg>\n", encoding="utf-8", newline="\n")

    h = hashlib.sha1()
    for p in [MODULE, SPRITE, *specs]:
        h.update(p.read_bytes())
    manifest = {"version": h.hexdigest()[:10], "ids": ids}
    (SPECS / "index.json").write_text(json.dumps(manifest, indent=0) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(ids)} diagrams, {len(used)} icons, sprite {SPRITE.stat().st_size // 1024} KB, version {manifest['version']}")


if __name__ == "__main__":
    main()
