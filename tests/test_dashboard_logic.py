#!/usr/bin/env python3
"""
Tests for dashboard API logic.

Tests the backend endpoints that the dashboard UI calls.
Run with: pytest tests/test_dashboard_logic.py -v
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, AsyncMock, patch

# Set environment variables before importing
os.environ['SUBGRAPH_API_KEY'] = '60728d932abd25fe7567a4c8e49cb891'
os.environ['RPC_URL'] = 'https://eth-sepolia.g.alchemy.com/v2/S4LzzFcj3i6naYgcXPRvx'
os.environ['CHAIN_NAME'] = 'eth-sepolia'
os.environ['IDENTITY_REGISTRY_ADDRESS'] = '0x8004A818BFB912233c491871b3d84c89A494BD9e'
os.environ['REPUTATION_REGISTRY_ADDRESS'] = '0x8004B663056A597Dffe9eCcC1965A193B7388713'


class TestSubgraphClient:
    """Tests for SubgraphClient."""

    @pytest.mark.asyncio
    async def test_get_agent_by_owner_with_api_key(self):
        """Test that subgraph query works with API key."""
        from src.agent.subgraph_client import SubgraphClient
        from src.agent.chain_config import get_subgraph_url

        url = get_subgraph_url()
        assert '60728d932abd25fe7567a4c8e49cb891' in url, "API key should be in URL"

        client = SubgraphClient(subgraph_url=url)
        result = await client.get_agent_by_owner('0x87B1B890664C49d77e26Ef878a97D50Fb00bd217')

        assert result is not None, "Should find agent"
        assert result.get('agentId') == '535', f"Should return agentId 535, got {result.get('agentId')}"
        assert result.get('owner') == '0x87b1b890664c49d77e26ef878a97d50fb00bd217'

    @pytest.mark.asyncio
    async def test_get_agent_reputation(self):
        """Test reputation query."""
        from src.agent.subgraph_client import SubgraphClient
        from src.agent.chain_config import get_subgraph_url

        client = SubgraphClient(subgraph_url=get_subgraph_url())
        result = await client.get_agent_reputation('535')

        assert 'feedbackCount' in result
        assert 'averageScore' in result
        assert 'recentFeedback' in result


class TestRegistryClient:
    """Tests for RegistryClient."""

    @pytest.mark.asyncio
    async def test_check_agent_registration_fast_path(self):
        """Test that check_agent_registration uses subgraph for instant lookup."""
        from src.agent.chain_config import get_chain_config_from_env
        from src.agent.registry import RegistryClient

        config = get_chain_config_from_env()
        registry = RegistryClient(config=config)

        result = await registry.check_agent_registration(
            agent_address='0x87B1B890664C49d77e26Ef878a97D50Fb00bd217'
        )

        assert result['registered'] is True
        assert result['agent_id'] == 535, f"Expected agent_id 535, got {result['agent_id']}"

    @pytest.mark.asyncio
    async def test_get_reputation(self):
        """Test reputation fetch from contract."""
        from src.agent.chain_config import get_chain_config_from_env
        from src.agent.registry import RegistryClient

        config = get_chain_config_from_env()
        registry = RegistryClient(config=config)

        result = await registry.get_reputation(535)

        assert 'feedbackCount' in result
        assert 'averageScore' in result
        # No error should be present
        assert 'error' not in result or result.get('error') is None


class TestChainConfig:
    """Tests for chain configuration."""

    def test_subgraph_url_with_api_key(self):
        """Test that subgraph URL includes API key."""
        from src.agent.chain_config import get_subgraph_url

        url = get_subgraph_url(api_key='test-key')
        assert 'test-key' in url
        assert 'gateway.thegraph.com/api/test-key' in url

    def test_subgraph_url_from_env(self):
        """Test that subgraph URL uses env var."""
        from src.agent.chain_config import get_subgraph_url

        url = get_subgraph_url()
        assert '60728d932abd25fe7567a4c8e49cb891' in url

    def test_chain_config_from_env(self):
        """Test loading chain config from environment."""
        from src.agent.chain_config import get_chain_config_from_env

        config = get_chain_config_from_env()

        assert config.chain_id == 11155111
        assert config.identity_registry == '0x8004A818BFB912233c491871b3d84c89A494BD9e'
        assert config.reputation_registry == '0x8004B663056A597Dffe9eCcC1965A193B7388713'


class TestDashboardFlow:
    """Tests for the dashboard UI flow logic."""

    @pytest.mark.asyncio
    async def test_registration_check_does_not_block_on_subgraph_failure(self):
        """
        Test that registration check falls back to RPC if subgraph fails.
        This ensures the UI flow doesn't get stuck.
        """
        from src.agent.chain_config import get_chain_config_from_env
        from src.agent.registry import RegistryClient

        config = get_chain_config_from_env()

        # Create registry with subgraph disabled to test fallback
        registry = RegistryClient(config=config, use_subgraph=False)

        # This should still work via RPC (slower but functional)
        result = await registry.check_agent_registration(
            agent_address='0x87B1B890664C49d77e26Ef878a97D50Fb00bd217',
            agent_id=535  # Provide known ID for fast verification
        )

        assert result['registered'] is True
        assert result['agent_id'] == 535

    @pytest.mark.asyncio
    async def test_reputation_failure_should_not_block_tee_step(self):
        """
        Test that reputation check failure doesn't block TEE verification.

        In the UI, even if reputation fails, user should be able to proceed
        to TEE verification step. This is tested at the logic level.
        """
        # This is a conceptual test - the actual fix is in dashboard.html
        # where checkReputation() now continues to checkTEE() even on failure

        # Verify the fix by checking the HTML contains the right logic
        with open('static/dashboard.html', 'r') as f:
            html = f.read()

        # Should have the fix that enables step4 even on reputation failure
        assert "// IMPORTANT: Still enable step 4 - don't block the flow" in html
        assert "document.getElementById('step4').classList.remove('opacity-50')" in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
