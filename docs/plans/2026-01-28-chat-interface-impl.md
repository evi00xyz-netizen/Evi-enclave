# Chat Interface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the developer page to a conversational chat interface powered by Claude Agent SDK with Redpill AI backend.

**Architecture:** FastAPI backend with anthropic SDK connecting to Redpill AI, server-side session storage, 12 tools for wallet/signing/attestation/registration/reputation/code execution, frontend chat UI with quick action buttons.

**Tech Stack:** Python (anthropic SDK, FastAPI), JavaScript (vanilla), Tailwind CSS

**Security Note:** All user-provided content rendered in the UI uses `escapeHtml()` to prevent XSS. The `formatContent()` function sanitizes markdown before rendering.

---

## Task 1: Add anthropic SDK to requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: Add anthropic dependency**

Add the anthropic SDK to requirements.txt after the existing dependencies:

```
anthropic>=0.40.0
```

**Step 2: Verify syntax**

Run: `python3 -c "import sys; sys.exit(0)"`
Expected: Exit code 0 (just verifying Python works)

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add anthropic SDK for chat interface"
```

---

## Task 2: Create session store module

**Files:**
- Create: `src/agent/session_store.py`

**Step 1: Create the session store module**

```python
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
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile src/agent/session_store.py`
Expected: No output (successful compilation)

**Step 3: Commit**

```bash
git add src/agent/session_store.py
git commit -m "feat: add session store for chat interface"
```

---

## Task 3: Create code execution module

**Files:**
- Create: `src/agent/code_executor.py`

**Step 1: Create the code executor module**

```python
"""
Code execution module for chat interface.

Executes Python and shell code in a subprocess with timeout.
"""

import subprocess
import tempfile
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    """Result of code execution."""
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    max_output_size: int = 10000
) -> ExecutionResult:
    """
    Execute code in a subprocess with timeout.

    Args:
        code: The code to execute
        language: "python" or "shell"
        timeout: Execution timeout in seconds
        max_output_size: Maximum output size in characters

    Returns:
        ExecutionResult with stdout, stderr, exit_code, and timed_out flag
    """
    script_path: Optional[str] = None

    try:
        if language == "python":
            # Write Python code to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                script_path = f.name
            cmd = ["python3", script_path]

        elif language == "shell":
            cmd = ["bash", "-c", code]

        else:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1
            )

        # Execute with restricted environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1"
            }
        )

        return ExecutionResult(
            stdout=result.stdout[:max_output_size],
            stderr=result.stderr[:max_output_size],
            exit_code=result.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds",
            exit_code=-1,
            timed_out=True
        )

    except Exception as e:
        return ExecutionResult(
            stdout="",
            stderr=f"Execution error: {str(e)}",
            exit_code=-1
        )

    finally:
        # Clean up temp file
        if script_path and os.path.exists(script_path):
            try:
                os.unlink(script_path)
            except:
                pass
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile src/agent/code_executor.py`
Expected: No output (successful compilation)

**Step 3: Commit**

```bash
git add src/agent/code_executor.py
git commit -m "feat: add code executor for chat interface"
```

---

## Task 4: Create chat agent module with tools

**Files:**
- Create: `src/agent/chat_agent.py`

**Step 1: Create the chat agent module**

```python
"""
Chat agent module using Anthropic SDK with Redpill backend.

Provides conversational interface with tools for TEE agent operations.
"""

import os
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from anthropic import Anthropic

from .session_store import Session
from .code_executor import execute_code, ExecutionResult


# System prompt template
SYSTEM_PROMPT = """You are a TEE (Trusted Execution Environment) Agent assistant running inside a secure enclave. You help developers interact with and explore this agent's capabilities.

## Your Identity
- Agent ID: {agent_id}
- Wallet Address: {wallet_address}
- Chain: {chain_name} (ID: {chain_id})
- TEE Status: {tee_status}

## Your Capabilities
You have access to these tools:
- **Wallet**: Check balance, sign messages, verify signatures
- **Attestation**: Generate cryptographic proofs of TEE execution
- **Agent Card**: View and explain agent metadata
- **Registration**: Check identity, reputation, and TEE registry status
- **Reputation**: Query reputation scores and submit feedback
- **Code Execution**: Run Python scripts or shell commands (sandboxed in TEE)

## Guidelines
1. Be concise but informative. Developers want facts, not fluff.
2. When showing addresses/hashes, display first 6 and last 4 chars (0xabcd...1234)
3. Always explain what TEE attestation proves when generating one
4. For code execution, warn about the {timeout}s timeout limit
5. If a tool fails, explain what went wrong and suggest alternatives
6. You can run multiple tools in sequence to answer complex questions

## Security Notes
- You cannot access the private key directly - only sign with it
- All code runs in an isolated subprocess with timeout
- Attestation proves this code runs in genuine TEE hardware
"""

