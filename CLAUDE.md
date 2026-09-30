# aws_qbank — working notes for Claude Code

Static GitHub Pages site (https://hyunhp.github.io/aws_qbank/) with original AWS certification
practice questions. No build step: `index.html`, `js/*.js`, `data/*.json`, `diagrams/*.json`.
Explanations live apart from the questions: `data/<EXAM>.json` has none, `data/explanations/<EXAM>.json` is `{id: text}`
(qgen `load_exam`/`save_exam` merge and split them; the site fetches them on first reveal).
Open work items are in `TODO.md` — read it at the start of a session.

## Hard rules
- Never create files or folders the site reads whose names start with `_` (GitHub Pages/Jekyll
  drops them; `.nojekyll` is a safety net, not a license). Mock exam broke on 2026-09-26 because of this.
- Questions are added or changed only through batch files in `tools/qgen/batches/<EXAM>/bNN.txt`
  and `python3 tools/qgen/qgen.py ingest <file>`. Never hand-edit `data/<EXAM>.json`.
- `ingest` assigns question ids and rewrites shared data files: run it **one batch at a time,
  never in parallel**. Parallel work = writing batch files only.
- After editing `js/mock.js` run `python3 tools/stamp_version.py`.
- Never paste tokens into files or chat; push with the local git credential (gh auth / SSH).

## Batch format (see tools/qgen/qgen.py docstring)
```
@ EXAM Dx Tx.x basic|applied|advanced use-case|tradeoff|comparison|troubleshooting [+OTHER:Dy]
S: stem (multi-answer stems end with "(Select TWO)")
A:..D: (E: for multi)   K: A  or  K: A,C
W: why correct   X: B=... | C=... | D=...   T: takeaway   V: services (optional)
G: background (detailed explanation; required style for all new and rewritten explanations)
```
Detailed explanations (see `tools/qgen/batches/ANS-C01/e01.txt` for the reference style):
- `G:` teaches the concept a learner needs first: `## Heading` lines, short paragraphs, `- ` bullets,
  `code` for CIDRs/ARNs/commands, a concrete example. `G:`, `W:`, `X:` may span lines.
- `W:` and each `X:` entry start with a short option name then a colon (`B=VPC peering: ...`) and give
  the real reason it works or fails; one `X:` entry per line. `T:` is the one-sentence key idea.
- Multi-answer questions: `W:` has one entry per correct option, one per line, like `X:`
  (`W: A=Name: why` / `D=Name: why`).
- Never refer to options by letter in the text ("option B"): ingest reorders choices.
- Rewrite an existing question's explanation with an explain-only batch
  `tools/qgen/batches/<EXAM>/eNN.txt` using `@ Q001592 explain` blocks (G/W/X/T; X letters are the
  published letters). Ingest never replaces a detailed explanation with a short one.
Quality gates enforced by `qgen check`: schema, near-duplicates, length bias (correct answer
must not be clearly the longest option too often; write distractors as long and specific as the
answer), stem length. `python3 tools/qgen/length_bias.py <batch>` lists the questions to fix.

## Commands
- Plan gaps: `python3 tools/qgen/qgen.py plan <EXAM>`; status: `python3 tools/qgen/qgen.py report`
- Validate: `python3 tools/qgen/qgen.py check <batch>`; write: `... ingest <batch>`
- Tests (all must pass before commit):
  `node tools/mock_unit_test.mjs && python3 tools/mock_e2e_test.py && python3 tools/mock_link_test.py && python3 tools/bookmark_backup_test.py && python3 tools/loading_perf_test.py && python3 tools/diagrams/scroll_ui_test.py && python3 tools/diagrams/check.py`
