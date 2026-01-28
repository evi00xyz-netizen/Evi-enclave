# Claude Agent SDK Chat Interface Design

**Date:** 2026-01-28
**Status:** Approved

## Overview

Convert the developer page from a traditional dashboard into a conversational chat interface powered by Claude Agent SDK. The agent runs in the TEE and provides tools for wallet operations, attestation, registration status, reputation, and code execution.

## Current vs New Flow

**Current:**
```
Developer Dashboard → Static cards → Manual API button clicks → JSON responses
```

**New:**
```
Agent Status Card → Quick Action Buttons → Chat Interface → Conversational responses with tool results
```

## Section 1: High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Agent Card  │  │Quick Actions│  │     Chat Interface      │  │
│  │  (status)   │  │  (buttons)  │  │  (messages + input)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                            │                                     │
│                    POST /api/chat                                │
│                            ▼                                     │
├─────────────────────────────────────────────────────────────────┤
│                    FastAPI Backend (TEE)                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Claude Agent SDK                         │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐  │    │
│  │  │ Wallet  │  │ Signing │  │ Attesta │  │ Registry  │  │    │
│  │  │  Tool   │  │  Tool   │  │  Tool   │  │   Tools   │  │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └───────────┘  │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐  │    │
│  │  │ Reputa  │  │  Code   │  │  MCP    │  │  Agent    │  │    │
│  │  │  Tools  │  │  Exec   │  │  Tools  │  │   Card    │  │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └───────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                            │                                     │
│                    Redpill AI API                                │
│                            ▼                                     │
├─────────────────────────────────────────────────────────────────┤
│                   openai/gpt-oss-120b                            │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

- **Claude Agent SDK (Python)**: Native integration with existing FastAPI backend
- **Tools as Functions**: Each capability becomes a tool the agent can invoke
- **Session State**: Server-side session storage with message history
- **Quick Actions**: Bypass LLM for common operations, display results in chat format

## Section 2: Tool Definitions

### 2.1 Wallet Tools

```python
@tool
def get_wallet_info() -> dict:
    """Get wallet address, balance, and chain information."""
    return {
        "address": agent.wallet_address,
        "balance": agent.get_balance(),
        "chain": agent.chain_name,
        "chain_id": agent.chain_id
    }

@tool
def sign_message(message: str) -> dict:
    """Sign a message with the agent's private key.

    Args:
        message: The message to sign
    """
    signature = agent.sign_message(message)
    return {
        "message": message,
        "signature": signature,
        "signer": agent.wallet_address
    }

@tool
def verify_signature(message: str, signature: str, address: str) -> dict:
    """Verify a signed message.

    Args:
        message: The original message
        signature: The signature to verify
        address: The expected signer address
    """
    is_valid = agent.verify_signature(message, signature, address)
    return {"valid": is_valid, "address": address}
```

### 2.2 Attestation Tools

```python
@tool
def generate_attestation(user_data: str = "") -> dict:
    """Generate a TEE attestation proof.

    Args:
        user_data: Optional data to include in attestation
    """
    attestation = agent.generate_attestation(user_data)
    return {
        "attestation_hex": attestation.hex(),
        "user_data": user_data,
        "timestamp": datetime.now().isoformat()
    }
```

### 2.3 Agent Card Tools

```python
@tool
def get_agent_card() -> dict:
    """Get the agent's full metadata card including capabilities and endpoints."""
    return agent.get_agent_card()
```

### 2.4 Registration Status Tools

```python
@tool
def get_registration_status() -> dict:
    """Check registration status across Identity, Reputation, and TEE registries."""
    return {
        "identity": {
            "registered": agent.is_registered,
            "agent_id": agent.agent_id
        },
        "reputation": {
            "registered": agent.reputation_registered,
            "score": agent.reputation_score
        },
        "tee": {
            "verified": agent.tee_verified,
            "attestation_hash": agent.attestation_hash
        }
    }
```

### 2.5 Reputation Tools

