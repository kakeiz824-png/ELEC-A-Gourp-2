"""StudyDeck application package.

Loads a local ``.env`` file (if present) before anything else in the package
runs, so modules that read configuration at import time -- notably
``app.auth``, which bakes ``GOOGLE_CLIENT_ID`` into the OAuth client -- see the
values without the developer having to export them into every shell. Real
environment variables always win over the file.
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    # utf-8-sig tolerates a byte-order mark that some Windows editors prepend.
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            # setdefault so an already-exported variable is never overridden.
            os.environ.setdefault(key, value)


_load_dotenv()
