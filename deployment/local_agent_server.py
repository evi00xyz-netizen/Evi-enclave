#!/usr/bin/env python3
"""
Local Agent Server

Run agent locally with HTTP API for interaction and verification.
Demonstrates TEE-derived key signing without requiring on-chain registration.
"""

import sys
import os
import asyncio
import json
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime
from typing import Dict, Any, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from eth_account.messages import encode_defunct
from eth_utils import keccak
import uvicorn

from src.agent.base import AgentConfig, RegistryAddresses
from src.templates.server_agent import ServerAgent
from src.agent.tee_auth import TEEAuthenticator
from src.agent.chain_config import get_chain_config_from_env, log_chain_config
from src.agent.session_store import SessionStore
from src.agent.chat_agent import ChatAgent, INITIAL_GREETING


# Request/Response Models
class SignRequest(BaseModel):
    message: str


class TaskRequest(BaseModel):
    task_id: str
    query: str
    data: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class QuickActionRequest(BaseModel):
    session_id: Optional[str] = None
    tool: str
    arguments: Dict[str, Any] = {}


# Initialize FastAPI
app = FastAPI(
    title="ERC-8004 TEE Agent Server",
    description="Local agent server with TEE-derived key verification",
    version="1.0.0"
)

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), '..', 'static')
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Global agent instance
agent: Optional[ServerAgent] = None
tee_auth: Optional[TEEAuthenticator] = None

# Chat interface components
session_store: Optional[SessionStore] = None

# TEE Preparation State
tee_preparation = {
    "state": "idle",      # idle | preparing | ready | error
    "started_at": None,
    "proof_data": None,   # Cached: {tee_arch, code_measurement, code_config_uri, proof}
    "error": None,
    "expires_at": None    # Cache expiry time
}

TEE_CACHE_DURATION = 300  # 5 minutes


