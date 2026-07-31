---
name: review
description: Review the current code changes against this team's standard — correctness, security, performance, readability, tests, edge cases.
---

Review the staged changes (run `git diff --staged`), or the changes described
in $ARGUMENTS if given. If nothing is staged, review the unstaged diff
(`git diff`).

Criteria:
1. Correctness: logic errors? Does it do what it claims?
2. Security: hardcoded secrets, SQL injection (this project requires
   parameterised SQL — flag any string-built query), XSS (user text must be
   rendered with `textContent`, never `innerHTML`).
3. Performance: N+1 queries, work repeated on a hot path?
4. Readability: clear names, right layer (routers do HTTP, services hold rules,
   db.py does data access)?
5. Tests: do they test behaviour, not implementation? Is there coverage for the
   change, including an error case?
6. Edge cases: empty, null, large input, concurrent access?

Also check this project's rules from CLAUDE.md: a lookup failure must never fail
an add; the `lookup(title)` signature must stay stable.

Format the output as:
- **Must fix** (with file:line)
- **Should fix**
- **Nit**
- **Praise** (always include at least one)

Usage: `/review` or `/review the new search endpoint`
