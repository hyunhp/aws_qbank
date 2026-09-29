---
description: Generate N new questions for an exam with parallel writers, review, then ingest serially
argument-hint: <EXAM> <N>
---
Goal: add $ARGUMENTS (exam code and count) questions to the bank.

1. Run `python3 tools/qgen/qgen.py plan` for the exam and split the needed questions by
   domain into chunks of about 20. Pick the next free batch numbers under
   tools/qgen/batches/<EXAM>/.
2. In ONE message, launch one `question-writer` subagent per chunk in parallel, each with its
   exam, domain/task ids, count and batch path.
3. When they finish, bring each batch file into this checkout, then launch `batch-reviewer`
   subagents in parallel (one per batch).
4. Ingest the reviewed batches ONE AT A TIME: `python3 tools/qgen/qgen.py ingest <batch>`.
5. Run the full test command from CLAUDE.md. If all pass, commit with a message listing the
   batches and new counts. Do not push unless asked.
