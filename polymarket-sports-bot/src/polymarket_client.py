"""Stage 1 — Fetch active sport markets from Polymarket and apply pre-LLM filters."""

from __future__ import annotations

from typing import List, Optional

import httpx

from config import config
from src.models import Market, SportType, TargetCandidate

POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"

SPORT_KEYWORDS = {
    SportType.TENNIS: [
        "tennis", "atp", "wta", "grand slam", "wimbledon",
        "roland garros", "us open tennis", "australian open tennis",
    ],
    SportType.FOOTBALL: [
        "football", "soccer", "premier league", "la liga", "bundesliga",
        "serie a", "ligue 1", "champions league", "europa league",
        "mls", "world cup", "euro 202", "fa cup", "copa libertadores",
    ],
}


def detect_sport(text: str) -> SportType:
    """Classify a market as tennis / football / unknown from its question text."""
    text_lower = text.lower()
    for sport, keywords in SPORT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return sport
    return SportType.UNKNOWN


async def fetch_active_markets() -> List[Market]:
    """Pull active markets from the Polymarket Gamma API and keep only sport markets."""
    async with httpx.AsyncClient(timeout=30) as client:
        params = {
            "active": "true",
            "closed": "false",
            "limit": 500,
            "offset": 0,
        }
        resp = await client.get(f"{POLYMARKET_GAMMA_URL}/markets", params=params)
        resp.raise_for_status()
        data = resp.json()

    markets: List[Market] = []
    for item in data:
        combined_text = f"{item.get('question', '')} {item.get('description', '')}"
        sport = detect_sport(combined_text)
        if sport == SportType.UNKNOWN:
            continue

        # Build token list from outcomes
        tokens = []
        outcomes = item.get("outcomes", [])
        clob_ids = item.get("clobTokenIds", [])
        prices = item.get("outcomePrices", [])
        outcome_labels = outcomes if isinstance(outcomes, list) else []

        for i, label in enumerate(outcome_labels):
            token_id = clob_ids[i] if i < len(clob_ids) else ""
            price_str = prices[i] if i < len(prices) else "0"
            try:
                price = float(price_str)
            except (TypeError, ValueError):
                price = 0.0
            tokens.append({
                "token_id": token_id,
                "outcome": label,
                "price": price,
            })

        volume = float(item.get("volume", 0) or 0)
        liquidity = float(item.get("liquidity", 0) or 0)

        markets.append(Market(
            condition_id=item.get("conditionId", ""),
            question=item.get("question", ""),
            description=item.get("description", ""),
            tokens=tokens,
            volume=volume,
            liquidity=liquidity,
            sport=sport,
            end_date=item.get("endDate", ""),
            active=item.get("active", False),
        ))

    return markets


def filter_market(market: Market) -> bool:
    """Stage 1 volume filter — reject markets below the minimum 24h volume."""
    return market.volume >= config.min_volume


def get_target_candidate(market: Market) -> Optional[TargetCandidate]:
    """Identify the favoured side as TARGET_CANDIDATE if the market passes all filters.

    Filters:
      - Volume > $5,000 (configurable)
      - Implied probability < 90% (configurable) — discard heavy favourites
    """
    if not filter_market(market):
        return None

    if not market.tokens:
        return None

    # Favoured side = highest price (highest implied probability)
    best_token = max(market.tokens, key=lambda t: t.get("price", 0))
    price = best_token.get("price", 0)
    implied_prob = price  # Polymarket price == implied probability

    if implied_prob > config.max_implied_prob:
        return None  # heavy favourite — discard

    if implied_prob <= 0:
        return None

    return TargetCandidate(
        market=market,
        token_id=best_token.get("token_id", ""),
        outcome=best_token.get("outcome", ""),
        price=price,
        implied_prob=implied_prob,
    )
