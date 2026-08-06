# Shelf Life AI Usage Log

## Purpose

This project-wide log records meaningful uses of generative AI during the Shelf Life
project. It documents what the team asked AI to help with, what AI contributed, what
people checked or changed, and how the result was verified.

The entries below are based on `prompting-notes.md`, `M1-REFLECTION.md`, the current
repository, and retained evidence from the August 5 review-feedback work. Older prompt
wording is summarized rather than presented as a verbatim transcript. Unknown dates or
team-member names are marked for the team to complete instead of being guessed.

## How to Maintain This Log

Add one row for each meaningful AI-assisted task. Do not log routine autocomplete.
Record failed or rejected AI output as well as accepted output. Never claim that a
test, review, deployment, or human decision occurred unless the team verified it.

| Date / session | Team member | AI tool | Task and prompt/context summary | AI contribution | Human judgment and changes | Verification / evidence | Status |
|---|---|---|---|---|---|---|---|
| M1 - exact date to add | Name to add | ChatGPT and Claude Code | Clarify the personal reading tracker requirements; define MoSCoW scope, user stories, acceptance criteria, Book/Review data, and API endpoints. Explicitly exclude authentication and chat. | Proposed requirements, data-model ideas, endpoint structure, and testable acceptance criteria. | The team reduced the scope to a small reading tracker and retained responsibility for final requirements and design choices. | `DESIGN.md`, `CLAUDE.md`, `prompting-notes.md`, and `M1-REFLECTION.md`. | Historical entry reconstructed from retained project documents. |
| M1 - exact date to add | Name to add | ChatGPT and Claude Code | Help implement a keyless Open Library lookup behind the existing `lookup(title)` boundary, preserve the offline seed fallback, define timeout/failure behavior, and mock network calls in tests. | Suggested the normalized `BookDetails` boundary, external lookup behavior, fallback handling, and test cases. | The team required deterministic offline fallback, prevented tests from reaching the real service, and distinguished direct HTTP integration from the later MCP requirement. | `app/openlibrary.py`, `app/lookup.py`, `seed/books.json`, `tests/test_openlibrary.py`, and `tests/test_lookup.py`. | Historical entry reconstructed from retained project documents. |
| M1 - exact date to add | Name to add | ChatGPT | Diagnose Windows pytest `PermissionError` without changing application code. | Identified the temporary-directory environment issue and suggested a project-local `--basetemp` command. | The team chose the environment-level workaround rather than an unrelated code change and reran the tests. | Test command documented in `README.md`; M1 snapshot recorded 38 passing tests in `M1-REFLECTION.md`. | Historical entry reconstructed from retained project documents. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) | Read the course requirements and organize the evidence needed for cross-team review: manual-first review, AI comparison, structured feedback, action on received feedback, and final deployment verification. | Summarized requirements, separated evidence collection from implementation, and proposed an ordered task list. | The user clarified team responsibilities and supplied the received feedback and screenshots. No code was changed during the evidence-only phase. | `studio-10-slides.pdf` in the course-material folder and the archived feedback screenshot. | Completed; outgoing review evidence is still waiting on the responsible teammate. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) | Fix the received feedback that some books appeared to have blank covers. Work locally only; do not commit, push, or deploy. | Added an explicit `NO COVER` SVG, centralized front-end fallback logic, added a static-asset test, and added cache-versioning for `app.js`. | The user rejected the first result because blank covers still appeared. Browser inspection then showed that Open Library returned successful 1x1 transparent images. The implementation was revised to detect those images by natural dimensions and replace them with the fallback. | `static/app.js`, `static/cover-placeholder.svg`, `templates/index.html`, `tests/test_books.py`; 98 tests passed; user-provided before/after screenshots show the visible change. | Completed and accepted locally; not committed, pushed, or deployed. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) | Update README without committing, pushing, or deploying; first verify the real MCP implementation and tests. | Inspected the MCP server, client, environment configuration, routes, and tests; corrected the stale statement that MCP was unfinished; documented MCP startup, default backend, structure, endpoints, deployment URL, and M3 remaining work. | The user explicitly authorized the README edit. Only behavior supported by existing code and tests was documented. | `README.md`, `mcp_server/server.py`, `app/mcp_client.py`, `tests/test_mcp_server.py`, and `tests/test_mcp_client.py`; full suite: 98 passed. | Completed locally; not committed, pushed, or deployed. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) | Create the project-wide AI usage log from retained evidence without inventing missing team history. | Produced this structured log and identified incomplete names, dates, and unlogged team activity. | The user authorized creation. Historical entries are labeled as reconstructed, and unsupported M2/M3 history is not claimed. | This file plus `prompting-notes.md` and `M1-REFLECTION.md`. | Initial log created; team review still required. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) and Semgrep OSS 1.172.0 | Check whether the required security scan evidence exists; if absent, run Semgrep without changing application code. | Confirmed no prior report was present, installed Semgrep in a temporary tool environment, ran the automatic community rules, parsed the JSON result, and drafted the human-readable triage report. | Sam Zhu authorized the next task and the tool download. The result was checked for findings, scan errors, scope, and limitations; zero findings was not treated as proof of complete security. | `semgrep-report.json` and `SEMGREP-REPORT.md`: 493 rules, 54 project files, 0 findings, 0 errors. | Completed locally; no source fix, commit, push, or deployment performed. |
| 2026-08-05, Studio 10 follow-up | Sam Zhu | Codex (OpenAI) | Create a GitHub Actions CI workflow without committing, pushing, or deploying. Use the course Studio 9 pattern and the project's documented test command. | Added a least-privilege workflow for pushes and pull requests to `main`, plus manual dispatch; configured Python 3.11, pip dependency caching, a 15-minute timeout, concurrency cancellation, and the full pytest command. | Sam Zhu authorized the workflow. The configuration was kept aligned with `render.yaml`, `requirements.txt`, and the local test command rather than adding unrelated build steps. | `.github/workflows/test.yml`; YAML structure validated with all three triggers and four steps; local suite: 98 passed. | Created and locally validated; not committed, pushed, or executed on GitHub. |

## Team Follow-up Required

- Replace every remaining `Name to add` placeholder with the correct person.
- Add exact dates for the reconstructed M1 entries if chat history, commits, or notes
  are available.
- Add meaningful AI-assisted M2 work not captured in the retained documents,
  especially MCP implementation, CI/deployment work, and any custom
  Skill work. Include the human review and test evidence for each entry.
- Add the completed Studio 10 outgoing review entry when the responsible teammate
  provides the manual findings, AI findings, comparison table, and five structured
  feedback items.
- Add a production verification entry only after the latest changes are deployed and
  tested at the public URL.

## Current Disclosure Summary

The retained evidence shows use of ChatGPT, Claude Code, and Codex for requirements,
planning, implementation support, debugging, testing guidance, documentation, and
review-feedback remediation. Human decisions included controlling scope, rejecting an
incomplete first cover fix, requiring a root-cause investigation, checking screenshots,
and running the complete automated test suite. The current local suite result is 98
passed with one third-party deprecation warning.
