# TODO

State on 2026-09-30: every question in all 13 exams (4,502 incl. shared) has a detailed explanation; 64 flawed
questions were fixed in place (`tools/qgen/batches/*/f0*.txt`). Done the same day: bookmarks load only the exams
holding bookmarked ids (id ranges in `exams-index.json`), explanations split into `data/explanations/<EXAM>.json`
(exam files ~0.33 MB, explanations fetched on first reveal), `qgen check` refuses old blocks superseded by an
`I:` rewrite, `.claude/agents` now has explanation-writer, batch-reviewer, question-writer and fix-writer,
`.explain{contain:layout style}` cut the reveal layout cost by about a quarter.

## 1. Keep availability notes current
Explanations mention services closed to new customers (verified 2026-09-30 against the AWS "service availability
change" pages): CloudTrail Lake (2026-05-31), Audit Manager (2026-04-30), Incident Manager / Migration Hub /
Application Discovery Service / Snowball Edge (2025-11-07), Glacier vaults (2025-12-15), CodeGuru Security
(ended 2025-11-20), S3 Select (2024-07), Timestream for LiveAnalytics (2025-06-20), QLDB (ended 2025-07-31).
Also moved to maintenance on 2026-04-30 (closed to new customers): App Runner, ARC readiness check, Glue Ray jobs,
IoT FleetWise, Comprehend topic modeling / event detection / prompt safety, Rekognition streaming events and batch
image content moderation, SNS Message Data Protection. Sunset: RDS Custom for Oracle, WorkMail, WorkSpaces Thin
Client, AWS Service Management Connector (mention removed from Q001823). App Runner and ARC readiness check already
carry an availability note in their explanations. Re-check every few months; the original Security Hub is now
"Security Hub CSPM" (don't state a rename date).

## 2. Reveal frame cost (no action needed)
Profiling (4x CPU) shows the ~100 ms frame is one ~45-70 ms Layout on any reveal, independent of list size and of
diagrams (`injectStyles` is not the cause); it is the explanation text layout itself. `.explain{contain:layout style}`
already cut it ~25 %. `loading_perf_test.py` "no long frames on reveal" (100 ms limit) can still flake when the
company network needs re-authentication.

## Tooling notes
- `tools/diagrams/build_assets.py` reuses icons already in `assets/aws-icons.svg` when the icon pack is missing, so
  it works on any PC; only brand-new icons need the pack (path as first argument).
- Windows cp949: file I/O in tools now passes `encoding="utf-8"`; `qgen.py` and `diagrams/check.py` reconfigure stdout.
  If a new script prints or reads non-ASCII, do the same.
