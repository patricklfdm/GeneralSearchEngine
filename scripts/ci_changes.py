"""Choose the lightweight documentation lane; unknown inputs run full CI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess


def is_documentation(path: str) -> bool:
    parts = path.split("/")
    # Markdown in source/test resources can itself be a build input.
    if "src" in parts[:-1] or path.startswith((".github/workflows/", "scripts/", ".mvn/")):
        return False
    return (path.endswith(".md") or path in {"LICENSE", ".gitignore"}
            or path.startswith(".github/ISSUE_TEMPLATE/"))


def comparison(event_name: str, event: dict) -> str | None:
    try:
        if event_name == "pull_request":
            base = event["pull_request"]["base"]["sha"]
            head = event["pull_request"]["head"]["sha"]
            separator = "..."  # Entire PR, including code in earlier commits.
        elif event_name == "push":
            base, head = event["before"], event["after"]
            separator = ".."  # Entire push, not only its final commit.
        else:
            return None  # Manual dispatch and unknown events always run full CI.
    except (KeyError, TypeError):
        return None
    if not all(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha)
               and sha != "0" * 40 for sha in (base, head)):
        return None
    return base + separator + head


def decide(event_name: str, event: dict, repository: Path) -> tuple[bool, str]:
    revisions = comparison(event_name, event)
    if revisions is None:
        return True, "manual/unknown event or unavailable commit boundary"
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", revisions, "--"],
            cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return True, "commit comparison unavailable"
    if not changed or not changed.endswith(b"\0"):
        return True, "empty or invalid change list"
    # No API pagination/file-count limit; --no-renames includes both old and new
    # paths, so moving a source file into docs cannot hide the source deletion.
    paths = changed[:-1].decode("utf-8", errors="surrogateescape").split("\0")
    full = any(not is_documentation(path) for path in paths)
    return full, f"{len(paths)} changed paths; " + ("build inputs changed" if full else "documentation only")


def main() -> None:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        full, reason = True, "event payload unavailable"
    else:
        full, reason = decide(os.environ.get("GITHUB_EVENT_NAME", ""), event, Path.cwd())
    value = str(full).lower()
    print(f"run_full_ci={value}: {reason}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"run_full_ci={value}\n")


if __name__ == "__main__":
    main()
