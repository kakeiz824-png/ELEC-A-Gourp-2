# Semgrep Security Scan Report

## Scan Metadata

- Date: 2026-08-05
- Operator: Sam Zhu
- Tool: Semgrep OSS 1.172.0
- Configuration: Semgrep Registry automatic community rules (`--config=auto`)
- Source scope: current Shelf Life project
- Raw machine-readable result: `semgrep-report.json`

## Command

```powershell
uvx semgrep scan --config=auto --exclude=.venv --exclude=.uv-cache-semgrep --json-output=semgrep-report.json .
```

The virtual environment and temporary installation cache were excluded because they
contain third-party dependencies rather than project source.

## Results

| Measure | Result |
|---|---:|
| Project files scanned | 54 |
| Rules run | 493 |
| Findings | 0 |
| Blocking findings | 0 |
| Scan errors | 0 |
| Parsed project lines | Approximately 100% |

Semgrep scanned the project's Python, JavaScript, HTML, JSON, YAML, and multi-language
files. The scan completed successfully with no reported findings.

## Human Triage

There were no Critical, High, blocking, or other Semgrep findings to triage. Therefore:

- No security finding was dismissed as a false positive.
- No source-code change was required by this scan.
- No Critical or High finding remains unresolved.

## Limitations

A zero-finding static scan does not prove that the application has no security defects.
This run used the public automatic community rules and did not use Semgrep Pro rules.
Runtime configuration, authentication decisions, external-service behavior, dependency
vulnerabilities, and production secrets still require separate review. Secrets must
remain in environment variables, and the full automated and manual test suites should
still be run before deployment.

## Conclusion

The current source passes the required Semgrep static-analysis pass with zero findings.
The raw JSON result is retained beside this report so the scan can be independently
checked. Run the same command again after material code changes and before final code
freeze.
