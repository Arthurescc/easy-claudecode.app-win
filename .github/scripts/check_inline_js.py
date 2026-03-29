#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_inline_js.py <html-file>", file=sys.stderr)
        return 64
    html_path = pathlib.Path(sys.argv[1]).resolve()
    html_text = html_path.read_text(encoding="utf-8")
    matches = re.findall(r"<script>(.*?)</script>", html_text, flags=re.S)
    if not matches:
        print(f"no inline <script> blocks found in {html_path}", file=sys.stderr)
        return 65
    inline_js = "\n\n".join(matches)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(inline_js)
        temp_path = handle.name
    try:
        completed = subprocess.run(
            ["node", "--check", temp_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr or completed.stdout or "node --check failed\n")
            return completed.returncode
        print(f"inline JS ok: {html_path}")
        return 0
    finally:
        pathlib.Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
