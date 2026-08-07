# AI Usage Log

**Team:** Shelf Life (ELEC-A-Gourp-2)
**Milestone:** M3
**Date:** 2026-08-06

## Tools Used

| Tool | Purpose | Approximate Usage |
|------|---------|-------------------|
| Codex (OpenAI) | Project implementation, review-feedback fixes, testing, documentation | High |
| Claude Code | Teammate implementation and project-specific skills | Medium |
| ChatGPT | Early requirements and implementation support | Low |

## Estimated AI Contribution

- Estimated % of code AI-generated: ~65% (team to adjust)
- Estimated % of code human-written: ~15%
- Estimated % of code AI-generated then modified: ~20%

## Key Interactions

### Interaction 1: Author search and paged results

**Tool:** Codex (OpenAI), with teammate implementation

**What I asked for:**
Add a Title/Author selector and paged search results so an author search returns every
match, and confirm additions by ISBN instead of re-running the search.

**What it produced:**
The selector UI, paged results (ten per page), ISBN confirmation through
`get_book_details`, and the associated tests.

**What I changed and why:**
Verified in the browser (J. K. Rowling returns 431 results across 44 pages, and a book
from page seven can be added), then merged via PRs #12 and #14.

**Quality assessment:** Good

### Interaction 2: Missing-cover fallback fix

**Tool:** Codex (OpenAI)

**What I asked for:**
Fix books that showed a blank white box instead of a cover.

**What it produced:**
A first version that looked correct but still showed blank covers, because Open Library
returns 1x1 transparent images with HTTP 200 instead of an error.

**What I changed and why:**
The user rejected the first version after manual testing. We inspected the real API
response and reworked the fallback to detect 1x1 images by natural size and replace
them with the `NO COVER` placeholder, with a regression test. Merged via PR #14.

**Quality assessment:** Needed significant fixes

### Interaction 3: Review-feedback remediation (card error handling, MCP input normalisation, MCP exception handling, field-list refactor, review reply)

**Tool:** Codex (OpenAI)

**What I asked for:**
Fix the five review findings recorded in `REVIEW-RESPONSE.md`.

**What it produced:**
The `cardAction` helper with visible error hints, `_normalise_query`, a broad exception
fallback with server-side logging, a single `_BOOK_FIELDS` spec, and the written reply
to the seed-id review comment.

**What I changed and why:**
Each change followed a test-first cycle (write a failing test, watch it fail, then
implement). The user reviewed each plan before implementation. The suite grew 163 to
173 passing tests without regressions, and the work merged via PRs #15 to #19.

**Quality assessment:** Good

### Interaction 4: Advanced pattern -- project-specific Claude Code skills

**Tool:** Claude Code

**What I asked for:**
Create reusable project-specific skills for the team's development workflow.

**What it produced:**
Three skills under `.claude/skills/` (`add-endpoint`, `review`, `test`) that encode the
project's conventions: parameterised SQL only, user text rendered with `textContent`,
and a standard review output format.

**What I changed and why:**
Details of the human review and verification are to be confirmed by the responsible
teammate (Phoebe). The skill files are committed via PR #9.

**Quality assessment:** To be confirmed by the team

### Interaction 5: MCP server implementation

**Tool:** ChatGPT and Claude Code

**What I asked for:**
Implement the course-required MCP server exposing `search_book`, `search_by_author`,
and `get_book_details`, plus the application-side adapter.

**What it produced:**
`mcp_server/server.py` (FastMCP tools) and `app/mcp_client.py`. The tools are exercised
by the test suite and by the deployed application through FastMCP's in-memory
transport.

**What I changed and why:**
Details of the human review and verification are to be confirmed by the responsible
teammate. Merged via PR #8.

**Quality assessment:** To be confirmed by the team

### Interaction 6: Deployment setup (Render + Turso)

**Tool:** Claude Code (teammate)

**What I asked for:**
Set up deployment so the application is live on a public URL.

**What it produced:**
The Render Blueprint (`render.yaml`) with `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`,
and Turso/libSQL support in `app/db.py`. Merged via PR #10.

**What I changed and why:**
Deployment requires a manual Render deploy by the account holder; the final deploy of
the latest `main` is still pending, and the production verification entry will be
added once it is live.

**Quality assessment:** To be confirmed by the team

## Context Engineering

**CLAUDE.md effectiveness:**
CLAUDE.md gave AI tools the project's hard rules (parameterised SQL only, `textContent`
for user text, a stable `lookup(title)` signature, current-state description), which
made onboarding noticeably faster and reduced off-project suggestions. It was worth
keeping current.

**Design doc as context:**
DESIGN.md sections 7.6 and 7.7 recorded why the Title/Author selector exists and how
paging and ISBN confirmation work. Providing it stopped AI from re-introducing the
inferred-mode search that had already failed twice.

## What Worked Well

1. Author search and paging were delivered quickly with tests and verified in the browser.
2. Test-first cycles on the review fixes kept every change safe; the suite grew from 163 to 173 passing tests with no regressions.
3. Project-specific Claude Code skills captured team conventions for endpoint, review, and test work.

## What Didn't Work Well

1. The first cover fix looked correct but was broken (1x1 transparent images); confidence did not equal correctness, and manual testing was required to catch it.
2. The MCP tools initially leaked internal exception text to AI clients; a human code review found the defect.
3. Deployment depended on one teammate with Render access, so shipping was blocked when that person was unavailable.

## Lessons Learned

AI output must be verified against real behavior, not against whether it looks right:
the 1x1 transparent-image case and the vacuous-test suite are the two clearest examples
from this term. Giving AI tools good, current context (CLAUDE.md, DESIGN.md) and
planning each task before implementing reduced wasted work substantially. Finally,
deployment and other single-owner steps should be set up early and shared, because
they became bottlenecks at the end.