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

    @property
    def caip2_chain_id(self) -> str:
        """Return CAIP-2 format chain identifier (e.g., eip155:11155111)."""
        return f"eip155:{self.chain_id}"

    def agent_registry_caip10(self) -> str:
        """Return CAIP-10 format for agentRegistry field."""
        return f"eip155:{self.chain_id}:{self.identity_registry}"


# Subgraph ID for ERC-8004 on Sepolia
SUBGRAPH_ID = "6wQRC7geo9XYAhckfmfo8kbMRLeWU8KQd3XsJqFKmZLT"


def get_subgraph_url(api_key: str = None) -> str:
    """
    Get subgraph URL with optional API key.

    The Graph Gateway requires an API key in the URL path:
    https://gateway.thegraph.com/api/{api-key}/subgraphs/id/{subgraph-id}

    If no API key is provided, returns URL that will fail with auth error.
    """
    api_key = api_key or os.getenv("SUBGRAPH_API_KEY", "")
    if api_key:
        return f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{SUBGRAPH_ID}"
    # Fallback URL without API key (will fail with auth error)
    return f"https://gateway.thegraph.com/api/subgraphs/id/{SUBGRAPH_ID}"


# Chain configurations - add new chains here
CHAIN_CONFIGS: Dict[str, ChainConfig] = {
    "eth-sepolia": ChainConfig(
        chain_id=11155111,
        rpc_url="https://1rpc.io/sepolia",
        subgraph_url=get_subgraph_url(),  # Will use SUBGRAPH_API_KEY env var
        identity_registry="0x8004A818BFB912233c491871b3d84c89A494BD9e",
        reputation_registry="0x8004B663056A597Dffe9eCcC1965A193B7388713",
    ),
    # Future chains - uncomment and configure as needed:
    # "base-mainnet": ChainConfig(
    #     chain_id=8453,
    #     rpc_url="https://mainnet.base.org",
    #     subgraph_url="https://...",
    #     identity_registry="0x...",
    #     reputation_registry="0x...",
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
