# Prompting Notes

## Purpose and Tools

These notes summarize how our team used AI during the requirements, design, and M1
implementation of Shelf Life.

We used:

- **ChatGPT** for requirements clarification, planning, documentation, debugging
  support, and step-by-step guidance.
- **Claude Code** for repository-aware implementation and testing support.

The team did not retain every original prompt. The examples below are representative
reconstructions based on tasks we actually performed, not verbatim chat logs. AI
assisted our work, but the team remained responsible for scope, review, testing, and
the final result.

## Our Prompting Approach

The most reliable workflow was:

1. Provide the current project context.
2. Ask the AI to inspect existing code or documents before editing.
3. Give it one small, clearly bounded task.
4. Specify inputs, outputs, validation, and failure behavior.
5. Request tests or verification steps.
6. Review the changed filenames and diff before accepting the result.
7. Run automated tests and manually check the main user journey.

This worked better than asking the AI to build the entire application in one prompt.

## Representative Examples

### 1. Requirements

**Too broad**

> Build a personal reading tracker.

**Improved**

> Write user stories and acceptance criteria for adding a book by title, assigning it
> to reading, finished, or wishlist, moving and deleting it, and adding a rating from
> 1 to 5 with optional review text. Separate Must Have, Should Have, Could Have, and
> Won't Have requirements. Do not add authentication or chat.

The improved prompt defined the audience, supported actions, validation rules, and
out-of-scope features.

### 2. Open Library lookup

**Too broad**

> Connect the app to Open Library.

**Improved**

> Inspect the existing `lookup(title)` boundary before editing. Add a keyless Open
> Library HTTP client that normalizes results into `BookDetails`. Preserve
> `seed/books.json` as the fallback. If every source fails, save the title with
> `details_pending = true`. Use a timeout and mock all network responses in tests.
> Do not describe this direct HTTP client as the course-required MCP server.

The improved prompt protected the existing architecture and made failure behavior
testable.

### 3. Debugging and verification

**Too broad**

> Pytest is broken on Windows. Fix it.

**Improved**

> The tests report `PermissionError: [WinError 5]` for the system pytest temporary
> directory. Do not modify application code yet. Explain the likely environment cause
> and provide a command that uses a project-local pytest temporary directory.

This avoided unrelated code changes and led to the project-local `--basetemp` solution.

## What Worked

- **Small tasks:** one endpoint, validation rule, test group, or document at a time was
  easier to review and reverse.
- **Project context:** `CLAUDE.md` and `DESIGN.md` reduced invented frameworks,
  endpoints, and file locations.
- **Acceptance criteria:** rules such as ratings being limited to 1-5 and reviews being
  deleted with their book translated directly into tests.
- **Explicit failure behavior:** defining timeouts, empty results, invalid input, and
  seed fallback produced a more reliable design.
- **Human verification:** we ran automated tests and manually added *The Hobbit*,
  checked its metadata, added a rating, moved it to Finished, refreshed the page, and
  confirmed persistence.

## What Did Not Work

- Broad prompts left too much room for unstated assumptions.
- An older downloaded ZIP sometimes provided stale context compared with GitHub.
- A direct Open Library HTTP client could be mistaken for completion of the required
  MCP server unless the distinction was stated explicitly.
- Assuming that every team member could access Claude Code blocked the planned context
  experiment for one member.
- Correct content could still be applied to the wrong file, so checking
  **Files changed** before merging became part of our process.

We did not identify a clear case of incorrect AI-generated application code that
required manual repair during M1. However, human judgment was still needed to confirm
the MoSCoW scope, resolve local environment problems, distinguish HTTP from MCP, review
documentation against the repository, and verify the application.

## Rules for M2

1. Pull or download the latest repository before starting.
2. Work on a feature branch and request teammate review.
3. Give the AI the current project context and ask it to inspect before editing.
4. Keep each prompt focused on one bounded change.
5. State validation, timeout, error, fallback, security, and privacy requirements.
6. Mock external services in automated tests.
7. Review every filename and diff before merging.
8. Run the latest full test suite and record the real result.
9. Run and manually review the required security scan.
10. Do not describe direct HTTP functions as MCP tools until an MCP server exists.

The separate with-and-without-`CLAUDE.md` context experiment is still pending. Its
actual token and cost results will be recorded in `context-experiment.md`; these notes
do not substitute for that experiment.
