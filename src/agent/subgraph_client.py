"""
Subgraph Client for ERC-8004 Agent

Direct GraphQL queries to The Graph subgraph for fast data reads.
Falls back gracefully if subgraph is unavailable.
"""

import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta

from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

from .chain_config import ChainConfig, get_chain_config_from_env


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""
    data: Any
    expires_at: datetime


class SubgraphClient:
    """
    GraphQL client for ERC-8004 subgraph queries.

    Provides fast reads for agent info, reputation, and discovery.
    Includes caching and fallback handling.
    """

    def __init__(
        self,
        subgraph_url: Optional[str] = None,
        cache_ttl_seconds: int = 30,
        config: Optional[ChainConfig] = None
    ):
        """
        Initialize subgraph client.

        Args:
            subgraph_url: Subgraph GraphQL endpoint. If None, uses chain config.
            cache_ttl_seconds: TTL for cached responses (default: 30 seconds).
            config: Chain configuration. If None, loads from environment.
        """
        if config is None:
            config = get_chain_config_from_env()

        self.subgraph_url = subgraph_url or config.subgraph_url
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, CacheEntry] = {}
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Get or create GraphQL client."""
        if self._client is None:
            transport = AIOHTTPTransport(url=self.subgraph_url)
            self._client = Client(
                transport=transport,
                fetch_schema_from_transport=False  # Don't fetch schema on startup
            )
        return self._client

    def _cache_key(self, query_name: str, **kwargs) -> str:
        """Generate cache key from query name and params."""
        params = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{query_name}:{params}"

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        entry = self._cache.get(key)
        if entry and entry.expires_at > datetime.now():
            return entry.data
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        """Set cached value with TTL."""
        self._cache[key] = CacheEntry(
            data=data,
            expires_at=datetime.now() + self.cache_ttl
        )

    async def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent details by ID.

        Args:
            agent_id: Agent ID (token ID from IdentityRegistry).

        Returns:
            Agent data or None if not found.
        """
        cache_key = self._cache_key("get_agent_by_id", agent_id=agent_id)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = gql("""
            query GetAgent($agentId: String!) {
                agent(id: $agentId) {
                    id
                    owner
                    tokenURI
                    createdAt
                    updatedAt
                }
            }
        """)

        try:
            client = self._get_client()
            async with client as session:
                result = await session.execute(query, variable_values={"agentId": agent_id})
                agent_data = result.get("agent")
                self._set_cached(cache_key, agent_data)
                return agent_data
        except TransportQueryError as e:
            print(f"Subgraph query error (get_agent_by_id): {e}")
            return None
        except Exception as e:
            print(f"Subgraph error (get_agent_by_id): {e}")
            return None

    async def get_agent_by_owner(self, owner_address: str) -> Optional[Dict[str, Any]]:
        """
        Find agent by owner wallet address.

        Args:
            owner_address: Ethereum address of the agent owner.

        Returns:
            First agent owned by address, or None if not found.
        """
        cache_key = self._cache_key("get_agent_by_owner", owner=owner_address.lower())
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = gql("""
            query GetAgentByOwner($owner: String!) {
                agents(where: { owner: $owner }, first: 1) {
                    id
                    owner
                    tokenURI
                    createdAt
                    updatedAt
                }
            }
        """)

        try:
            client = self._get_client()
            async with client as session:
                result = await session.execute(query, variable_values={"owner": owner_address.lower()})
                agents = result.get("agents", [])
                agent_data = agents[0] if agents else None
                self._set_cached(cache_key, agent_data)
                return agent_data
        except TransportQueryError as e:
            print(f"Subgraph query error (get_agent_by_owner): {e}")
            return None
        except Exception as e:
            print(f"Subgraph error (get_agent_by_owner): {e}")
            return None

    async def get_agent_reputation(
        self,
        agent_id: str,
        feedback_limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get agent reputation stats and recent feedback.

        Args:
            agent_id: Agent ID to get reputation for.
            feedback_limit: Max number of recent feedbacks to return.

        Returns:
            Dict with reputation stats and recent feedback.
        """
        cache_key = self._cache_key("get_agent_reputation", agent_id=agent_id, limit=feedback_limit)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        query = gql("""
            query GetReputation($agentId: String!, $feedbackLimit: Int!) {
                agentStats(id: $agentId) {
                    totalFeedback
                    averageFeedbackValue
                }
                feedbacks(
                    where: { agent: $agentId }
                    first: $feedbackLimit
                    orderBy: createdAt
                    orderDirection: desc
                ) {
                    id
                    tag1
                    tag2
                    value
                    clientAddress
                    createdAt
                }
            }
        """)

        try:
            client = self._get_client()
            async with client as session:
                result = await session.execute(
                    query,
                    variable_values={"agentId": agent_id, "feedbackLimit": feedback_limit}
                )

                stats = result.get("agentStats") or {"totalFeedback": 0, "averageFeedbackValue": 0}
                feedbacks = result.get("feedbacks", [])

                reputation_data = {
                    "feedbackCount": int(stats.get("totalFeedback", 0)),
                    "averageScore": float(stats.get("averageFeedbackValue", 0)),
                    "recentFeedback": feedbacks
                }

                self._set_cached(cache_key, reputation_data)
                return reputation_data
        except TransportQueryError as e:
            print(f"Subgraph query error (get_agent_reputation): {e}")
            return {"feedbackCount": 0, "averageScore": 0, "recentFeedback": [], "error": str(e)}
        except Exception as e:
            print(f"Subgraph error (get_agent_reputation): {e}")
            return {"feedbackCount": 0, "averageScore": 0, "recentFeedback": [], "error": str(e)}

    async def list_agents(
        self,
        limit: int = 20,
        offset: int = 0,
        order_by: str = "createdAt",
        order_direction: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        List agents with pagination.

        Args:
            limit: Max agents to return.
            offset: Number of agents to skip.
            order_by: Field to order by (createdAt, updatedAt).
            order_direction: asc or desc.

        Returns:
            List of agent data.
        """
        query = gql("""
            query ListAgents($limit: Int!, $skip: Int!, $orderBy: String!, $orderDirection: String!) {
                agents(
                    first: $limit
                    skip: $skip
                    orderBy: $orderBy
                    orderDirection: $orderDirection
                ) {
                    id
                    owner
                    tokenURI
                    createdAt
                    updatedAt
                }
            }
        """)

        try:
            client = self._get_client()
            async with client as session:
                result = await session.execute(
                    query,
                    variable_values={
                        "limit": limit,
                        "skip": offset,
                        "orderBy": order_by,
                        "orderDirection": order_direction
                    }
                )
                return result.get("agents", [])
        except TransportQueryError as e:
            print(f"Subgraph query error (list_agents): {e}")
            return []
        except Exception as e:
            print(f"Subgraph error (list_agents): {e}")
            return []

    async def health_check(self) -> bool:
        """
        Check if subgraph is accessible.

        Returns:
            True if subgraph is responding, False otherwise.
        """
        try:
            # Simple query to check connectivity
            agents = await self.list_agents(limit=1)
            return True
        except Exception:
            return False

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
