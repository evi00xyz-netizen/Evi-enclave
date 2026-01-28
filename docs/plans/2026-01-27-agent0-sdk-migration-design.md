# Agent0 SDK Migration Design

Migrate from custom web3.py implementation to agent0-py SDK with ETH Sepolia contracts and reputation support.

## Summary

- **Approach**: Python-First Migration
- **Target Chain**: ETH Sepolia (multi-chain ready via config)
- **SDK**: agent0-py for registry/reputation operations
- **TEE**: Keep dstack-sdk and custom `tee_verifier.py`
- **Data Access**: Direct GraphQL queries to subgraph

## Contract Addresses (ETH Sepolia)

| Contract | Address | Handler |
|----------|---------|---------|
| IdentityRegistry | `0x8004A818BFB912233c491871b3d84c89A494BD9e` | agent0-py SDK |
| ReputationRegistry | `0x8004B663056A597Dffe9eCcC1965A193B7388713` | agent0-py SDK |
| TEERegistry | `0x034675a9541445087Cd73B2120d6c8AF7F2056E3` | Custom `tee_verifier.py` |
| TEE Verifier | `0x27F8C122618b05420c2f67A9464415586C30D18B` | Custom `tee_verifier.py` |

## Subgraph

**Endpoint**: `https://gateway.thegraph.com/api/subgraphs/id/6wQRC7geo9XYAhckfmfo8kbMRLeWU8KQd3XsJqFKmZLT`

## Architecture

### Layer 1: TEE Foundation (Unchanged)
- `tee_auth.py` - dstack-sdk key derivation and attestation generation
- `tee_verifier.py` - TEERegistry contract interactions (updated addresses only)

### Layer 2: Registry & Reputation (NEW - agent0-py SDK)
- Replace custom `registry.py` with agent0-py `SDK` class
- Use `Agent` class for lifecycle management
- Use `FeedbackManager` for reputation operations
- Use direct GraphQL for subgraph queries

### Layer 3: Application Logic (Minimal Changes)
- `ServerAgent` adapts to new SDK
- Agent card includes reputation data
- Existing endpoints preserved

## File Changes

### Files to MODIFY

| File | Change |
|------|--------|
| `requirements.txt` | Add `agent0-sdk`, `gql[aiohttp]` |
| `src/agent/registry.py` | Replace with agent0-py SDK wrapper |
| `src/agent/agent_card.py` | Add reputation data from subgraph |
| `src/agent/tee_verifier.py` | Update contract addresses only |
| `deployment/local_agent_server.py` | Use new SDK + subgraph |
| `.env.example` | New addresses, add subgraph URL |
| `agent_config.json` | New ERC-8004 format with reputation |

### Files to CREATE

| File | Purpose |
|------|---------|
| `src/agent/subgraph_client.py` | Direct GraphQL queries |
| `src/agent/chain_config.py` | Multi-chain ready configuration |

### Files UNCHANGED
- `src/agent/tee_auth.py`
- `src/agent/base.py`
- `src/agent/eip712.py`
- All contract `.sol` files

## Chain Configuration

```python
# src/agent/chain_config.py
CHAIN_CONFIGS = {
    "eth-sepolia": {
        "chain_id": 11155111,
        "rpc_url": "https://1rpc.io/sepolia",
        "subgraph_url": "https://gateway.thegraph.com/api/subgraphs/id/6wQRC7geo9XYAhckfmfo8kbMRLeWU8KQd3XsJqFKmZLT",
        "contracts": {
            "identity_registry": "0x8004A818BFB912233c491871b3d84c89A494BD9e",
            "reputation_registry": "0x8004B663056A597Dffe9eCcC1965A193B7388713",
            "tee_registry": "0x034675a9541445087Cd73B2120d6c8AF7F2056E3",
            "tee_verifier": "0x27F8C122618b05420c2f67A9464415586C30D18B",
        }
    }
    # Future: add "base-mainnet", "arbitrum", etc.
}
```

## ERC-8004 Registration Format

```json
{
  "type": "agent-registration-v1",
  "metadata": {
    "name": "TEE Agent",
    "description": "Trustless AI agent with Intel TDX attestation",
    "image": "https://your-domain/agent-image.png"
  },
  "services": {
    "a2a": {
      "enabled": true,
      "endpoint": "https://{domain}/.well-known/agent.json",
      "version": "0.3.0"
    },
    "mcp": {
      "enabled": false,
      "endpoint": "",
      "version": "2025-06-18"
    },
    "agentWallet": {
      "eip155:11155111": "{agent_address}"
    }
  },
  "capabilities": {
    "oasf": "0.8.0",
    "domains": ["infrastructure"],
    "skills": ["tee-attestation", "secure-computation"]
  },
  "trust": {
    "supportedTrust": ["tee-attestation", "reputation"],
    "teeAttestation": true,
    "reputation": true
  },
  "registration": {
    "agentId": null,
    "agentRegistry": "eip155:11155111:0x8004A818BFB912233c491871b3d84c89A494BD9e"
  },
  "status": {
    "active": true,
    "x402": false
  }
}
```

