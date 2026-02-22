"""Clone a GitHub repo for use as context and build target."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

# Only allow HTTPS GitHub URLs (prevents command injection / arbitrary clones)
_GITHUB_RE = re.compile(r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$")


async def clone_repo(github_url: str) -> Path:
    """Shallow-clone a GitHub repo, return the local path.

    Raises ValueError for non-GitHub URLs and RuntimeError on clone failure.
    """
    if not _GITHUB_RE.match(github_url):
        raise ValueError(
            f"Invalid GitHub URL: {github_url!r}  "
            "(only https://github.com/<owner>/<repo> is accepted)"
        )

    tmp = Path(tempfile.mkdtemp(prefix="telos_repo_"))
    target = tmp / "repo"

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", github_url, str(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"git clone failed: {stderr.decode().strip()}")

    return target
