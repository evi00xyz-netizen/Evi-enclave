# ERC-8004 TEE Agent Template

Build trustless AI agents with [dstack](https://github.com/dstack-tee/dstack), ERC-8004 compliance, and seamless deployment on Phala Cloud.

## Features

- 🔐 **TEE-Derived Keys** - Intel TDX attestation via dstack CVM on Phala Cloud
- 🌐 **ERC-8004 Compliant** - Standard `/agent.json` endpoint
- 📜 **Real TEE Attestation** - Cryptographic proof of execution
- 🔗 **On-Chain Registry** - Decentralized agent discovery
- 🤖 **A2A Protocol** - Agent-to-Agent communication
- 🔧 **Config-Driven** - Easy customization via `agent_config.json`
- 🧪 **VibeVM Ready** - Local development environment

## Quick Start

### For Local Development (VibeVM)

1. **Fork or use this template**

   Click "Use this template" on GitHub or fork this repository

2. **Start VibeVM and clone**

   ```bash
   # Inside your VibeVM environment
   git clone https://github.com/YOUR_USERNAME/erc-8004-tee-agent.git
   cd erc-8004-tee-agent
   ```

3. **Configure environment**

   ```bash
   cp .env.local.example .env
   # Edit .env with your settings
   ```

4. **Install and run**

   ```bash
   pip3 install -e .
   python3 deployment/local_agent_server.py
   ```

5. **Test your agent**

   Open http://localhost:8000

### For Production Deployment (Phala CVM)

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions.

```bash
# 1. Commit your production code
git commit -m "Production ready"
git push origin main

# 2. Note your commit hash
git rev-parse HEAD

# 3. Deploy on phala.com with docker-compose.yml
# 4. Set secrets: GITHUB_REPO, GIT_COMMIT_HASH, AGENT_SALT
# 5. Launch CVM and fund your agent
npx phala deploy -n erc-8004-tee-agent -c docker-compose.yml -e .env
```

## Developer Workflow

```mermaid
graph LR
    A[Fork Template] --> B[Clone to VibeVM]
    B --> C[Local Development]
    C --> D[Test & Iterate]
    D --> E[Commit to GitHub]
    E --> F[Deploy on Phala]
    F --> G[Fund & Register]
    G --> H[Production Agent Live]
```

**Detailed steps:**

1. **Fork/Template** - Create your repository from this template
2. **VibeVM Development** - Clone into VibeVM for local testing
3. **Customize** - Edit `agent_config.json` and add your logic
4. **Test Locally** - Run agent in VibeVM, test registration flow
5. **Commit** - Push production-ready code to GitHub
6. **Deploy** - Use `docker-compose.yml` on Phala with your commit hash
7. **Launch** - Fund wallet, register on-chain, validate TEE

## Project Structure

```
erc-8004-tee-agent/
├── agent_config.json          # Agent metadata & capabilities
├── entrypoint.sh              # Build & deploy script (customize this!)
├── docker-compose.yml         # Production deployment config
├── .env.example               # Production environment template
├── .env.local.example         # Local development template
├── DEV_GUIDE.md              # Comprehensive developer guide
├── DEPLOYMENT.md             # Production deployment checklist
├── contracts/                 # Solidity contracts
├── src/agent/                 # Core agent logic
│   ├── tee_auth.py           # TEE key derivation & auth
│   ├── tee_verifier.py       # TEE attestation submission
│   ├── agent_card.py         # ERC-8004 card builders
│   ├── registry.py           # On-chain registry client
│   └── base.py               # Base agent functionality
├── deployment/
│   └── local_agent_server.py # FastAPI server
└── static/                    # Web UI assets
```

## Architecture

```
┌─────────────┐
│   Wallet    │ Fund with ETH Sepolia ETH
└─────────────┘
       ↓
┌─────────────┐
│  Register   │ Identity Registry (on-chain)
└─────────────┘
       ↓
┌─────────────┐
│ TEE Verify  │ Attestation + Code Measurement
└─────────────┘
       ↓
┌─────────────┐
│    Ready    │ A2A endpoints active
└─────────────┘
```

## API Endpoints

- `GET /agent.json` - ERC-8004 registration-v1 format
- `GET /.well-known/agent-card.json` - A2A agent card
- `GET /api/status` - Agent status
- `POST /api/register` - Register on-chain
- `POST /api/tee/register` - Register TEE key
- `POST /api/metadata/update` - Update on-chain metadata
- `POST /tasks` - A2A task submission
- `GET /tasks/{id}` - Task status
- `GET /.well-known/agent-registration.json` - Domain verification (ERC-8004)
- `GET /api/reputation` - Agent reputation data

## Deployed Contracts

**ETH Sepolia:**
- IdentityRegistry: `0x8004A818BFB912233c491871b3d84c89A494BD9e`
- ReputationRegistry: `0x8004B663056A597Dffe9eCcC1965A193B7388713`
- TEERegistry: `0x034675a9541445087Cd73B2120d6c8AF7F2056E3`
- TEE Verifier: `0x27F8C122618b05420c2f67A9464415586C30D18B`

## Configuration

**`.env`** - Runtime config:
```bash
AGENT_DOMAIN=your-domain.com
AGENT_SALT=unique-salt
CHAIN_NAME=eth-sepolia
IDENTITY_REGISTRY_ADDRESS=0x8004A818BFB912233c491871b3d84c89A494BD9e
REPUTATION_REGISTRY_ADDRESS=0x8004B663056A597Dffe9eCcC1965A193B7388713
TEE_REGISTRY_ADDRESS=0x034675a9541445087Cd73B2120d6c8AF7F2056E3
SUBGRAPH_URL=https://gateway.thegraph.com/api/subgraphs/id/6wQRC7geo9XYAhckfmfo8kbMRLeWU8KQd3XsJqFKmZLT
```

**`agent_config.json`** - Agent metadata (ERC-8004 format):
```json
{
  "type": "agent-registration-v1",
  "metadata": {
    "name": "Your Agent",
    "description": "Agent description"
  },
  "services": {
    "a2a": {"enabled": true, "version": "0.3.0"},
    "mcp": {"enabled": false}
  },
  "trust": {
    "supportedTrust": ["tee-attestation", "reputation"]
  },
  "evmChains": [
    {"name": "Ethereum-Sepolia", "chainId": 11155111}
  ]
}
```

## Customization

Edit `agent_config.json` to add endpoints:

**Add MCP:**
```json
"mcp": {
  "enabled": true,
  "endpoint": "https://mcp.agent.eth/",
  "version": "2025-06-18"
}
```

**Add chains:**
```json
{"name": "Polygon", "chainId": 137}
```

**Add trust models:**
```json
"supportedTrust": ["tee-attestation", "reputation"]
```

## Documentation

- **[DEV_GUIDE.md](DEV_GUIDE.md)** - Comprehensive developer guide covering:
  - Local development with VibeVM
  - Customizing your agent
  - Testing and debugging
  - Production deployment workflow

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment checklist:
  - Pre-deployment requirements
  - Phala CVM configuration
  - Post-deployment validation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 3 minutes

## How It Works

1. **Key Derivation** - TEE derives wallet from `domain + salt`
2. **Local Development** - Test in VibeVM with simulated TEE
3. **Funding** - Add ETH Sepolia ETH to derived wallet
4. **Registration** - Register agent on-chain via IdentityRegistry
5. **TEE Attestation** - Submit cryptographic proof to TEE verifier
6. **Reputation** - Build trust via on-chain feedback
7. **Production** - Deploy to Phala CVM with real TEE attestation
8. **Agent Live** - Accessible at `/agent.json` endpoint

## Tech Stack

- **TEE**: Intel TDX via Phala CVM/dstack
- **Blockchain**: ETH Sepolia (testnet) - multi-chain ready via config
- **Backend**: Python 3, FastAPI
- **Contracts**: Solidity ^0.8.20 (ERC-8004 standard)
- **Data**: The Graph subgraph for fast queries
- **Development**: VibeVM for local testing
- **Deployment**: Docker, Phala Cloud

## ERC-8004 Compliance

✅ Standard `/agent.json` endpoint (registration-v1)
✅ CAIP-10 wallet address format
✅ A2A protocol endpoints
✅ TEE attestation support
✅ On-chain registry integration
✅ Verifiable code measurement

## Customization

### Agent Metadata

Edit [agent_config.json](agent_config.json):

```json
{
  "name": "Your Agent Name",
  "description": "What your agent does",
  "endpoints": {
    "a2a": {"enabled": true},
    "mcp": {"enabled": false}
  }
}
```

### Agent Logic

Modify files in [src/agent/](src/agent/):

- Add custom endpoints in `deployment/local_agent_server.py`
- Implement custom logic in `src/agent/base.py`
- Configure blockchain interactions in `src/agent/registry.py`

### Build Process

Update [entrypoint.sh](entrypoint.sh) for custom setup:

```bash
# Add model downloads, DB initialization, etc.
echo "🤖 Downloading ML model..."
wget https://example.com/model.bin -O /app/model.bin
```

See [DEV_GUIDE.md](DEV_GUIDE.md) for detailed customization instructions.

## Deployment Checklist

Before deploying to production:

- [ ] Test thoroughly in VibeVM
- [ ] Update `agent_config.json` with production values
- [ ] Ensure `entrypoint.sh` has all required setup steps
- [ ] Commit production code to GitHub
- [ ] Note commit hash for deployment
- [ ] Set secrets on Phala: `GITHUB_REPO`, `GIT_COMMIT_HASH`, `AGENT_SALT`
- [ ] Configure CVM (2+ CPU, 4GB+ RAM, 10GB+ storage)
- [ ] Fund agent wallet with ETH Sepolia ETH

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete checklist.

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/erc-8004-tee-agent/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/erc-8004-tee-agent/discussions)
- **Phala Discord**: [discord.gg/phala](https://discord.gg/phala)
- **VibeVM Docs**: [github.com/Phala-Network/VibeVM](https://github.com/Phala-Network/VibeVM)

## License

MIT

## Links

- **ERC-8004 Spec**: [eips.ethereum.org/EIPS/eip-8004](https://eips.ethereum.org/EIPS/eip-8004)
- **Phala Network**: [phala.network](https://phala.network)
- **VibeVM**: [github.com/Phala-Network/VibeVM](https://github.com/Phala-Network/VibeVM)
- **ETH Sepolia Explorer**: [sepolia.etherscan.io](https://sepolia.etherscan.io)
- **Agent0 SDK**: [github.com/agent0lab/agent0-py](https://github.com/agent0lab/agent0-py)
- **Subgraph**: [github.com/agent0lab/subgraph](https://github.com/agent0lab/subgraph)

---

**Ready to build?** Start with [DEV_GUIDE.md](DEV_GUIDE.md) or jump into [QUICKSTART.md](QUICKSTART.md) 🚀
