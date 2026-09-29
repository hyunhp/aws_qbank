---
description: Upgrade an exam's explanations to the detailed style with parallel writers, review, then ingest serially
argument-hint: <EXAM>
---
Goal: every question of $ARGUMENTS gets a detailed explanation (starts with "## ").

1. List the exam's question ids whose explanation does not start with "## " (python one-liner over
   data/<EXAM>.json). Skip ids that already have one in another exam (shared questions).
2. Split them into chunks of about 25 and pick free batch names tools/qgen/batches/<EXAM>/eNN.txt.
3. In ONE message, launch one `explanation-writer` subagent per chunk (at most 8 at a time).
4. Launch `batch-reviewer` subagents in parallel, one per batch.
5. Ingest the reviewed batches ONE AT A TIME with `python3 tools/qgen/qgen.py ingest <batch>`.
6. Run the full test command from CLAUDE.md; commit when all pass. Do not push unless asked.