```python
@tool
def get_reputation(agent_id: int = None) -> dict:
    """Get reputation information for an agent.

    Args:
        agent_id: Agent ID to query. Defaults to this agent.
    """
    target_id = agent_id or agent.agent_id
    return agent.get_reputation(target_id)

@tool
def submit_feedback(target_agent_id: int, value: int, tag: str, comment: str = "") -> dict:
    """Submit feedback for another agent.

    Args:
        target_agent_id: The agent to give feedback to
        value: Feedback value (-100 to 100)
        tag: Category tag for the feedback
        comment: Optional comment
    """
    result = agent.submit_feedback(target_agent_id, value, tag, comment)
    return {"tx_hash": result["tx_hash"], "success": True}
```

### 2.6 Code Execution Tools

```python
@tool
def run_python(code: str) -> dict:
    """Execute Python code in a sandboxed environment.

    Args:
        code: Python code to execute
    """
    result = execute_code(code, language="python", timeout=30)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code
    }

@tool
def run_shell(command: str) -> dict:
    """Execute a shell command in a sandboxed environment.

    Args:
        command: Shell command to execute
    """
    result = execute_code(command, language="shell", timeout=30)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code
    }
```

### 2.7 MCP Tools

```python
@tool
def list_mcp_tools() -> dict:
    """List available MCP server tools."""
    return {"tools": agent.mcp_tools}

@tool
def call_mcp_tool(server: str, tool_name: str, arguments: dict) -> dict:
    """Call an MCP server tool.

    Args:
        server: MCP server name
        tool_name: Tool to invoke
        arguments: Tool arguments
    """
    return agent.call_mcp_tool(server, tool_name, arguments)
```

### 2.8 Chain Configuration Tool

```python
@tool
def get_chain_config() -> dict:
    """Get current blockchain configuration including RPC endpoints and contract addresses."""
    return {
        "chain_id": agent.chain_id,
        "chain_name": agent.chain_name,
        "rpc_url": agent.rpc_url,
        "contracts": {
            "identity_registry": agent.identity_registry_address,
            "reputation_registry": agent.reputation_registry_address,
            "tee_registry": agent.tee_registry_address
        }
    }
```

## Section 3: Session & Memory Management

### Session Storage (Server-Side)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict
import uuid

@dataclass
class Session:
    id: str
    created_at: datetime
    last_active: datetime
    messages: List[Dict] = field(default_factory=list)

class SessionStore:
    def __init__(self, timeout_minutes: int = 60, max_sessions: int = 100):
        self.sessions: Dict[str, Session] = {}
        self.timeout_minutes = timeout_minutes
        self.max_sessions = max_sessions

    def create(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = Session(
            id=session_id,
            created_at=datetime.now(),
            last_active=datetime.now()
        )
        self._cleanup_expired()
        return session_id

    def get(self, session_id: str) -> Session | None:
        session = self.sessions.get(session_id)
        if session:
            session.last_active = datetime.now()
        return session

    def add_message(self, session_id: str, role: str, content: str):
        session = self.get(session_id)
        if session:
            session.messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })

    def _cleanup_expired(self):
        now = datetime.now()
        expired = [
            sid for sid, s in self.sessions.items()
            if (now - s.last_active).minutes > self.timeout_minutes
        ]
        for sid in expired:
            del self.sessions[sid]
```

### Client-Side Session ID

```javascript
// localStorage for session persistence
const SESSION_KEY = 'tee_agent_session_id';

function getOrCreateSessionId() {
    let sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem(SESSION_KEY, sessionId);
    }
    return sessionId;
}

function clearSession() {
    localStorage.removeItem(SESSION_KEY);
}
```

### Message History in Agent Calls

```python
async def chat(session_id: str, user_message: str) -> str:
    session = session_store.get(session_id)
    if not session:
        session_id = session_store.create()
        session = session_store.get(session_id)

    # Build messages array for Claude
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in session.messages
    ]
    messages.append({"role": "user", "content": user_message})

    # Call agent with full history
    response = await agent.run(messages=messages)

    # Store both messages
    session_store.add_message(session_id, "user", user_message)
    session_store.add_message(session_id, "assistant", response)

    return response
```

## Section 4: Code Execution

### Local Subprocess Execution

```python
import subprocess
import tempfile
import os
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30
) -> ExecutionResult:
    """Execute code in a subprocess with timeout."""

    if language == "python":
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False
        ) as f:
            f.write(code)
            script_path = f.name

        cmd = ["python3", script_path]

    elif language == "shell":
        cmd = ["bash", "-c", code]
        script_path = None

    else:
        return ExecutionResult("", f"Unsupported language: {language}", 1)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",  # Isolated working directory
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1"
            }
        )
        return ExecutionResult(
            stdout=result.stdout[:10000],  # Limit output size
            stderr=result.stderr[:10000],
            exit_code=result.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            stdout="",
            stderr=f"Execution timed out after {timeout}s",
            exit_code=-1,
            timed_out=True
        )

    finally:
        if script_path and os.path.exists(script_path):
            os.unlink(script_path)
