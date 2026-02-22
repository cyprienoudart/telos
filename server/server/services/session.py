"""In-memory session store — one ConversationLoop per session."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ali.conversation_loop import ConversationLoop


@dataclass
class Session:
    id: str
    loop: ConversationLoop
    context_path: Path
    question_info: dict = field(default_factory=dict)
    done: bool = False
    transcript: str = ""  # accumulated context.md content for build phase
    repo_url: str | None = None  # original GitHub URL (echo back to client)
    repo_dir: Path | None = None  # cloned repo path (context + build target)


class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self, missions_path: str):
        self._sessions: dict[str, Session] = {}
        self._missions_path = missions_path

    def create(self) -> Session:
        session_id = uuid.uuid4().hex[:12]
        # Each session gets its own temp context.md
        tmp_dir = Path(tempfile.mkdtemp(prefix="telos_session_"))
        context_path = tmp_dir / "context.md"

        loop = ConversationLoop(
            missions_path=self._missions_path,
            context_path=str(context_path),
        )

        session = Session(
            id=session_id,
            loop=loop,
            context_path=context_path,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