## Reputation Feedback Format

```python
feedback = {
    "tag1": "reliability",      # Measurement dimension
    "tag2": "uptime",           # Sub-dimension
    "value": 9850,              # 98.50% as integer
    "valueDecimals": 2,         # Decimal places
    "uri": "ipfs://...",        # Optional rich context
    "uriHash": "0x..."          # Integrity hash
}
```

## Data Flow

### Registration (Write Path)
```
User Request → ServerAgent → agent0-py SDK.Agent.register()
                                ↓
                           IdentityRegistry Contract (ETH Sepolia)
                                ↓
                           NFT minted with tokenId
                                ↓
                           IPFS upload (agent metadata)
                                ↓
                           setAgentUri() links NFT → IPFS
                                ↓
                           TEE signs confirmation (dstack layer)
```

### Reputation Submission (Write Path)
```
Feedback Request → ServerAgent → agent0-py FeedbackManager.giveFeedback()
                                      ↓
                                 ReputationRegistry Contract
                                      ↓
                                 Event emitted
                                      ↓
                                 Subgraph indexes (automatic)
```

### Data Query (Read Path - Fast)
```
Status Check → ServerAgent → Direct GraphQL to Subgraph
                                  ↓
                             Query: agent by ID, reputation stats
                                  ↓
                             Cached indexed data (milliseconds)
```

## Migration Phases

### Phase 1: Foundation (No Breaking Changes)
1. Add `agent0-sdk` and `gql[aiohttp]` to `requirements.txt`
2. Create `src/agent/chain_config.py` with ETH Sepolia config
3. Create `src/agent/subgraph_client.py` with GraphQL queries
4. Update `.env.example` with new contract addresses and subgraph URL

### Phase 2: Registry Migration
5. Refactor `src/agent/registry.py` to wrap agent0-py SDK
6. Keep old methods as fallbacks during transition
7. Update `tee_verifier.py` contract addresses (TEE layer unchanged)
8. Test registration flow against ETH Sepolia

### Phase 3: Reputation Integration
9. Add reputation queries to subgraph client
10. Add reputation submission via agent0-py FeedbackManager
11. Update `agent_config.json` to new ERC-8004 format
12. Add `/.well-known/agent-registration.json` endpoint

### Phase 4: Server Integration
13. Update `deployment/local_agent_server.py` to use new SDK
14. Update `src/agent/agent_card.py` to include reputation data
15. Remove old Base Sepolia references from code and docs

### Phase 5: Cleanup & Documentation
16. Remove deprecated code paths
17. Update README.md with ETH Sepolia details
18. Update DEPLOYMENT.md with new workflow

## Error Handling

### Subgraph Fallback Strategy
- If subgraph query fails → fall back to RPC calls via SDK
- Cache subgraph responses with TTL (e.g., 30 seconds)
- Log subgraph errors but don't fail user requests

### Transaction Handling
- Keep existing retry logic for failed transactions
- Add nonce management for concurrent operations
- Surface clear errors for insufficient funds

### Chain Config Validation
- Validate chain config on startup
- Fail fast if contract addresses missing
- Log active chain configuration

## Subgraph Queries

Key queries to implement in `subgraph_client.py`:

```graphql
# Get agent by ID
query GetAgent($agentId: String!) {
  agent(id: $agentId) {
    id
    owner
    tokenURI
    createdAt
    updatedAt
  }
}

# Get agent reputation
query GetReputation($agentId: String!) {
  agentStats(id: $agentId) {
    feedbackCount
    averageScore
  }
  feedbacks(where: { agent: $agentId }, first: 10, orderBy: timestamp, orderDirection: desc) {
    id
    tag1
    tag2
    value
    valueDecimals
    reviewer
    timestamp
  }
}

# Find agent by owner address
query GetAgentByOwner($owner: String!) {
  agents(where: { owner: $owner }) {
    id
    tokenURI
  }
}
```

## New Endpoint

Add to `deployment/local_agent_server.py`:

```python
@app.get("/.well-known/agent-registration.json")
async def agent_registration():
    """Domain verification endpoint (ERC-8004 best practice)."""
    return JSONResponse(content=agent.get_registration_file())
```
