"""
ERC-8004 Registry Client

Handles all interactions with the ERC-8004 registry contracts.
Uses chain_config for addresses and subgraph for fast reads.
"""

import json
from typing import Dict, Any, Optional, List
from web3 import Web3
from eth_account import Account

from .chain_config import ChainConfig, get_chain_config_from_env
from .subgraph_client import SubgraphClient


class RegistryClient:
    """
    Client for interacting with ERC-8004 registry contracts.

    Uses:
    - chain_config for contract addresses (multi-chain ready)
    - subgraph for fast read operations
    - web3.py for write operations (transactions)
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        chain_id: Optional[int] = None,
        registries: Optional[Dict[str, str]] = None,
        account: Optional[Account] = None,
        config: Optional[ChainConfig] = None,
        use_subgraph: bool = True
    ):
        """
        Initialize registry client.

        Args:
            rpc_url: Blockchain RPC endpoint (optional if config provided)
            chain_id: Chain ID for the network (optional if config provided)
            registries: Dictionary with registry addresses (optional if config provided)
            account: Account for signing transactions
            config: Chain configuration (if None, loads from environment)
            use_subgraph: Whether to use subgraph for read operations (default: True)
        """
        # Load chain config if not provided
        if config is None:
            config = get_chain_config_from_env()
        self.config = config

        # Use config values, allow overrides for backward compatibility
        self.rpc_url = rpc_url or config.rpc_url
        self.chain_id = chain_id or config.chain_id

        # Build registries dict from config if not provided
        if registries is None:
            self.registries = {
                'identity': config.identity_registry,
                'reputation': config.reputation_registry,
            }
        else:
            self.registries = registries

        self.account = account

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {self.rpc_url}")

        # Initialize subgraph client for fast reads
        self.use_subgraph = use_subgraph
        if use_subgraph:
            self.subgraph = SubgraphClient(config=config)
        else:
            self.subgraph = None

        # Load contract ABIs
        self._load_abis()

        # Initialize contract instances
        self._init_contracts()

        print(f"RegistryClient initialized for chain {self.chain_id}")
        print(f"  Identity Registry: {self.registries['identity']}")
        print(f"  Reputation Registry: {self.registries['reputation']}")
        print(f"  Subgraph enabled: {use_subgraph}")

    def _load_abis(self):
        """Load contract ABIs."""
        self.identity_abi = [
            {
                "inputs": [],
                "name": "register",
                "outputs": [{"name": "agentId", "type": "uint256"}],
                "type": "function",
                "stateMutability": "nonpayable"
            },
            {
                "inputs": [{"name": "tokenUri", "type": "string"}],
                "name": "register",
                "outputs": [{"name": "agentId", "type": "uint256"}],
                "type": "function",
                "stateMutability": "nonpayable"
            },
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "ownerOf",
                "outputs": [{"name": "", "type": "address"}],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [{"name": "owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [{"name": "agentId", "type": "uint256"}],
                "name": "tokenURI",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [{"name": "owner", "type": "address"}, {"name": "index", "type": "uint256"}],
                "name": "tokenOfOwnerByIndex",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "key", "type": "string"},
                    {"name": "value", "type": "bytes"}
                ],
                "name": "setMetadata",
                "outputs": [],
                "type": "function",
                "stateMutability": "nonpayable"
            },
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "key", "type": "string"}
                ],
                "name": "getMetadata",
                "outputs": [{"name": "value", "type": "bytes"}],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "newUri", "type": "string"}
                ],
                "name": "setAgentUri",
                "outputs": [],
                "type": "function",
                "stateMutability": "nonpayable"
            }
        ]

        self.reputation_abi = [
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "tag1", "type": "string"},
                    {"name": "tag2", "type": "string"},
                    {"name": "value", "type": "int256"},
                    {"name": "valueDecimals", "type": "uint8"},
                    {"name": "uri", "type": "string"},
                    {"name": "uriHash", "type": "bytes32"}
                ],
                "name": "giveFeedback",
                "outputs": [],
                "type": "function",
                "stateMutability": "nonpayable"
            },
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "clientAddress", "type": "address"},
                    {"name": "index", "type": "uint64"}
                ],
                "name": "readFeedback",
                "outputs": [
                    {"name": "tag1", "type": "string"},
                    {"name": "tag2", "type": "string"},
                    {"name": "value", "type": "int256"},
                    {"name": "valueDecimals", "type": "uint8"},
                    {"name": "uri", "type": "string"},
                    {"name": "uriHash", "type": "bytes32"},
                    {"name": "timestamp", "type": "uint256"}
                ],
                "type": "function",
                "stateMutability": "view"
            },
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "clientAddresses", "type": "address[]"},
                    {"name": "tag1", "type": "string"},
                    {"name": "tag2", "type": "string"}
                ],
                "name": "getSummary",
                "outputs": [
                    {"name": "count", "type": "uint256"},
                    {"name": "averageScore", "type": "int256"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]

    def _init_contracts(self):
        """Initialize contract instances."""
        self.identity_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.registries['identity']),
            abi=self.identity_abi
        )

        self.reputation_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.registries['reputation']),
            abi=self.reputation_abi
        )

    async def check_agent_registration(
        self,
        domain: str = None,
        agent_address: str = None,
        agent_id: int = None
    ) -> Dict[str, Any]:
        """
        Check if agent is registered (owns an NFT).

        Uses subgraph for fast lookup if available, falls back to RPC.

        Args:
            domain: Unused (kept for compatibility)
            agent_address: Agent's Ethereum address
            agent_id: Optional known agent ID for fast verification

        Returns:
            Dict with registration info or {"registered": False}
        """
        # Try subgraph first (fast path)
        if self.subgraph and agent_address:
            agent_data = await self.subgraph.get_agent_by_owner(agent_address)
            if agent_data:
                print(f"✅ Found agent via subgraph: ID {agent_data['id']}")
                return {
                    "registered": True,
                    "agent_id": int(agent_data['id']),
                    "agent_address": agent_address
                }

        # FAST PATH: If we know the agent_id, use direct verification (1 RPC call)
        if agent_id is not None:
            print(f"🚀 Using fast path verification for agent ID {agent_id}")
            result = await self.verify_agent_by_id(agent_id, agent_address)
            if result["verified"]:
                return {
                    "registered": True,
                    "agent_id": agent_id,
                    "agent_address": result["owner"]
                }
            else:
                print(f"⚠️  Fast verification failed, falling back to slow path")

        # SLOW PATH: RPC-based lookup
        try:
            if agent_address:
                checksum_address = Web3.to_checksum_address(agent_address)
                print(f"🔍 Checking registration for: {checksum_address}")

                balance = self.identity_contract.functions.balanceOf(checksum_address).call()
                print(f"🔍 NFT Balance: {balance}")

                if balance > 0:
                    try:
                        token_id = self.identity_contract.functions.tokenOfOwnerByIndex(checksum_address, 0).call()
                        print(f"✅ Found agent ID {token_id} for address {checksum_address}")
                        return {
                            "registered": True,
                            "agent_id": token_id,
                            "agent_address": agent_address
                        }
                    except Exception as token_err:
                        print(f"⚠️  Error getting token by index: {token_err}")
                        # Fallback: brute force search
                        print(f"🔍 Attempting brute force search for token ID...")
                        for potential_id in range(1, 1000):
                            try:
                                owner = self.identity_contract.functions.ownerOf(potential_id).call()
                                if owner.lower() == checksum_address.lower():
                                    print(f"✅ Found agent ID {potential_id} via brute force")
                                    return {
                                        "registered": True,
                                        "agent_id": potential_id,
                                        "agent_address": agent_address
                                    }
                            except:
                                continue

                        return {
                            "registered": True,
                            "agent_id": None,
                            "agent_address": agent_address
                        }
                else:
                    print(f"⚠️  Address has no NFTs (balance: 0)")
        except Exception as e:
            print(f"⚠️  Registration check error: {e}")
            import traceback
            traceback.print_exc()

        return {"registered": False}

    async def register_agent(
        self,
        domain: str,
        agent_address: str,
        agent_card: Dict[str, Any] = None,
        wait_for_receipt: bool = True
    ) -> Dict[str, Any]:
        """
        Register agent by minting ERC-721 NFT.

        Args:
            domain: Agent's domain (used to build tokenURI)
            agent_address: Unused (msg.sender gets NFT)
            agent_card: Unused
            wait_for_receipt: If True, wait for confirmation and return agent_id.

        Returns:
            Dict with either {'agent_id': int} or {'tx_hash': str, 'agent_address': str}
        """
        if not self.account:
            raise ValueError("Account required")

        # Check if already registered
        check = await self.check_agent_registration(agent_address=self.account.address)
        if check["registered"]:
            print(f"✅ Already registered with Agent ID: {check['agent_id']}")
            return {"agent_id": check["agent_id"], "already_registered": True}

        # Build tokenURI pointing to /agent.json
        token_uri = f"https://{domain}/agent.json"

        tx = self.identity_contract.functions.register(token_uri).build_transaction({
            'chainId': self.chain_id,
            'gas': 300000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Registration tx: {tx_hash.hex()}")

        if not wait_for_receipt:
            return {
                "tx_hash": tx_hash.hex(),
                "agent_address": self.account.address
            }

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Registration failed: tx={tx_hash.hex()}")

        # Get agent ID from logs
        if receipt['logs'] and len(receipt['logs'][0]['topics']) >= 4:
            agent_id = int(receipt['logs'][0]['topics'][3].hex(), 16)
        else:
            balance = self.identity_contract.functions.balanceOf(self.account.address).call()
            if balance > 0:
                agent_id = self.identity_contract.functions.tokenOfOwnerByIndex(
                    self.account.address,
                    balance - 1
                ).call()
            else:
                raise RuntimeError("Registration succeeded but couldn't determine agent ID")

        print(f"✅ Registered with Agent ID: {agent_id}")
        return {"agent_id": agent_id, "tx_hash": tx_hash.hex()}

    async def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction status and extract agent_id if confirmed."""
        try:
            if isinstance(tx_hash, str):
                tx_hash_bytes = bytes.fromhex(tx_hash.replace('0x', ''))
            else:
                tx_hash_bytes = tx_hash

            receipt = self.w3.eth.get_transaction_receipt(tx_hash_bytes)

            if receipt is None:
                return {"status": "pending", "confirmed": False}

            if receipt.status != 1:
                return {"status": "failed", "confirmed": True, "success": False}

            agent_id = None
            if receipt['logs'] and len(receipt['logs'][0]['topics']) >= 4:
                agent_id = int(receipt['logs'][0]['topics'][3].hex(), 16)

            return {
                "status": "confirmed",
                "confirmed": True,
                "success": True,
                "agent_id": agent_id,
                "block_number": receipt.blockNumber
            }

        except Exception as e:
            return {"status": "pending", "confirmed": False, "error": str(e)}

    async def verify_agent_by_id(
        self,
        agent_id: int,
        expected_address: str = None
    ) -> Dict[str, Any]:
        """Fast verification using known agent_id."""
        try:
            owner = self.identity_contract.functions.ownerOf(agent_id).call()

            verified = True
            if expected_address:
                checksum_expected = Web3.to_checksum_address(expected_address)
                verified = owner.lower() == checksum_expected.lower()

            token_uri = self.identity_contract.functions.tokenURI(agent_id).call()

            print(f"✅ Fast verification: Agent ID {agent_id} owned by {owner}")

            return {
                "verified": verified,
                "agent_id": agent_id,
                "owner": owner,
                "token_uri": token_uri
            }
        except Exception as e:
            print(f"⚠️  Fast verification failed for agent ID {agent_id}: {e}")
            return {"verified": False, "error": str(e)}

    async def give_feedback(
        self,
        agent_id: int,
        tag1: str,
        tag2: str,
        value: int,
        value_decimals: int = 2,
        uri: str = "",
        uri_hash: bytes = b'\x00' * 32
    ) -> str:
        """
        Submit feedback to the Reputation Registry (ERC-8004 format).

        Args:
            agent_id: ID of agent being rated
            tag1: Primary measurement dimension (e.g., "reliability")
            tag2: Secondary dimension (e.g., "uptime")
            value: Feedback value as integer (e.g., 9850 for 98.50%)
            value_decimals: Decimal places for value interpretation
            uri: Optional IPFS URI for rich feedback context
            uri_hash: Integrity hash for URI content

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for feedback submission")

        tx = self.reputation_contract.functions.giveFeedback(
            agent_id,
            tag1,
            tag2,
            value,
            value_decimals,
            uri,
            uri_hash
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Feedback tx: {tx_hash.hex()}")
        return tx_hash.hex()

    async def get_reputation(self, agent_id: int) -> Dict[str, Any]:
        """
        Get agent reputation.

        Uses subgraph for fast lookup if available, falls back to RPC.

        Args:
            agent_id: Agent ID to lookup

        Returns:
            Reputation information
        """
        # Try subgraph first (fast)
        if self.subgraph:
            rep_data = await self.subgraph.get_agent_reputation(str(agent_id))
            if "error" not in rep_data:
                return rep_data

        # Fall back to RPC
        try:
            result = self.reputation_contract.functions.getSummary(
                agent_id,
                [],  # No client address filter (empty array)
                "",  # No tag1 filter
                ""   # No tag2 filter
            ).call()

            return {
                "feedbackCount": result[0],
                "averageScore": result[1] / 100 if result[0] > 0 else 0
            }
        except Exception as e:
            print(f"⚠️  Error getting reputation: {e}")
            return {"feedbackCount": 0, "averageScore": 0, "error": str(e)}

    async def get_agent_info(self, agent_id: int) -> Dict[str, Any]:
        """
        Get agent information.

        Uses subgraph for fast lookup if available.
        """
        # Try subgraph first
        if self.subgraph:
            agent_data = await self.subgraph.get_agent_by_id(str(agent_id))
            if agent_data:
                return {
                    "agent_id": agent_id,
                    "owner": agent_data.get("owner"),
                    "tokenURI": agent_data.get("tokenURI")
                }

        # Fall back to RPC
        try:
            owner = self.identity_contract.functions.ownerOf(agent_id).call()
            token_uri = self.identity_contract.functions.tokenURI(agent_id).call()

            return {
                "agent_id": agent_id,
                "owner": owner,
                "tokenURI": token_uri
            }
        except Exception as e:
            raise ValueError(f"Agent ID {agent_id} not found: {e}")

    async def set_agent_uri(self, agent_id: int, new_uri: str) -> str:
        """Update the tokenURI for an agent."""
        if not self.account:
            raise ValueError("Account required for setting agent URI")

        tx = self.identity_contract.functions.setAgentUri(
            agent_id,
            new_uri
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Set agent URI tx: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Set agent URI failed: tx={tx_hash.hex()}")

        # Clear subgraph cache for this agent
        if self.subgraph:
            self.subgraph.clear_cache()

        return tx_hash.hex()

    async def get_metadata(self, agent_id: int, key: str) -> bytes:
        """Get metadata value for an agent."""
        return self.identity_contract.functions.getMetadata(agent_id, key).call()

    async def set_metadata(self, agent_id: int, key: str, value: bytes) -> str:
        """Set metadata for an agent."""
        if not self.account:
            raise ValueError("Account required for setting metadata")

        tx = self.identity_contract.functions.setMetadata(
            agent_id,
            key,
            value
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Set metadata tx: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Set metadata failed: tx={tx_hash.hex()}")

        return tx_hash.hex()

    # Backward compatibility aliases
    async def submit_feedback(
        self,
        target_agent_id: int,
        rating: int,
        data: Dict[str, Any]
    ) -> str:
        """
        Legacy feedback submission (maps to new give_feedback).

        Args:
            target_agent_id: ID of agent being rated
            rating: Rating value (1-5, maps to 20-100)
            data: Additional feedback data

        Returns:
            Transaction hash
        """
        # Convert 1-5 rating to 0-100 scale (1★=20, 5★=100)
        value = rating * 20

        return await self.give_feedback(
            agent_id=target_agent_id,
            tag1="rating",
            tag2="legacy",
            value=value,
            value_decimals=0,
            uri="",
            uri_hash=b'\x00' * 32
        )
