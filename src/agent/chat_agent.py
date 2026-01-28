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
from .code_executor import execute_code


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
