---
name: test
description: Run the Shelf Life test suite (pytest), analyse any failures, and report pass/fail/skip.
---

Run the test suite for this project.

Steps:
1. Use the project's virtual environment: `.venv\Scripts\python.exe -m pytest`.
   (This is a FastAPI + pytest project; tests live in `tests/`.)
2. Run the full suite. If the user gave a pattern in $ARGUMENTS, run only tests
   matching it: `.venv\Scripts\python.exe -m pytest $ARGUMENTS`.
3. If any tests fail, analyse each failure:
   - What is the test testing?
   - Is it a real bug or a flaky/environment issue?
4. Provide a summary: how many passed / failed / skipped.
5. For each failure: a one-line description and a proposed fix.

Never claim tests passed unless you actually executed them and saw the result
(per this project's CLAUDE.md).

Usage: `/test` or `/test tests/test_books.py`
