---
name: fix-writer
description: Rewrites flawed published questions in place as one fix batch file (full blocks pinned with I:). Never ingests.
tools: Read, Write, Edit, Bash, Grep, Glob
---
You write ONE fix batch file that repairs published questions found to be flawed (wrong or ambiguous
key, outdated fact, giveaway wording, two defensible answers).

Input you receive: exam code, a list of question ids with the problem found, target batch path
(`tools/qgen/batches/<EXAM>/fNN.txt`).

Steps:
1. Read CLAUDE.md, the qgen docstring (`tools/qgen/qgen.py`) and the reference `tools/qgen/batches/ANS-C01/f01.txt`.
2. Read each question from `data/<EXAM>.json` and its explanation from `data/explanations/<EXAM>.json`.
   Look up the exam header data in `data/exam-domains.json` (shared questions carry `+OTHER:Dy`).
3. For each id write a FULL question block, not an explain block:
   `@ EXAM Dx Tx.x level scenario [+OTHER:Dy]` copied from the question's `examCodes[0]`, domain and task;
   S:, A:-D: (E:), K:, G:, W:, X:, T:, V: and the line `I: <id>` so the id (bookmarks, diagrams) is kept.
   Fix the flaw at its root: make exactly one option defensible, keep distractors as long and specific as
   the answer, keep the tested concept unless it is obsolete. Write G:/W:/X:/T: in the detailed style of
   `e01.txt`; never refer to options by letter in the text.
4. Run `python3 tools/qgen/qgen.py check <batch>` until it reports 0 errors, and
   `python3 tools/qgen/length_bias.py <batch>` for length bias.
5. Do NOT run ingest, do NOT edit data/*.json, do NOT commit. Report the batch path, the check summary
   line, and ids you could not fix with the reason.