# Tool definitions for Anthropic API
TOOL_DEFINITIONS = [
    {
        "name": "get_wallet_info",
        "description": "Get wallet address, balance, and chain information",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "sign_message",
        "description": "Sign a message with the agent's private key",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to sign"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "verify_signature",
        "description": "Verify a signed message",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The original message"
                },
                "signature": {
                    "type": "string",
                    "description": "The signature to verify"
                },
                "address": {
                    "type": "string",
                    "description": "The expected signer address"
                }
            },
            "required": ["message", "signature", "address"]
        }
    },
    {
        "name": "generate_attestation",
        "description": "Generate a TEE attestation proof",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_data": {
                    "type": "string",
                    "description": "Optional data to include in attestation"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_agent_card",
        "description": "Get the agent's full metadata card including capabilities and endpoints",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_registration_status",
        "description": "Check registration status across Identity, Reputation, and TEE registries",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_chain_config",
        "description": "Get current blockchain configuration including RPC endpoints and contract addresses",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_reputation",
        "description": "Get reputation information for an agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "Agent ID to query. Defaults to this agent if not specified."
                }
            },
            "required": []
        }
    },
    {
        "name": "submit_feedback",
        "description": "Submit feedback for another agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_agent_id": {
                    "type": "integer",
                    "description": "The agent to give feedback to"
                },
                "value": {
                    "type": "integer",
                    "description": "Feedback value (-100 to 100)"
                },
                "tag": {
                    "type": "string",
                    "description": "Category tag for the feedback"
                },
                "comment": {
                    "type": "string",
                    "description": "Optional comment"
                }
            },
            "required": ["target_agent_id", "value", "tag"]
        }
    },
    {
        "name": "run_python",
        "description": "Execute Python code in a sandboxed environment",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "run_shell",
        "description": "Execute a shell command in a sandboxed environment",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

# Initial greeting message
INITIAL_GREETING = """Hello! I'm your TEE agent assistant running in a secure enclave.

I can help you:
- Check wallet balance and sign messages
- Generate attestation proofs
- Query registration and reputation status
- Run Python or shell scripts
- Explore agent capabilities

What would you like to do?"""


class ChatAgent:
    """Chat agent using Anthropic SDK with Redpill backend."""

    def __init__(
        self,
        agent_context: Dict[str, Any],
        tool_handlers: Dict[str, callable]
    ):
        """
        Initialize the chat agent.

        Args:
            agent_context: Dict with agent_id, wallet_address, chain_name, chain_id, tee_status
            tool_handlers: Dict mapping tool names to handler functions
        """
        self.agent_context = agent_context
        self.tool_handlers = tool_handlers
        self.code_timeout = int(os.getenv("CODE_EXECUTION_TIMEOUT", "30"))

        # Initialize Anthropic client with Redpill backend
        self.client = Anthropic(
            api_key=os.getenv("ANTHROPIC_AUTH_TOKEN"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.redpill.ai")
        )
        self.model = os.getenv("ANTHROPIC_MODEL", "openai/gpt-oss-120b")

    def _build_system_prompt(self) -> str:
        """Build the system prompt with agent context."""
        return SYSTEM_PROMPT.format(
            agent_id=self.agent_context.get("agent_id", "Not registered"),
            wallet_address=self.agent_context.get("wallet_address", "Unknown"),
            chain_name=self.agent_context.get("chain_name", "Unknown"),
            chain_id=self.agent_context.get("chain_id", 0),
            tee_status=self.agent_context.get("tee_status", "Unknown"),
            timeout=self.code_timeout
        )

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool and return the result."""
        # Handle code execution tools locally
        if tool_name == "run_python":
            result = execute_code(
                tool_input.get("code", ""),
                language="python",
                timeout=self.code_timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out
            }

        elif tool_name == "run_shell":
            result = execute_code(
                tool_input.get("command", ""),
                language="shell",
                timeout=self.code_timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out
            }

        # Delegate to external handler
        handler = self.tool_handlers.get(tool_name)
        if handler:
            try:
                return await handler(tool_input)
            except Exception as e:
                return {"error": str(e)}

        return {"error": f"Unknown tool: {tool_name}"}

    async def chat(
        self,
        session: Session,
        user_message: str
    ) -> Tuple[str, List[dict]]:
        """
        Process a chat message and return the response.

        Args:
            session: The chat session
            user_message: The user's message

        Returns:
            Tuple of (response_text, tool_calls)
        """
        # Add user message to session
        session.add_message("user", user_message)

        # Build messages for API
        messages = session.get_messages_for_api()

        tool_calls = []
        max_iterations = 10  # Prevent infinite loops

        for _ in range(max_iterations):
            # Call the API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self._build_system_prompt(),
                tools=TOOL_DEFINITIONS,
                messages=messages
            )

            # Check if we need to handle tool use
            if response.stop_reason == "tool_use":
                # Process each tool use block
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        # Execute the tool
                        result = await self._execute_tool(tool_name, tool_input)
                        tool_calls.append({
                            "tool": tool_name,
                            "input": tool_input,
                            "result": result
                        })

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                # Add assistant message with tool use
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Add tool results
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

            else:
                # Extract text response
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text

                # Add assistant message to session
                session.add_message("assistant", response_text, tool_calls if tool_calls else None)

                return response_text, tool_calls

        # If we hit max iterations, return what we have
        return "I apologize, but I encountered an issue processing your request. Please try again.", tool_calls

    def get_initial_greeting(self) -> str:
        """Get the initial greeting message."""
        return INITIAL_GREETING
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile src/agent/chat_agent.py`
Expected: No output (successful compilation)

**Step 3: Commit**

```bash
git add src/agent/chat_agent.py
git commit -m "feat: add chat agent with tools for conversational interface"
```

---

## Task 5: Add chat endpoints to local_agent_server.py

**Files:**
- Modify: `deployment/local_agent_server.py`

**Step 1: Add imports at top of file (after existing imports, around line 33)**

```python
from src.agent.session_store import SessionStore
from src.agent.chat_agent import ChatAgent, INITIAL_GREETING
```

**Step 2: Add global session store and chat agent (after tee_verifier declaration, around line 62)**

```python
# Chat interface components
session_store: Optional[SessionStore] = None
chat_agent: Optional[ChatAgent] = None
```

**Step 3: Add Pydantic models for chat endpoints (after TaskRequest class, around line 44)**

```python
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class QuickActionRequest(BaseModel):
    session_id: Optional[str] = None
    tool: str
    arguments: Dict[str, Any] = {}
```

**Step 4: Add session store initialization in startup_event (before "AGENT SERVER READY" print, around line 245)**

```python
    # Initialize chat components
    global session_store, chat_agent
    timeout_minutes = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    max_sessions = int(os.getenv("MAX_SESSIONS", "100"))
    session_store = SessionStore(timeout_minutes=timeout_minutes, max_sessions=max_sessions)
    print(f"\n💬 Chat session store initialized (timeout: {timeout_minutes}m, max: {max_sessions})")
```

**Step 5: Add chat endpoints and tool handlers (before health check endpoint, around line 1044)**

Add the following endpoints and handler functions. Due to length, this is the high-level structure:

1. `POST /api/chat` - Main chat endpoint
2. `POST /api/quick-action` - Direct tool execution
3. `POST /api/session/new` - Create new session
4. `GET /api/session/{session_id}/history` - Get session history
5. `DELETE /api/session/{session_id}` - Delete session
6. Tool handler functions: `_handle_get_wallet_info`, `_handle_sign_message`, `_handle_verify_signature`, `_handle_generate_attestation`, `_handle_get_agent_card`, `_handle_get_registration_status`, `_handle_get_chain_config`, `_handle_get_reputation`, `_handle_submit_feedback`

See the design document `docs/plans/2026-01-28-chat-interface-design.md` Section 5 for the complete endpoint implementations.

**Step 6: Add json import at top if not present**

Ensure `import json` is at the top of the file.

**Step 7: Verify syntax**

Run: `python3 -m py_compile deployment/local_agent_server.py`
Expected: No output (successful compilation)

**Step 8: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: add chat and quick action endpoints to server"
```

---

## Task 6: Create chat.css stylesheet

**Files:**
- Create: `static/chat.css`

**Step 1: Create the CSS file**

Create a CSS file with styles for:
- Chat container layout
- Quick action buttons
- Message bubbles (user and assistant)
- Tool result cards (collapsible)
- Typing indicator animation
- Input area styling
- Agent status card (collapsed view)
- Scrollbar styling
- Basic markdown formatting in messages

See the design document `docs/plans/2026-01-28-chat-interface-design.md` Section 7 for color scheme and layout specifications.

**Step 2: Commit**

```bash
git add static/chat.css
git commit -m "feat: add chat interface styles"
```

---

## Task 7: Create chat.js client module

**Files:**
- Create: `static/chat.js`

**Step 1: Create the JavaScript file**

Create a JavaScript module with two classes:

1. `ChatClient` - Handles API communication
   - `getOrCreateSessionId()` - localStorage session management
   - `sendMessage(message)` - Send chat message
   - `quickAction(tool, args)` - Execute tool directly
   - `getHistory()` - Fetch session history
   - `newSession()` - Create new session

2. `ChatUI` - Handles UI rendering
   - `render()` - Render chat interface
   - `addMessage(message)` - Add message to chat
   - `formatContent(content)` - Basic markdown to HTML (with XSS protection via escapeHtml)
   - `renderToolResult(toolCall)` - Render collapsible tool result
   - `sendMessage()` - Handle send button click
   - `quickAction(tool)` - Handle quick action button
   - `showTyping()` - Show typing indicator
   - `setLoading(loading)` - Toggle loading state

**Security:** The `formatContent()` function must escape HTML entities before applying markdown transformations to prevent XSS.

**Step 2: Commit**

```bash
git add static/chat.js
git commit -m "feat: add chat client JavaScript module"
```

---

## Task 8: Update developer.html with chat interface

**Files:**
- Modify: `static/developer.html`

**Step 1: Update the HTML**

Replace the current developer page content with:

1. Header with navigation and "New Session" button
2. Collapsible agent status card (shows key info inline)
3. Expandable agent details section
4. Chat container div (rendered by JavaScript)
5. Collapsible API documentation section
6. Script to initialize ChatUI

Include CSS and JS imports:
```html
<link rel="stylesheet" href="/static/chat.css">
<script src="/static/chat.js"></script>
```

**Step 2: Commit**

```bash
git add static/developer.html
git commit -m "feat: replace developer page with chat interface"
```

---

## Task 9: Update docker-compose.yml with Redpill env vars

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add environment variables to agent service (after existing Redpill config, around line 92)**

```yaml
      # Anthropic/Redpill Chat Configuration
      - ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-${REDPILL_API_KEY}}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.redpill.ai}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-openai/gpt-oss-120b}

      # Chat Session Configuration
      - SESSION_TIMEOUT_MINUTES=${SESSION_TIMEOUT_MINUTES:-60}
      - MAX_SESSIONS=${MAX_SESSIONS:-100}
      - CODE_EXECUTION_TIMEOUT=${CODE_EXECUTION_TIMEOUT:-30}
```

**Step 2: Verify YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`
Expected: No output (valid YAML)

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "config: add Redpill and chat session env vars to docker-compose"
```

---

## Task 10: Final integration verification

**Files:**
- All modified files

**Step 1: Verify all Python files compile**

Run: `python3 -m py_compile src/agent/session_store.py src/agent/code_executor.py src/agent/chat_agent.py deployment/local_agent_server.py`
Expected: No output (all files compile successfully)

**Step 2: Verify static files exist**

Run: `ls -la static/chat.css static/chat.js static/developer.html`
Expected: All files exist

**Step 3: Verify requirements.txt has anthropic**

Run: `grep anthropic requirements.txt`
Expected: `anthropic>=0.40.0`

**Step 4: Create final commit if needed**

```bash
git status
git add -A
git commit -m "chore: complete chat interface implementation"
```

---

## Summary

After completing all tasks, the following files will be modified or created:

| File | Status | Description |
|------|--------|-------------|
| `requirements.txt` | Modified | Added anthropic SDK |
| `src/agent/session_store.py` | Created | Session management |
| `src/agent/code_executor.py` | Created | Python/shell execution |
| `src/agent/chat_agent.py` | Created | Chat agent with tools |
| `deployment/local_agent_server.py` | Modified | Chat endpoints |
| `static/chat.css` | Created | Chat UI styles |
| `static/chat.js` | Created | Chat client JS |
| `static/developer.html` | Modified | New chat interface |
| `docker-compose.yml` | Modified | Redpill env vars |

Total: 9 files (4 created, 5 modified)