```

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| File system access | CVM isolation + /tmp working dir |
| Network access | TEE network policies |
| Resource exhaustion | Timeout + output size limits |
| Sensitive data | No access to agent private key or env vars |

## Section 5: API Endpoints

### Chat Endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str

class ChatResponse(BaseModel):
    session_id: str
    response: str
    tool_calls: list[dict] | None = None

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Send a message to the agent and get a response."""
    session_id = request.session_id or session_store.create()

    try:
        response, tool_calls = await agent_chat(
            session_id=session_id,
            message=request.message
        )
        return ChatResponse(
            session_id=session_id,
            response=response,
            tool_calls=tool_calls
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Quick Action Endpoint

```python
class QuickActionRequest(BaseModel):
    session_id: str | None = None
    tool: str
    arguments: dict = {}

@app.post("/api/quick-action")
async def quick_action_endpoint(request: QuickActionRequest) -> ChatResponse:
    """Execute a tool directly without LLM, format result as chat message."""
    session_id = request.session_id or session_store.create()

    # Execute tool directly
    result = await execute_tool(request.tool, request.arguments)

    # Format as assistant message
    formatted = format_tool_result(request.tool, result)

    # Add to session history
    session_store.add_message(session_id, "user", f"[Quick Action: {request.tool}]")
    session_store.add_message(session_id, "assistant", formatted)

    return ChatResponse(
        session_id=session_id,
        response=formatted,
        tool_calls=[{"tool": request.tool, "result": result}]
    )
```

### Session Management Endpoints

```python
@app.post("/api/session/new")
async def new_session() -> dict:
    """Create a new chat session."""
    session_id = session_store.create()
    return {"session_id": session_id}

@app.get("/api/session/{session_id}/history")
async def get_history(session_id: str) -> dict:
    """Get message history for a session."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": session.messages}

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session and its history."""
    if session_id in session_store.sessions:
        del session_store.sessions[session_id]
    return {"deleted": True}
```

## Section 6: Docker & Deployment Configuration

### docker-compose.yml Updates

```yaml
services:
  agent:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      # Redpill AI Configuration
      - ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN}
      - ANTHROPIC_BASE_URL=https://api.redpill.ai
      - ANTHROPIC_DEFAULT_HAIKU_MODEL=openai/gpt-oss-120b
      - ANTHROPIC_DEFAULT_OPUS_MODEL=openai/gpt-oss-120b
      - ANTHROPIC_DEFAULT_SONNET_MODEL=openai/gpt-oss-120b
      - ANTHROPIC_MODEL=openai/gpt-oss-120b
      # Session Configuration
      - SESSION_TIMEOUT_MINUTES=60
      - MAX_SESSIONS=100
      - CODE_EXECUTION_TIMEOUT=30
      # Existing env vars...
    volumes:
      - ./skills:/app/skills:ro  # Custom skills (read-only)
    ports:
      - "8000:8000"
