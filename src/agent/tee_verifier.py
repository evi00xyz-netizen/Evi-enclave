"""TEE Verification and Registration"""

import httpx
from typing import Dict, Any, Optional
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

from .chain_config import ChainConfig, get_chain_config_from_env


class TEEVerifier:
    def __init__(
        self,
        w3: Web3,
        tee_registry_address: Optional[str] = None,
        account: Optional[Account] = None,
        verifier_address: Optional[str] = None,
        config: Optional[ChainConfig] = None
    ):
        """
        Initialize TEE verifier.

        Args:
            w3: Web3 instance
            tee_registry_address: TEE Registry contract address (optional if config provided)
            account: Account for signing transactions
            verifier_address: TEE Verifier contract address (optional if config provided)
            config: Chain configuration (if None, loads from environment)
        """
        # Load chain config if addresses not provided
        if config is None and (tee_registry_address is None or verifier_address is None):
            config = get_chain_config_from_env()

        # Use provided addresses or fall back to config
        registry_addr = tee_registry_address or config.tee_registry
        verifier_addr = verifier_address or config.tee_verifier

        self.w3 = w3
        self.registry_address = Web3.to_checksum_address(registry_addr)
        self.account = account
        self.verifier_address = Web3.to_checksum_address(verifier_addr)

        print(f"TEEVerifier initialized:")
        print(f"  TEE Registry: {self.registry_address}")
        print(f"  TEE Verifier: {self.verifier_address}")

        self.registry_abi = [
            {
                "inputs": [
                    {"name": "agentId", "type": "uint256"},
                    {"name": "teeArch", "type": "bytes32"},
                    {"name": "codeMeasurement", "type": "bytes32"},
                    {"name": "pubkey", "type": "address"},
                    {"name": "codeConfigUri", "type": "string"},
                    {"name": "verifier", "type": "address"},
                    {"name": "proof", "type": "bytes"}
                ],
                "name": "addKey",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"name": "agentId", "type": "uint256"}, {"name": "pubkey", "type": "address"}],
                "name": "hasKey",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.registry_contract = w3.eth.contract(
            address=self.registry_address,
            abi=self.registry_abi
        )

    async def check_tee_registered(self, agent_id: int, pubkey_address: str) -> bool:
        """Check if TEE key already registered."""
        return self.registry_contract.functions.hasKey(agent_id, Web3.to_checksum_address(pubkey_address)).call()

    async def register_tee_key(
        self,
        agent_id: int,
        agent_address: str,
        tdx_quote: str,
        app_id: str,
        dstack_domain: str,
        event_log: object,
        mock_mode: bool = True
    ) -> Dict[str, Any]:
        """Register TEE key - uses mock proof with actual agent address."""

        # Check if already registered
        pubkey = Web3.to_checksum_address(agent_address)
        if await self.check_tee_registered(agent_id, pubkey):
            return {"success": True, "agent_id": agent_id, "pubkey": pubkey, "already_registered": True}

        payload = {
            'agentId': agent_id,
            'agentPubkey': agent_address,
            'tdxQuote': tdx_quote,
            'appId': app_id,
            'dstackDomain': dstack_domain,
        }

        print(f"📤 Requesting offchain proof with payload: {payload}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post('https://194622febfc33d67e4a98f365dbc2fe9d0d53933-3000.dstack-pha-prod9.phala.network/getOffchainProof', json=payload)
                print(f"📥 Offchain proof response status: {resp.status_code}")
                print(f"📥 Offchain proof response: {resp.text[:500]}")
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            print(f"❌ Offchain proof request failed: {str(e)}")
            raise RuntimeError(f"Failed to get offchain proof: {str(e)}")

        tee_arch = Web3.to_bytes(text="TDX_DSTACK").ljust(32, b'\x00')
        code_measurement = data['codeMeasurement']
        code_config_uri = data['codeConfigUri']
        proof = data['proof']

        tx = self.registry_contract.functions.addKey(
            agent_id,
            tee_arch,
            code_measurement,
            pubkey,
            code_config_uri,
            self.verifier_address,
            proof
        ).build_transaction({
            'chainId': self.w3.eth.chain_id,
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'nonce': self.w3.eth.get_transaction_count(self.account.address)
        })

        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"📤 TEE tx: {tx_hash.hex()}")

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise RuntimeError(f"TEE registration failed: tx={tx_hash.hex()}")

        return {
            "success": True,
            "tx_hash": tx_hash.hex(),
            "agent_id": agent_id,
            "pubkey": pubkey,
            "code_measurement": code_measurement
        }