async def prepare_tee_attestation():
    """Background task to prepare TEE attestation and offchain proof."""
    global tee_preparation

    # Don't restart if already preparing or ready (and not expired)
    if tee_preparation["state"] == "preparing":
        return
    if tee_preparation["state"] == "ready" and tee_preparation["expires_at"]:
        if datetime.utcnow().timestamp() < tee_preparation["expires_at"]:
            return

    # Check prerequisites
    if not agent or not tee_auth or not agent.is_registered or not agent.agent_id:
        tee_preparation["state"] = "error"
        tee_preparation["error"] = "Agent not registered"
        return

    tee_preparation["state"] = "preparing"
    tee_preparation["started_at"] = datetime.utcnow().timestamp()
    tee_preparation["error"] = None

    try:
        # Step 1: Get TEE attestation
        attestation = await tee_auth.get_attestation()

        if "error" in attestation:
            raise Exception(f"Attestation failed: {attestation.get('error')}")

        if attestation.get("mode") == "development":
            raise Exception("TEE is disabled in development mode")

        if "quote" not in attestation or "event_log" not in attestation:
            raise Exception(f"Invalid attestation: missing fields")

        # Step 2: Get agent info
        agent_address = await agent._get_agent_address()
        agent_domain = os.getenv('AGENT_DOMAIN', '')

        # Strip protocol prefixes
        for prefix in ['https://', 'http://', 'ipfs://', 'ipns://']:
            if agent_domain.startswith(prefix):
                agent_domain = agent_domain[len(prefix):]

        # Parse domain
        if '-' in agent_domain and '.' in agent_domain:
            app_id = agent_domain.split('-')[0]
            dstack_domain = agent_domain.split('.', 1)[1]
        else:
            app_id = agent_domain.split(':')[0].split('.')[0]
            dstack_domain = os.getenv('DSTACK_GATEWAY_DOMAIN', 'local.dev')

        # Step 3: Get offchain proof
        import httpx
        from web3 import Web3

        payload = {
            'agentId': agent.agent_id,
            'agentPubkey': agent_address,
            'tdxQuote': attestation['quote'],
            'appId': app_id,
            'dstackDomain': dstack_domain,
        }

        print(f"🔄 TEE Prep: Requesting offchain proof...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                'https://194622febfc33d67e4a98f365dbc2fe9d0d53933-3000.dstack-pha-prod9.phala.network/getOffchainProof',
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

        # Cache the proof data
        tee_preparation["proof_data"] = {
            "tee_arch": Web3.to_bytes(text="TDX_DSTACK").ljust(32, b'\x00'),
            "code_measurement": data['codeMeasurement'],
            "code_config_uri": data['codeConfigUri'],
            "proof": data['proof'],
            "pubkey": Web3.to_checksum_address(agent_address)
        }
        tee_preparation["state"] = "ready"
        tee_preparation["expires_at"] = datetime.utcnow().timestamp() + TEE_CACHE_DURATION
        tee_preparation["error"] = None

        print(f"✅ TEE Prep: Proof cached, expires in {TEE_CACHE_DURATION}s")

    except Exception as e:
        print(f"❌ TEE Prep failed: {str(e)}")
        tee_preparation["state"] = "error"
        tee_preparation["error"] = str(e)
        tee_preparation["proof_data"] = None


@app.on_event("startup")
async def startup_event():
    """Initialize agent on startup."""
    global agent, tee_auth

    print("=" * 80)
    print("STARTING LOCAL AGENT SERVER")
    print("=" * 80)

    # Get domain from environment or use localhost
    domain = os.getenv("AGENT_DOMAIN", "localhost:8000")
    salt = os.getenv("AGENT_SALT", "local-development-salt")

    print(f"\n📍 Agent Domain: {domain}")
    print(f"🔐 Salt: {salt}")

    # Initialize TEE authenticator
    print("\n🔑 Initializing TEE authentication...")
    tee_auth = TEEAuthenticator(
        domain=domain,
        salt=salt,
        use_tee=True  # Use real TEE
    )

    address = await tee_auth.derive_address()
    print(f"✅ Agent Address: {address}")

    # Get attestation
    print("\n📜 Generating TEE attestation...")
    attestation = await tee_auth.get_attestation()
    if "quote" in attestation:
        quote_size = len(attestation.get("quote", ""))
        print(f"✅ Attestation generated: {quote_size} bytes")

    # Create agent configuration
    from src.agent.base import AgentRole

    # Load chain configuration from environment (multi-chain ready)
    chain_config = get_chain_config_from_env()
    print("\n🔗 Chain Configuration:")
    log_chain_config(chain_config)

    config = AgentConfig(
        domain=domain,
        salt=salt,
        role=AgentRole.SERVER,
        chain_id=chain_config.chain_id,
        rpc_url=chain_config.rpc_url,
        use_tee_auth=True,
        private_key=tee_auth.private_key
    )

    # Registry addresses from chain config
    registries = RegistryAddresses(
        identity=chain_config.identity_registry,
        reputation=chain_config.reputation_registry,
    )

    # Initialize agent
    print("\n🤖 Initializing agent...")
    agent = ServerAgent(config, registries)

    # Generate agent card
    print("\n📋 Generating agent card...")
    agent_card = await agent._create_agent_card()

    # Initialize chat components
    global session_store
    timeout_minutes = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    max_sessions = int(os.getenv("MAX_SESSIONS", "100"))
    session_store = SessionStore(timeout_minutes=timeout_minutes, max_sessions=max_sessions)
    print(f"\n💬 Chat session store initialized (timeout: {timeout_minutes}m, max: {max_sessions})")

    print("\n" + "=" * 80)
    print("✅ AGENT SERVER READY")
    print("=" * 80)
    print(f"\nAgent Name: {agent_card['name']}")
    print(f"Agent Address: {address}")
    print(f"Domain: {domain}")
    print(f"\nCapabilities:")
    for cap in agent_card.get('capabilities', []):
        print(f"  • {cap['name']}: {cap['description'][:60]}...")
    print("\n" + "=" * 80)


@app.get("/")
async def root():
    """Root endpoint - redirect to funding page."""
    return FileResponse(os.path.join(static_path, 'funding.html'))


@app.get("/funding")
async def funding_page():
    """Funding page."""
    return FileResponse(os.path.join(static_path, 'funding.html'))


@app.get("/dashboard")
async def dashboard_page():
    """Dashboard page."""
    return FileResponse(os.path.join(static_path, 'dashboard.html'))


@app.get("/developer")
async def developer_page():
    """Developer API interaction page."""
    return FileResponse(os.path.join(static_path, 'developer.html'))


@app.get("/api/chain-config")
async def get_chain_config():
    """Get blockchain configuration for frontend."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Map chain IDs to their configurations
    chain_configs = {
        84532: {
            "chain_id": 84532,
            "chain_id_hex": "0x14a34",
            "chain_name": "Base Sepolia",
            "native_currency": {
                "name": "Ether",
                "symbol": "ETH",
                "decimals": 18
            },
            "rpc_urls": ["https://sepolia.base.org"],
            "block_explorer_urls": ["https://sepolia.basescan.org"],
            "faucet_url": "https://www.alchemy.com/faucets/base-sepolia"
        },
        8453: {
            "chain_id": 8453,
            "chain_id_hex": "0x2105",
            "chain_name": "Base Mainnet",
            "native_currency": {
                "name": "Ether",
                "symbol": "ETH",
                "decimals": 18
            },
            "rpc_urls": ["https://mainnet.base.org"],
            "block_explorer_urls": ["https://basescan.org"],
            "faucet_url": None
        },
        11155111: {
            "chain_id": 11155111,
            "chain_id_hex": "0xaa36a7",
            "chain_name": "Ethereum Sepolia",
            "native_currency": {
                "name": "Ether",
                "symbol": "ETH",
                "decimals": 18
            },
            "rpc_urls": ["https://rpc.sepolia.org"],
            "block_explorer_urls": ["https://sepolia.etherscan.io"],
            "faucet_url": "https://sepoliafaucet.com"
        },
        1: {
            "chain_id": 1,
            "chain_id_hex": "0x1",
            "chain_name": "Ethereum Mainnet",
            "native_currency": {
                "name": "Ether",
                "symbol": "ETH",
                "decimals": 18
            },
            "rpc_urls": ["https://eth.llamarpc.com"],
            "block_explorer_urls": ["https://etherscan.io"],
            "faucet_url": None
        }
    }

    chain_id = agent.config.chain_id
    config = chain_configs.get(chain_id, {
        "chain_id": chain_id,
        "chain_id_hex": hex(chain_id),
        "chain_name": f"Chain {chain_id}",
        "native_currency": {
            "name": "Ether",
            "symbol": "ETH",
            "decimals": 18
        },
        "rpc_urls": [agent.config.rpc_url],
        "block_explorer_urls": [],
        "faucet_url": None
    })

    return config


@app.get("/api/trust-center-url")
async def get_trust_center_url():
    """Get trust center URL from environment."""
    trust_center_url = os.getenv("TRUST_CENTER_URL", "")

    if not trust_center_url:
        raise HTTPException(status_code=404, detail="Trust center URL not configured")

    return {"trust_center_url": trust_center_url}


@app.get("/api/wallet")
async def get_wallet():
    """Get wallet address and balance for funding."""
    if not agent or not tee_auth:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent_address = await agent._get_agent_address()
    balance_wei = agent._registry_client.w3.eth.get_balance(agent_address)
    balance_eth = agent._registry_client.w3.from_wei(balance_wei, 'ether')
    min_balance = 0.001  # Minimum ETH for gas

    # Get chain config dynamically
    chain_configs = {
        84532: "Base Sepolia",
        8453: "Base Mainnet",
        11155111: "Ethereum Sepolia",
        1: "Ethereum Mainnet"
    }
    chain_name = chain_configs.get(agent.config.chain_id, f"Chain {agent.config.chain_id}")

    return {
        "address": agent_address,
        "balance": str(balance_eth),
        "balance_wei": str(balance_wei),
        "qr_code_data": f"ethereum:{agent_address}?chainId={agent.config.chain_id}",
        "chain_id": agent.config.chain_id,
        "chain_name": chain_name,
        "funded": float(balance_eth) >= min_balance,
        "minimum_balance": str(min_balance)
    }


@app.get("/api/status")
async def get_status():
    """Get agent status - check on-chain."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent_address = await agent._get_agent_address()

    is_registered = False
    agent_id = None

    # Always check on-chain registration to prevent spam registrations
    # Use fast path if we already have agent_id in memory (1 RPC call vs 1000)
    address_check = await agent._registry_client.check_agent_registration(
        agent_address=agent_address,
        agent_id=agent.agent_id if agent.agent_id else None
    )

    if address_check["registered"]:
        is_registered = True
        agent_id = address_check["agent_id"]
        # Update in-memory state
        agent.agent_id = agent_id
        agent.is_registered = True
    else:
        # Clear in-memory state if not registered on-chain
        agent.agent_id = None
        agent.is_registered = False

    return {
        "status": "operational",
        "agent": {
            "domain": agent.config.domain,
            "address": agent_address,
            "agent_id": agent_id,
            "is_registered": is_registered,
            "chain_id": agent.config.chain_id
        },
        "tee": {
            "enabled": True,
            "endpoint": tee_auth.tee_endpoint if tee_auth else None
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/sign")
async def sign_message(request: SignRequest):
    """
    Sign a message with TEE-derived key.

    This endpoint demonstrates the agent's cryptographic identity.
    """
    if not agent or not tee_auth:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        # Create message hash
        message_bytes = request.message.encode('utf-8')
        message_hash = keccak(message_bytes)

        # Sign with TEE key
        signature = await tee_auth.sign_with_tee(message_hash)

        # Also create EIP-191 signature for wallet compatibility
        signable_message = encode_defunct(text=request.message)
        signed_message = tee_auth.account.sign_message(signable_message)

        return {
            "message": request.message,
            "message_hash": "0x" + message_hash.hex(),
            "signature": "0x" + signature.hex(),
            "eip191_signature": signed_message.signature.hex(),
            "signer_address": await agent._get_agent_address(),
            "domain": agent.config.domain,
            "timestamp": datetime.utcnow().isoformat(),
            "verification": {
                "note": "Use eth_account.Account.recover_message() to verify EIP-191 signature",
                "expected_address": await agent._get_agent_address()
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signing failed: {str(e)}")


@app.post("/api/process")
async def process_task(request: TaskRequest):
    """
    Process a task with the agent.

    Demonstrates agent's analytical capabilities.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        task_data = {
            "task_id": request.task_id,
            "query": request.query,
            "data": request.data or {},
            "parameters": request.parameters or {}
        }

        result = await agent.process_task(task_data)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task processing failed: {str(e)}")


@app.get("/api/card")
async def get_agent_card():
    """Get ERC-8004 compliant agent card."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        card = await agent._create_agent_card()
        return card

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate card: {str(e)}")


@app.get("/api/attestation")
async def get_attestation():
    """Get TEE attestation for the agent."""
    if not tee_auth:
        raise HTTPException(status_code=503, detail="TEE auth not initialized")

    try:
        attestation = await tee_auth.get_attestation()

        # Format for API response
        response = {
            "agent_address": attestation.get("agent_address"),
            "endpoint": attestation.get("endpoint"),
            "application_data": attestation.get("application_data"),
            "quote_size": len(attestation.get("quote", "")),
            "event_log_size": len(attestation.get("event_log", "")),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Include full quote and event log
        if attestation.get("quote"):
            response["quote"] = attestation["quote"]

        if attestation.get("event_log"):
            response["event_log"] = attestation["event_log"]

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attestation: {str(e)}")


@app.post("/api/register")
async def register_agent():
    """Register agent on-chain."""
    if not agent or not tee_auth:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    agent_address = await agent._get_agent_address()

    # Check if already registered (ERC-721 based, check by address only)
    address_check = await agent._registry_client.check_agent_registration(agent_address=agent_address)

    if address_check["registered"]:
        agent_id = address_check["agent_id"]
        agent.agent_id = agent_id
        agent.is_registered = True
        # Auto-start TEE preparation for already registered agents
        asyncio.create_task(prepare_tee_attestation())
        return {
            "success": True,
            "agent_id": agent_id,
            "already_registered": True,
            "domain": agent.config.domain,
            "address": agent_address,
            "tee_prep_started": True
        }

    # Check balance
    balance_wei = agent._registry_client.w3.eth.get_balance(agent_address)
    balance_eth = float(agent._registry_client.w3.from_wei(balance_wei, 'ether'))

    if balance_eth < 0.001:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Try to register (don't wait for receipt - return tx_hash immediately)
    try:
        result = await agent._registry_client.register_agent(
            agent.config.domain,
            agent_address,
            wait_for_receipt=False
        )

        return {
            "success": True,
            "tx_hash": result["tx_hash"],
            "agent_address": result["agent_address"],
            "domain": agent.config.domain,
            "message": "Call /api/tee/prepare after registration confirms"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/transaction/{tx_hash}/status")
async def get_transaction_status(tx_hash: str):
    """Check transaction status and extract agent_id if confirmed."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    try:
        status = await agent._registry_client.get_transaction_status(tx_hash)

        # If confirmed and we have agent_id, update agent state
        if status.get("confirmed") and status.get("agent_id"):
            agent.agent_id = status["agent_id"]
            agent.is_registered = True

        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check transaction: {str(e)}")


@app.post("/api/tee/prepare")
async def prepare_tee():
    """Start background TEE attestation preparation."""
    global tee_preparation

    if not agent or not tee_auth:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not agent.is_registered or not agent.agent_id:
        raise HTTPException(status_code=400, detail="Agent must be registered first")

    # If already ready and not expired, return current state
    if tee_preparation["state"] == "ready" and tee_preparation["expires_at"]:
        if datetime.utcnow().timestamp() < tee_preparation["expires_at"]:
            return {
                "state": "ready",
                "message": "TEE proof already cached",
                "expires_in": int(tee_preparation["expires_at"] - datetime.utcnow().timestamp())
            }

    # If already preparing, return current state
    if tee_preparation["state"] == "preparing":
        elapsed = int(datetime.utcnow().timestamp() - tee_preparation["started_at"])
        return {
            "state": "preparing",
            "message": "TEE preparation in progress",
            "elapsed_seconds": elapsed
        }

    # Start background preparation
    asyncio.create_task(prepare_tee_attestation())

    return {
        "state": "preparing",
        "message": "TEE preparation started"
    }


@app.get("/api/tee/status")
async def get_tee_status():
    """Get TEE preparation status."""
    global tee_preparation

    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    response = {
        "state": tee_preparation["state"],
        "error": tee_preparation["error"]
    }

    if tee_preparation["state"] == "preparing" and tee_preparation["started_at"]:
        response["elapsed_seconds"] = int(datetime.utcnow().timestamp() - tee_preparation["started_at"])

    if tee_preparation["state"] == "ready" and tee_preparation["expires_at"]:
        remaining = int(tee_preparation["expires_at"] - datetime.utcnow().timestamp())
        if remaining > 0:
            response["expires_in"] = remaining
            response["cached_until"] = datetime.utcfromtimestamp(tee_preparation["expires_at"]).isoformat() + "Z"
        else:
            # Expired, reset to idle
            tee_preparation["state"] = "idle"
            tee_preparation["proof_data"] = None
            response["state"] = "idle"

    return response


@app.post("/api/metadata/update")
async def update_metadata():
    """Update on-chain metadata."""
    if not agent or not agent.is_registered or not agent.agent_id:
        raise HTTPException(status_code=400, detail="Agent not registered")

    agent_address = await agent._get_agent_address()

    # Verify ownership
    owner = agent._registry_client.identity_contract.functions.ownerOf(agent.agent_id).call()
    if owner.lower() != agent_address.lower():
        raise HTTPException(status_code=403, detail="Not owner")

    # Set metadata
    metadata_value = f"https://{agent.config.domain}/agent.json".encode()

    tx = agent._registry_client.identity_contract.functions.setMetadata(
        agent.agent_id,
        "agent_card_uri",
        metadata_value
    ).build_transaction({
        'chainId': agent._registry_client.chain_id,
        'gas': 200000,
        'gasPrice': agent._registry_client.w3.eth.gas_price,
        'nonce': agent._registry_client.w3.eth.get_transaction_count(agent_address)
    })

    signed = agent._registry_client.account.sign_transaction(tx)
    tx_hash = agent._registry_client.w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = agent._registry_client.w3.eth.wait_for_transaction_receipt(tx_hash)

    return {
        "success": True,
        "tx_hash": tx_hash.hex(),
        "agent_id": agent.agent_id
    }


@app.get("/.well-known/agent-card.json")
@app.get("/a2a/card")
async def agent_card():
    """ERC-8004: Agent card at standard path."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await agent._create_agent_card()


@app.get("/agent.json")
async def agent_registration():
    """ERC-8004 registration-v1 format."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    from src.agent.agent_card import build_erc8004_registration

    chain_config = get_chain_config_from_env()
    agent_address = await agent._get_agent_address()

    return build_erc8004_registration(
        domain=agent.config.domain,
        agent_address=agent_address,
        agent_id=agent.agent_id if agent.is_registered else None,
        identity_registry=chain_config.identity_registry,
        chain_id=chain_config.chain_id,
        config_path="agent_config.json"
    )


@app.get("/.well-known/agent-registration.json")
async def agent_registration_wellknown():
    """ERC-8004 domain verification endpoint (best practice)."""
    return await agent_registration()


@app.get("/api/reputation")
@app.get("/api/reputation/{agent_id}")
async def get_reputation(agent_id: Optional[int] = None):
    """Get agent reputation from contract/subgraph."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Use provided agent_id or default to current agent
    target_agent_id = agent_id if agent_id is not None else agent.agent_id

    if target_agent_id is None:
        raise HTTPException(status_code=400, detail="Agent not registered - no agent_id available")

    try:
        reputation = await agent._registry_client.get_reputation(target_agent_id)
        return {
            "agent_id": target_agent_id,
            "reputation": reputation,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reputation: {str(e)}")


@app.post("/api/reputation/submit-initial")
async def submit_initial_reputation(request: Dict[str, Any] = None):
    """Submit initial reputation entry for agent."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not agent.is_registered or not agent.agent_id:
        raise HTTPException(status_code=400, detail="Agent must be registered first")

    try:
        result = await agent._registry_client.submit_initial_reputation(
            agent_id=agent.agent_id,
            wait_for_receipt=True
        )
        return {
            "success": True,
            "tx_hash": result.get("tx_hash"),
            "agent_id": result.get("agent_id"),
            "confirmed": result.get("confirmed", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit initial reputation: {str(e)}")


tasks = {}

@app.post("/tasks")
async def create_task(request: Dict[str, Any]):
    """A2A: Create task."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    task_id = request.get("taskId") or str(__import__('uuid').uuid4())
    context_id = request.get("contextId") or task_id

    tasks[task_id] = {
        "taskId": task_id,
        "contextId": context_id,
        "status": "pending",
        "artifacts": []
    }

    # Execute async
    asyncio.create_task(execute_task(task_id, request))

    return {"taskId": task_id, "status": "pending"}

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """A2A: Get task status."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

async def execute_task(task_id: str, request: Dict[str, Any]):
    tasks[task_id]["status"] = "running"
    try:
        result = await agent.process_task(request)
        tasks[task_id].update({
            "status": "completed",
            "artifacts": [{"type": "result", "data": result}]
        })
    except Exception as e:
        tasks[task_id].update({
            "status": "failed",
            "error": str(e)
        })


# =============================================================================
# CHAT INTERFACE ENDPOINTS
# =============================================================================

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Send a message to the chat agent."""
    global session_store, agent, tee_auth

    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")

    # Get or create session
    session = session_store.get_or_create(request.session_id)

    # Build agent context
    agent_address = await agent._get_agent_address()
    chain_configs = {
        84532: "Base Sepolia",
        8453: "Base Mainnet",
        11155111: "Ethereum Sepolia",
        1: "Ethereum Mainnet"
    }

    agent_context = {
        "agent_id": agent.agent_id or "Not registered",
        "wallet_address": agent_address,
        "chain_name": chain_configs.get(agent.config.chain_id, f"Chain {agent.config.chain_id}"),
        "chain_id": agent.config.chain_id
    }

    # Build tool handlers
    tool_handlers = {
        "get_wallet_info": _handle_get_wallet_info,
        "sign_message": _handle_sign_message,
        "verify_signature": _handle_verify_signature,
        "generate_attestation": _handle_generate_attestation,
        "get_agent_card": _handle_get_agent_card,
        "get_registration_status": _handle_get_registration_status,
        "get_chain_config": _handle_get_chain_config,
        "get_reputation": _handle_get_reputation,
        "submit_feedback": _handle_submit_feedback,
    }

    # Create chat agent for this request
    chat_agent = ChatAgent(agent_context, tool_handlers)

    try:
        response_text, tool_calls = await chat_agent.chat(session, request.message)

        return {
            "session_id": session.id,
            "response": response_text,
            "tool_calls": tool_calls if tool_calls else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.post("/api/quick-action")
async def quick_action_endpoint(request: QuickActionRequest):
    """Execute a tool directly without LLM."""
    global session_store, agent

    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")

    # Get or create session
    session = session_store.get_or_create(request.session_id)

    # Map tool names to handlers
    tool_map = {
        "get_wallet_info": _handle_get_wallet_info,
        "get_agent_card": _handle_get_agent_card,
        "generate_attestation": _handle_generate_attestation,
        "get_registration_status": _handle_get_registration_status,
        "get_reputation": _handle_get_reputation,
    }

    handler = tool_map.get(request.tool)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")

    try:
        result = await handler(request.arguments)

        # Format as chat message
        formatted = f"**{request.tool}**\n```json\n{json.dumps(result, indent=2)}\n```"

        # Add to session history
        session.add_message("user", f"[Quick Action: {request.tool}]")
        session.add_message("assistant", formatted, [{"tool": request.tool, "result": result}])

        return {
            "session_id": session.id,
            "response": formatted,
            "tool_calls": [{"tool": request.tool, "result": result}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool error: {str(e)}")


@app.post("/api/session/new")
async def new_session():
    """Create a new chat session."""
    global session_store

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")

    session_id = session_store.create()
    return {
        "session_id": session_id,
        "greeting": INITIAL_GREETING
    }


@app.get("/api/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get message history for a session."""
    global session_store

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")

    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tool_calls": msg.tool_calls
            }
            for msg in session.messages
        ]
    }


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    global session_store

    if not session_store:
        raise HTTPException(status_code=503, detail="Session store not initialized")

    deleted = session_store.delete(session_id)
    return {"deleted": deleted}


# =============================================================================
# CHAT TOOL HANDLERS
# =============================================================================

async def _handle_get_wallet_info(args: dict) -> dict:
    """Handle get_wallet_info tool."""
    agent_address = await agent._get_agent_address()
    balance_wei = agent._registry_client.w3.eth.get_balance(agent_address)
    balance_eth = agent._registry_client.w3.from_wei(balance_wei, 'ether')

    chain_configs = {
        84532: "Base Sepolia",
        8453: "Base Mainnet",
        11155111: "Ethereum Sepolia",
        1: "Ethereum Mainnet"
    }

    return {
        "address": agent_address,
        "balance": str(balance_eth),
        "balance_wei": str(balance_wei),
        "chain": chain_configs.get(agent.config.chain_id, f"Chain {agent.config.chain_id}"),
        "chain_id": agent.config.chain_id
    }


async def _handle_sign_message(args: dict) -> dict:
    """Handle sign_message tool."""
    message = args.get("message", "")
    signable_message = encode_defunct(text=message)
    signed = tee_auth.account.sign_message(signable_message)

    return {
        "message": message,
        "signature": signed.signature.hex(),
        "signer": await agent._get_agent_address()
    }


async def _handle_verify_signature(args: dict) -> dict:
    """Handle verify_signature tool."""
    from eth_account import Account

    message = args.get("message", "")
    signature = args.get("signature", "")
    expected_address = args.get("address", "")

    try:
        signable_message = encode_defunct(text=message)
        recovered = Account.recover_message(signable_message, signature=signature)
        is_valid = recovered.lower() == expected_address.lower()
        return {
            "valid": is_valid,
            "recovered_address": recovered,
            "expected_address": expected_address
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


async def _handle_generate_attestation(args: dict) -> dict:
    """Handle generate_attestation tool - returns full TEE attestation."""
    attestation = await tee_auth.get_attestation()

    if "error" in attestation:
        return {"error": attestation["error"]}

    # Check if in development mode (no real TEE)
    if attestation.get("mode") == "development":
        return {
            "mode": "development",
            "warning": "Running outside TEE - no real attestation available",
            "timestamp": datetime.utcnow().isoformat()
        }

    # Return actual attestation data
    quote = attestation.get("quote", "")
    event_log = attestation.get("event_log", "")

    # Parse TDX quote header for readable info (first 48 bytes contain header)
    quote_info = {}
    if quote and len(quote) >= 96:  # At least 48 bytes in hex
        try:
            quote_bytes = bytes.fromhex(quote[:96])
            quote_info = {
                "version": int.from_bytes(quote_bytes[0:2], 'little'),
                "attestation_key_type": int.from_bytes(quote_bytes[2:4], 'little'),
                "tee_type": hex(int.from_bytes(quote_bytes[4:8], 'little')),
            }
        except Exception:
            pass

    return {
        "quote": quote,
        "quote_hex_length": len(quote),
        "quote_info": quote_info,
        "event_log": event_log,
        "event_log_length": len(event_log),
        "timestamp": datetime.utcnow().isoformat(),
        "user_data": args.get("user_data", ""),
        "verification": {
            "type": "Intel TDX",
            "provider": "dstack",
            "verify_url": f"https://{os.getenv('AGENT_DOMAIN', '')}/api/tee/verify"
        }
    }


async def _handle_get_agent_card(args: dict) -> dict:
    """Handle get_agent_card tool."""
    return await agent._create_agent_card()


async def _handle_get_registration_status(args: dict) -> dict:
    """Handle get_registration_status tool."""
    return {
        "identity": {
            "registered": agent.is_registered,
            "agent_id": agent.agent_id
        }
    }


async def _handle_get_chain_config(args: dict) -> dict:
    """Handle get_chain_config tool."""
    chain_config = get_chain_config_from_env()

    return {
        "chain_id": chain_config.chain_id,
        "rpc_url": chain_config.rpc_url,
        "contracts": {
            "identity_registry": chain_config.identity_registry,
            "reputation_registry": chain_config.reputation_registry
        }
    }


async def _handle_get_reputation(args: dict) -> dict:
    """Handle get_reputation tool."""
    target_id = args.get("agent_id") or agent.agent_id

    if not target_id:
        return {"error": "No agent ID specified and agent not registered"}

    try:
        reputation = await agent._registry_client.get_reputation(target_id)
        return {
            "agent_id": target_id,
            "reputation": reputation
        }
    except Exception as e:
        return {"error": str(e)}


async def _handle_submit_feedback(args: dict) -> dict:
    """Handle submit_feedback tool."""
    try:
        result = await agent._registry_client.give_feedback(
            agent_id=args["target_agent_id"],
            value=args["value"],
            tag=args["tag"],
            comment=args.get("comment", "")
        )
        return {
            "success": True,
            "tx_hash": result.get("tx_hash")
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


def main():
    """Run the agent server."""
    # Get configuration
    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8000"))

    print("\n🚀 Starting agent server...")
    print(f"📍 Listening on {host}:{port}")
    print(f"📖 API docs available at http://localhost:{port}/docs\n")

    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