```

### New Dependencies (requirements.txt additions)

```
anthropic>=0.40.0
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_AUTH_TOKEN` | required | Redpill API key |
| `ANTHROPIC_BASE_URL` | https://api.redpill.ai | Redpill endpoint |
| `ANTHROPIC_MODEL` | openai/gpt-oss-120b | Model to use |
| `SESSION_TIMEOUT_MINUTES` | 60 | Session expiry |
| `MAX_SESSIONS` | 100 | Max concurrent sessions |
| `CODE_EXECUTION_TIMEOUT` | 30 | Script timeout (seconds) |

## Section 7: Frontend Chat UI Design

### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Agent Status Card (existing, collapsed by default)         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Agent ID: 42 │ Wallet: 0xabc... │ Status: Registered  │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Quick Actions                                              │
│  [Wallet Info] [Get Attestation] [Agent Card] [Reputation]  │
├─────────────────────────────────────────────────────────────┤
│  Chat Messages                                    ▲         │
│  ┌───────────────────────────────────────────────┐│         │
│  │ 🤖 Assistant                                  ││         │
│  │ Hello! I'm your TEE agent assistant...       ││         │
│  └───────────────────────────────────────────────┘│         │
│  ┌───────────────────────────────────────────────┐│ scroll  │
│  │ 👤 You                                        ││         │
│  │ What's my wallet balance?                    ││         │
│  └───────────────────────────────────────────────┘│         │
│  ┌───────────────────────────────────────────────┐│         │
│  │ 🤖 Assistant                                  ││         │
│  │ Your wallet balance is 0.5 ETH on Base...    ││         │
│  └───────────────────────────────────────────────┘▼         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────┐ [Send]         │
│  │ Type your message...                    │                │
│  └─────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Quick Action Buttons

| Button | Tool Called | Display |
|--------|-------------|---------|
| Wallet Info | `get_wallet_info` | Balance, address, chain |
| Get Attestation | `generate_attestation` | Attestation hex + report |
| Agent Card | `get_agent_card` | Full agent metadata |
| Reputation | `get_reputation` | Score, feedback count |
| Sign Message | Opens modal | Prompts for message input |
| Run Code | Opens modal | Code editor for Python/shell |

### Message Rendering

```html
<!-- User message -->
<div class="message user">
  <div class="avatar">👤</div>
  <div class="content">{text}</div>
</div>

<!-- Assistant message -->
<div class="message assistant">
  <div class="avatar">🤖</div>
  <div class="content">
    {text}
    <!-- Tool results rendered as collapsible cards -->
    <div class="tool-result" data-tool="get_wallet_info">
      <div class="tool-header">📋 Wallet Info <span class="toggle">▼</span></div>
      <pre class="tool-output">{formatted JSON}</pre>
    </div>
  </div>
</div>

<!-- Typing indicator -->
<div class="message assistant typing">
  <div class="avatar">🤖</div>
  <div class="dots"><span>.</span><span>.</span><span>.</span></div>
</div>
```

### Styling (CSS Variables)

```css
:root {
  --chat-bg: #1a1a2e;
  --message-user-bg: #16213e;
  --message-assistant-bg: #0f3460;
  --accent: #e94560;
  --text: #eaeaea;
  --tool-result-bg: #0a0a15;
}
```

## Section 8: System Prompt

```python
SYSTEM_PROMPT = """You are a TEE (Trusted Execution Environment) Agent assistant running inside a secure enclave. You help developers interact with and explore this agent's capabilities.

## Your Identity
- Agent ID: {agent_id}
- Wallet Address: {wallet_address}
- Chain: {chain_name} (ID: {chain_id})
- TEE Status: {tee_verified}

## Your Capabilities
You have access to these tools:
- **Wallet**: Check balance, sign messages, verify signatures
- **Attestation**: Generate cryptographic proofs of TEE execution
- **Agent Card**: View and explain agent metadata
- **Registration**: Check identity, reputation, and TEE registry status
- **Reputation**: Query reputation scores and submit feedback
- **Code Execution**: Run Python scripts or shell commands (sandboxed in TEE)
- **MCP Tools**: Access any configured MCP server tools

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
```

### Dynamic Variables

| Variable | Source |
|----------|--------|
| `{agent_id}` | From agent state |
| `{wallet_address}` | From wallet |
| `{chain_name}` | From config |
| `{chain_id}` | From config |
| `{tee_verified}` | "Verified" or "Pending" |
| `{timeout}` | CODE_EXECUTION_TIMEOUT env var |

### Initial Greeting (first message in new session)

```
Hello! I'm your TEE agent assistant running in a secure enclave.

I can help you:
• Check wallet balance and sign messages
• Generate attestation proofs
• Query registration and reputation status
• Run Python or shell scripts
• Explore agent capabilities

What would you like to do?
```

## Files to Modify

| File | Changes |
|------|---------|
| `deployment/local_agent_server.py` | Add chat endpoints, session store, tool definitions |
| `static/developer.html` | Replace with chat interface UI |
| `static/chat.js` | New file for chat client logic |
| `static/chat.css` | New file for chat styling |
| `docker-compose.yml` | Add Redpill env vars, session config |
| `requirements.txt` | Add anthropic SDK |
| `src/agent/chat.py` | New file for agent chat logic |
