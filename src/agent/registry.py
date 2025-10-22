"""
ERC-8004 Registry Client

Handles all interactions with the ERC-8004 registry contracts.
"""

import json
from typing import Dict, Any, Optional, List
from web3 import Web3
from eth_account import Account


class RegistryClient:
    """
    Client for interacting with ERC-8004 registry contracts.

    Manages connections to:
    - Identity Registry
    - Reputation Registry
    - Validation Registry
    """

    def __init__(
        self,
        rpc_url: str,
        chain_id: int,
        registries: Dict[str, str],
        account: Optional[Account] = None
    ):
        """
        Initialize registry client.

        Args:
            rpc_url: Blockchain RPC endpoint
            chain_id: Chain ID for the network
            registries: Dictionary with registry addresses
            account: Account for signing transactions
        """
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.registries = registries
        self.account = account

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to {rpc_url}")

        # Load contract ABIs
        self._load_abis()

        # Initialize contract instances
        self._init_contracts()

    def _load_abis(self):
        """Load contract ABIs."""
        # For now, define minimal ABIs inline
        # In production, load from JSON files

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
                    {"name": "targetAgentId", "type": "uint256"},
                    {"name": "rating", "type": "uint8"},
                    {"name": "data", "type": "string"}
                ],
                "name": "submitFeedback",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [{"name": "agentId", "type": "uint256"}],
                "name": "getReputation",
                "outputs": [
                    {"name": "totalFeedback", "type": "uint256"},
                    {"name": "averageRating", "type": "uint256"}
                ],
                "type": "function"
            }
        ]

        self.validation_abi = [
            {
                "inputs": [
                    {"name": "validatorAgentId", "type": "uint256"},
                    {"name": "dataHash", "type": "bytes32"}
                ],
                "name": "requestValidation",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "dataHash", "type": "bytes32"},
                    {"name": "response", "type": "uint8"}
                ],
                "name": "submitValidationResponse",
                "outputs": [],
                "type": "function"
            },
            {
                "inputs": [{"name": "dataHash", "type": "bytes32"}],
                "name": "getValidationStatus",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
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

        self.validation_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.registries['validation']),
            abi=self.validation_abi
        )

    async def check_agent_registration(
        self,
        domain: str = None,
        agent_address: str = None,
        agent_id: int = None
    ) -> Dict[str, Any]:
        """
        Check if agent is registered (owns an NFT).

        Args:
            domain: Unused (kept for compatibility)
            agent_address: Agent's Ethereum address
            agent_id: Optional known agent ID for fast verification (1 RPC call vs 1000)

        Returns:
            Dict with registration info or {"registered": False}
        """
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
                # Fall through to slow path

        # SLOW PATH: Existing logic for unknown agent_id
        try:
            if agent_address:
                checksum_address = Web3.to_checksum_address(agent_address)
                print(f"🔍 Checking registration for: {checksum_address}")

                balance = self.identity_contract.functions.balanceOf(checksum_address).call()
                print(f"🔍 NFT Balance: {balance}")

                if balance > 0:
                    # Get the first token owned by this address
                    # ERC721Enumerable provides tokenOfOwnerByIndex
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
                        # Fallback: Try brute force search for token IDs
                        print(f"🔍 Attempting brute force search for token ID (balance: {balance})...")
                        for potential_id in range(1, 1000):  # Search first 1000 token IDs
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

                        # If we still can't find it, return registered but without agent_id
                        print(f"⚠️  Balance is {balance} but couldn't find token ID after search")
                        return {
                            "registered": True,
                            "agent_id": None,  # Unknown, but we know they're registered
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
            wait_for_receipt: If True, wait for confirmation and return agent_id. If False, return tx_hash immediately.

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

        # Return immediately if not waiting for receipt
        if not wait_for_receipt:
            return {
                "tx_hash": tx_hash.hex(),
                "agent_address": self.account.address
            }

        # Otherwise wait for receipt and extract agent_id
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Registration failed: tx={tx_hash.hex()}")

        # Get agent ID from logs (Transfer event: topics[3] is tokenId)
        if receipt['logs'] and len(receipt['logs'][0]['topics']) >= 4:
            agent_id = int(receipt['logs'][0]['topics'][3].hex(), 16)
        else:
            # Fallback: use tokenOfOwnerByIndex to get the token we just minted
            balance = self.identity_contract.functions.balanceOf(self.account.address).call()
            if balance > 0:
                agent_id = self.identity_contract.functions.tokenOfOwnerByIndex(
                    self.account.address,
                    balance - 1  # Get the last token (most recently minted)
                ).call()
            else:
                raise RuntimeError("Registration succeeded but couldn't determine agent ID")

        print(f"✅ Registered with Agent ID: {agent_id}")
        return {"agent_id": agent_id, "tx_hash": tx_hash.hex()}

    async def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get transaction status and extract agent_id if confirmed.

        Args:
            tx_hash: Transaction hash to check

        Returns:
            Dict with status, confirmations, and agent_id if available
        """
        try:
            # Convert tx_hash to bytes if needed
            if isinstance(tx_hash, str):
                tx_hash_bytes = bytes.fromhex(tx_hash.replace('0x', ''))
            else:
                tx_hash_bytes = tx_hash

            # Try to get receipt
            receipt = self.w3.eth.get_transaction_receipt(tx_hash_bytes)

            if receipt is None:
                return {
                    "status": "pending",
                    "confirmed": False
                }

            # Transaction is mined
            if receipt.status != 1:
                return {
                    "status": "failed",
                    "confirmed": True,
                    "success": False
                }

            # Extract agent_id from logs
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
            # Transaction not yet mined
            return {
                "status": "pending",
                "confirmed": False,
                "error": str(e)
            }

    async def verify_agent_by_id(
        self,
        agent_id: int,
        expected_address: str = None
    ) -> Dict[str, Any]:
        """
        Fast verification using known agent_id.

        Uses ownerOf(agent_id) for single RPC call verification instead of brute force search.
        Optionally validates tokenURI domain.

        Args:
            agent_id: The known agent ID (token ID) to verify
            expected_address: Optional address to verify ownership against

        Returns:
            Dict with verification status, owner, and token URI
        """
        try:
            # Single RPC call to verify ownership
            owner = self.identity_contract.functions.ownerOf(agent_id).call()

            verified = True
            if expected_address:
                checksum_expected = Web3.to_checksum_address(expected_address)
                verified = owner.lower() == checksum_expected.lower()

            # Get tokenURI for additional validation if needed
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

    async def submit_feedback(
        self,
        target_agent_id: int,
        rating: int,
        data: Dict[str, Any]
    ) -> str:
        """
        Submit feedback to the Reputation Registry.

        Args:
            target_agent_id: ID of agent being rated
            rating: Rating value (1-5)
            data: Additional feedback data

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for feedback submission")

        # Convert data to JSON
        data_json = json.dumps(data)

        # Build transaction
        tx = self.reputation_contract.functions.submitFeedback(
            target_agent_id,
            rating,
            data_json
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 200000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()

    async def request_validation(
        self,
        validator_agent_id: int,
        data_hash: str
    ) -> str:
        """
        Request validation from a validator agent.

        Args:
            validator_agent_id: ID of validator agent
            data_hash: Hash of data to validate

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for validation request")

        # Convert data hash to bytes32
        if data_hash.startswith('0x'):
            data_hash_bytes = bytes.fromhex(data_hash[2:])
        else:
            data_hash_bytes = bytes.fromhex(data_hash)

        # Build transaction
        tx = self.validation_contract.functions.requestValidation(
            validator_agent_id,
            data_hash_bytes
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()

    async def submit_validation_response(
        self,
        data_hash: str,
        response: int
    ) -> str:
        """
        Submit a validation response.

        Args:
            data_hash: Hash of validated data
            response: Validation response (0=invalid, 1=valid, 2=uncertain)

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for validation response")

        # Convert data hash to bytes32
        if data_hash.startswith('0x'):
            data_hash_bytes = bytes.fromhex(data_hash[2:])
        else:
            data_hash_bytes = bytes.fromhex(data_hash)

        # Build transaction
        tx = self.validation_contract.functions.submitValidationResponse(
            data_hash_bytes,
            response
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()

    async def get_agent_info(self, agent_id: int) -> Dict[str, Any]:
        """
        Get agent information from Identity Registry.

        Args:
            agent_id: Agent ID to lookup

        Returns:
            Agent information dictionary
        """
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
        """
        Update the tokenURI for an agent.

        Args:
            agent_id: Agent ID to update
            new_uri: New token URI

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for setting agent URI")

        # Build transaction
        tx = self.identity_contract.functions.setAgentUri(
            agent_id,
            new_uri
        ).build_transaction({
            'chainId': self.chain_id,
            'gas': 150000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Set agent URI tx: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Set agent URI failed: tx={tx_hash.hex()}")

        return tx_hash.hex()

    async def get_metadata(self, agent_id: int, key: str) -> bytes:
        """
        Get metadata value for an agent.

        Args:
            agent_id: Agent ID
            key: Metadata key

        Returns:
            Metadata value as bytes
        """
        return self.identity_contract.functions.getMetadata(agent_id, key).call()

    async def set_metadata(self, agent_id: int, key: str, value: bytes) -> str:
        """
        Set metadata for an agent.

        Args:
            agent_id: Agent ID
            key: Metadata key
            value: Metadata value as bytes

        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("Account required for setting metadata")

        # Build transaction
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

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 Set metadata tx: {tx_hash.hex()}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"Set metadata failed: tx={tx_hash.hex()}")

        return tx_hash.hex()

    async def get_reputation(self, agent_id: int) -> Dict[str, Any]:
        """
        Get agent reputation from Reputation Registry.

        Args:
            agent_id: Agent ID to lookup

        Returns:
            Reputation information
        """
        result = self.reputation_contract.functions.getReputation(agent_id).call()

        return {
            "totalFeedback": result[0],
            "averageRating": result[1] / 100  # Convert from basis points
        }