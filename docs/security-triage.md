# M2 Security Triage — Shelf Life

**Date:** 2026-08-11 (final pass on merged `main`; original scan 2026-08-05, see `SEMGREP-REPORT.md`)
**Semgrep version:** 1.172.0
**Command note:** Semgrep pins `mcp==1.23.3`, which conflicts with `fastmcp` (needs `mcp>=1.24`), so scans run from an isolated tool environment. The project venv keeps only application dependencies.

## Scans run (2026-08-11, on the current repository)

| # | Ruleset | Targets | Findings |
|---|---------|---------|----------|
| 1 | `semgrep --config auto` | whole repository (493 rules, 69 files) | 2 initially, both fixed, 0 after |
| 2 | `semgrep --config auto` | `mcp_server/` only (MCP server scanned separately) | 0 |
| 3 | `semgrep --config p/security-audit` | `app/`, `mcp_server/` | 0 |
| 4 | `semgrep --config p/owasp-top-ten` | `app/`, `mcp_server/`, `templates/`, `static/` | 0 |

All scans completed with a 100% parse rate and exit code 0. The earlier 2026-08-05 pass (`SEMGREP-REPORT.md`, `semgrep-report.json`) covered `--config auto` only; this pass adds the MCP-only, security-audit, and OWASP Top 10 rulesets plus the manual review below.

## Triage table

| Finding | Severity | Classification | Rationale |
|---------|----------|----------------|-----------|
| Mutable GitHub Actions tags (`actions/checkout@v4`, `actions/setup-python@v5`) in `.github/workflows/test.yml` | Low (Semgrep WARNING) | True positive | FIXED — pinned to the full commit SHAs `11d5960a326750d5838078e36cf38b85af677262` (checkout v4) and `a26af69be951a213d495a4c3e4e4022e16d87065` (setup-python v5) so action owners cannot silently repoint the tags. Diff below. |
| User search queries and ISBNs written to logs (`app/lookup.py` fallback warnings; `mcp_server/server.py` unexpected-failure log) | Low | True positive | FIXED — log messages now record only the lookup kind, never user input. Regression tests added in `tests/test_lookup.py` and `tests/test_mcp_server.py`. Diff below. |
| Raw SQL built with an f-string in `_migrate_unique_books` (`app/db.py`) | Medium | False positive | The f-string only repeats `?` placeholders; every value is bound via parameters. Documented with `# nosemgrep` comments in the code. |
| `/docs` and `/openapi.json` exposed | Medium | Accepted risk | Single-user course application; interactive API documentation is part of the demo and TA review. Can be disabled in production later. |
| No TrustedHostMiddleware | Low | Accepted risk | Deployed behind the Render reverse proxy; no host-sensitive routing or multi-tenant behavior. |
| Cover URLs from Open Library assigned to `img.src` without scheme validation (`static/app.js`) | Low | Accepted risk | URLs originate from Open Library's own cover construction and are not attacker-controllable through this app; `<img src>` cannot execute script. |

## Fixed finding 1: user input in logs

**Before**

```python
logger.warning("Open Library unavailable for %s %r; using the seed", kind, query)
logger.warning("MCP lookup unavailable for ISBN %r; using the seed", isbn)
logger.exception("Unexpected failure resolving ISBN %r", key)
```

**After**

```python
logger.warning("%s lookup unavailable; using the seed", kind)
logger.warning("ISBN lookup unavailable; using the seed")
logger.exception("Unexpected failure resolving the requested ISBN")
```

Exception tracebacks are still logged server-side for diagnostics, but user-provided values are not echoed.

## Fixed finding 2: mutable CI action tags

**Before**

```yaml
uses: actions/checkout@v4
uses: actions/setup-python@v5
```

**After**

```yaml
uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5
```

## How the results were verified

- `--config auto`: 493 rules, 69 files; 2 findings (both above), re-scanned to 0 after fixing.
- MCP-only pass: 290 rules, 4 files, 0 findings.
- `p/security-audit`: 79 rules, 36 files, 0 findings.
- `p/owasp-top-ten`: 218 rules, 40 files, 0 findings.
- Manual review covered CORS allowlist, SQL parameterization, Jinja autoescaping, DOM sinks (textContent only), and server configuration; full test suite: 206 passed.