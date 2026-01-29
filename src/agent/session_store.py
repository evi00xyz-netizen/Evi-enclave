"""
Session store for chat interface.

Provides server-side session management with message history.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid


@dataclass
class Message:
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tool_calls: Optional[List[dict]] = None


@dataclass
class Session:
    """A chat session with message history."""
    id: str
    created_at: datetime
    last_active: datetime
    messages: List[Message] = field(default_factory=list)

    def add_message(self, role: str, content: str, tool_calls: Optional[List[dict]] = None):
        """Add a message to the session."""
        self.messages.append(Message(
            role=role,
            content=content,
            tool_calls=tool_calls
        ))
        self.last_active = datetime.utcnow()

    def get_messages_for_api(self) -> List[dict]:
        """Get messages formatted for the Anthropic API."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]


class SessionStore:
    """In-memory session store with automatic expiration."""

    def __init__(self, timeout_minutes: int = 60, max_sessions: int = 100):
        self.sessions: Dict[str, Session] = {}
        self.timeout_minutes = timeout_minutes
        self.max_sessions = max_sessions

    def create(self) -> str:
        """Create a new session and return its ID."""
        self._cleanup_expired()

        # If at max capacity, remove oldest session
        if len(self.sessions) >= self.max_sessions:
            oldest_id = min(
                self.sessions.keys(),
                key=lambda k: self.sessions[k].last_active
            )
            del self.sessions[oldest_id]

        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        self.sessions[session_id] = Session(
            id=session_id,
            created_at=now,
            last_active=now
        )
        return session_id

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, updating last_active."""
        session = self.sessions.get(session_id)
        if session:
            # Check if expired
            if self._is_expired(session):
                del self.sessions[session_id]
                return None
            session.last_active = datetime.utcnow()
        return session

    def get_or_create(self, session_id: Optional[str]) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = self.get(session_id)
            if session:
                return session
        # Create new session
        new_id = self.create()
        return self.sessions[new_id]

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def _is_expired(self, session: Session) -> bool:
        """Check if a session has expired."""
        expiry_time = session.last_active + timedelta(minutes=self.timeout_minutes)
        return datetime.utcnow() > expiry_time

    def _cleanup_expired(self):
        """Remove expired sessions."""
        expired = [
            sid for sid, session in self.sessions.items()
            if self._is_expired(session)
        ]
        for sid in expired:
            del self.sessions[sid]
