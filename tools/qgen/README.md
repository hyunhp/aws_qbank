# Question pool expansion pipeline

Target: 5 full exams per certification (65-question exams 325, 75-question exams 375, AIB-C01 425).

```bash
python3 tools/qgen/qgen.py report                 # every exam: pool vs target, multi-answer %, answer positions, longest-correct %
python3 tools/qgen/qgen.py plan AIB-C01           # gaps per domain and task statement
python3 tools/qgen/qgen.py check <batch.txt>      # validate only
python3 tools/qgen/qgen.py ingest <batch.txt>     # validate, then write data/*.json
```

Batches live in `tools/qgen/batches/<EXAM>/bNN.txt` and are the source of truth for added questions
(format in the docstring of `qgen.py`). `tools/qgen/ingested.json` maps each block to its question id, so
re-ingesting an edited batch updates questions in place and keeps their published choice order.
Use `I: Qxxxxxx` inside a block to keep the id when rewriting its stem.

Checks that reject a batch:
- schema: header fields, 4 choices (single answer) or 5 (multi-answer, stem ends with "(Select TWO)"),
  a reason for every wrong choice, no duplicate choices
- near-duplicates of existing questions in the same exams (cosine ≥ 0.72 on stem + correct answer; 0.55+ is a warning)
- length bias: correct answer much longer than every distractor in >25% of questions, or simply the
  longest option more often than chance allows

On ingest the correct answer is placed in the least-used position for that exam, the explanation is
assembled in the site's three-part format, shared questions (`+SOA-C03:D2`) are written to every exam
file and to `data/_exam_domains.json`.

After ingesting: run `node tools/mock_unit_test.mjs`, `python3 tools/mock_e2e_test.py`, and for
structural questions consider a diagram (`tools/diagrams/`).
