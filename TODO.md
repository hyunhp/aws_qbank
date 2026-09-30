# TODO

State on 2026-09-30: every question in all 13 exams (4,502 incl. shared) has a detailed explanation; 64 flawed
questions were fixed in place (`tools/qgen/batches/*/f0*.txt`). Open items, most useful first.

## 1. Bookmarks view loads every exam file (~12 MB)
`#bookmarks` fetches all `data/<EXAM>.json` to find the bookmarked ids (index.html, bookmark rendering around the
`cache` lookup). The detailed explanations roughly doubled the files (SAA-C03 0.58 MB -> 1.03 MB), so a slow phone
waits several seconds.
- Fix idea: have `tools/build_data_index.py` add an id -> exam map (or per-exam id ranges) to `data/exams-index.json`
  and load only the exams that contain bookmarked ids.
- Tests to update: `tools/loading_perf_test.py` ("bookmarks view loads all exams" currently asserts all files are
  requested) and `tools/bookmark_backup_test.py`.

## 2. Exam files are heavy because explanations are inline
Each exam file now carries all explanations (~1 MB). Consider splitting explanations into
`data/explanations/<EXAM>.json` (no leading `_`!) loaded on first reveal, or per-chunk files. Keep the mock exam review
(`js/mock.js`, uses `qb.explainHtml`) working; run `tools/stamp_version.py` after editing mock.js.

## 3. First diagram reveal has a ~130 ms long task (4x CPU)
`warmDiagrams()` in index.html preloads `js/diagram.js` and the sprite but not the stylesheet; the first
`renderDiagram()` calls `injectStyles()`, which restyles the whole page. Tried adding `export function warm(url)
{ injectStyles(); return loadSprite(url); }` and calling it from the warm-up; it did not clearly fix the long frame,
so profile further. Note `tools/diagrams/build_assets.py` (rebuilds the diagram manifest version after editing
diagram.js) fails on this Windows PC: the source icon set is missing ("missing icons: ..."), so diagram.js cannot be
re-versioned here.
`loading_perf_test.py` "no long frames on reveal" is borderline (100 ms limit, 100-230 ms seen under load or when the
company network needs re-authentication).

## 4. Old question batches can undo the fixes
`tools/qgen/ingested.json` still maps the original `b*.txt` blocks of 7 fixed questions to the same ids. Re-ingesting
those old batch files would overwrite the fixes. Either delete those blocks from the old batches or make `qgen ingest`
refuse a block whose id is pinned by a newer `I:` block.

## 5. Move the working instructions into the repo
The explanation/fix writer and reviewer prompts used for this pass lived in a temp folder. Fold the useful parts into
`.claude/agents/explanation-writer.md`, `.claude/agents/batch-reviewer.md` and a new fix-writer agent (full block +
`I: <id>`, header copied from examCodes[0] with `+OTHER:Dy` from `data/exam-domains.json`).

## 6. Keep availability notes current
Explanations mention services closed to new customers (as verified 2026-09): CloudTrail Lake (2026-05-31), Audit
Manager (2026-04-30), Incident Manager / Migration Hub / Application Discovery Service / Snowball Edge (2025-11-07),
Glacier vaults (2025-12-15), CodeGuru Security (ended 2025-11-20), S3 Select (2024-07), Timestream for LiveAnalytics
(2025-06-20), QLDB (ended 2025-07-31). Re-check periodically; the original Security Hub is now "Security Hub CSPM"
(don't state a rename date).
