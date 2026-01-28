"""
Chain Configuration for ERC-8004 Agent

Multi-chain ready configuration. Add new chains by adding entries to CHAIN_CONFIGS.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ChainConfig:
    """Configuration for a specific blockchain network."""
    chain_id: int
    rpc_url: str
    subgraph_url: str
    identity_registry: str
    reputation_registry: str
    tee_registry: str
    tee_verifier: str

    @property
    def caip2_chain_id(self) -> str:
        """Return CAIP-2 format chain identifier (e.g., eip155:11155111)."""
        return f"eip155:{self.chain_id}"

    def agent_registry_caip10(self) -> str:
        """Return CAIP-10 format for agentRegistry field."""
        return f"eip155:{self.chain_id}:{self.identity_registry}"


# Chain configurations - add new chains here
CHAIN_CONFIGS: Dict[str, ChainConfig] = {
    "eth-sepolia": ChainConfig(
        chain_id=11155111,
        rpc_url="https://1rpc.io/sepolia",
        subgraph_url="https://gateway.thegraph.com/api/subgraphs/id/6wQRC7geo9XYAhckfmfo8kbMRLeWU8KQd3XsJqFKmZLT",
        identity_registry="0x8004A818BFB912233c491871b3d84c89A494BD9e",
        reputation_registry="0x8004B663056A597Dffe9eCcC1965A193B7388713",
        tee_registry="0x034675a9541445087Cd73B2120d6c8AF7F2056E3",
        tee_verifier="0x27F8C122618b05420c2f67A9464415586C30D18B",
    ),
    # Future chains - uncomment and configure as needed:
    # "base-mainnet": ChainConfig(
    #     chain_id=8453,
    #     rpc_url="https://mainnet.base.org",
    #     subgraph_url="https://...",
    #     identity_registry="0x...",
    #     reputation_registry="0x...",
    #     tee_registry="0x...",
    #     tee_verifier="0x...",
    # ),
}

# Default chain
DEFAULT_CHAIN = "eth-sepolia"


def get_chain_config(chain_name: Optional[str] = None) -> ChainConfig:
    """
    Get chain configuration by name or from environment.

    Args:
        chain_name: Chain name (e.g., 'eth-sepolia'). If None, uses CHAIN_NAME env var or default.

    Returns:
        ChainConfig for the specified chain.

    Raises:
        ValueError: If chain name is not found in CHAIN_CONFIGS.
    """
    if chain_name is None:
        chain_name = os.getenv("CHAIN_NAME", DEFAULT_CHAIN)

    if chain_name not in CHAIN_CONFIGS:
        available = ", ".join(CHAIN_CONFIGS.keys())
        raise ValueError(f"Unknown chain '{chain_name}'. Available: {available}")

    return CHAIN_CONFIGS[chain_name]


def get_chain_config_from_env() -> ChainConfig:
    """
    Get chain configuration with environment variable overrides.

    Environment variables can override specific values:
    - CHAIN_NAME: Select which chain config to use
    - RPC_URL: Override RPC endpoint
    - SUBGRAPH_URL: Override subgraph endpoint
    - IDENTITY_REGISTRY_ADDRESS: Override identity registry address
    - REPUTATION_REGISTRY_ADDRESS: Override reputation registry address
    - TEE_REGISTRY_ADDRESS: Override TEE registry address
    - TEE_VERIFIER_ADDRESS: Override TEE verifier address

    Returns:
        ChainConfig with any environment overrides applied.
    """
    chain_name = os.getenv("CHAIN_NAME", DEFAULT_CHAIN)
    base_config = get_chain_config(chain_name)

    # Apply environment overrides
    return ChainConfig(
        chain_id=int(os.getenv("CHAIN_ID", str(base_config.chain_id))),
        rpc_url=os.getenv("RPC_URL", base_config.rpc_url),
        subgraph_url=os.getenv("SUBGRAPH_URL", base_config.subgraph_url),
        identity_registry=os.getenv("IDENTITY_REGISTRY_ADDRESS", base_config.identity_registry),
        reputation_registry=os.getenv("REPUTATION_REGISTRY_ADDRESS", base_config.reputation_registry),
        tee_registry=os.getenv("TEE_REGISTRY_ADDRESS", base_config.tee_registry),
        tee_verifier=os.getenv("TEE_VERIFIER_ADDRESS", base_config.tee_verifier),
    )


def validate_chain_config(config: ChainConfig) -> None:
    """
    Validate chain configuration on startup.

    Args:
        config: ChainConfig to validate.

    Raises:
        ValueError: If any required field is missing or invalid.
    """
    errors = []

    if not config.chain_id:
        errors.append("chain_id is required")
    if not config.rpc_url:
        errors.append("rpc_url is required")
    if not config.identity_registry or not config.identity_registry.startswith("0x"):
        errors.append("identity_registry must be a valid address")
    if not config.reputation_registry or not config.reputation_registry.startswith("0x"):
        errors.append("reputation_registry must be a valid address")
    if not config.tee_registry or not config.tee_registry.startswith("0x"):
        errors.append("tee_registry must be a valid address")
    if not config.tee_verifier or not config.tee_verifier.startswith("0x"):
        errors.append("tee_verifier must be a valid address")

    if errors:
        raise ValueError(f"Invalid chain config: {', '.join(errors)}")


def log_chain_config(config: ChainConfig) -> None:
    """Log active chain configuration for debugging."""
    print(f"Chain Configuration:")
    print(f"  Chain ID: {config.chain_id} ({config.caip2_chain_id})")
    print(f"  RPC URL: {config.rpc_url}")
    print(f"  Subgraph URL: {config.subgraph_url[:50]}..." if config.subgraph_url else "  Subgraph URL: None")
    print(f"  Identity Registry: {config.identity_registry}")
    print(f"  Reputation Registry: {config.reputation_registry}")
    print(f"  TEE Registry: {config.tee_registry}")
    print(f"  TEE Verifier: {config.tee_verifier}")
