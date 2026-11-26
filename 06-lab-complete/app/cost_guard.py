"""
Cost guard (tiêu chí 8) — Theo dõi chi phí LLM trong Redis.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _cost_key() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{day}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    client = get_redis()
    if client is None:
        return

    try:
        spent = float(client.get(_cost_key()) or 0.0)
    except Exception:
        return

    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "spent_usd": round(spent, 6),
                "daily_budget_usd": settings.daily_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng trong Redis."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (
        output_tokens / 1000.0
    ) * PRICE_OUTPUT_PER_1K
    client = get_redis()
    if client is not None:
        try:
            key = _cost_key()
            client.incrbyfloat(key, cost)
            client.expire(key, 172800)
        except Exception:
            pass
    return round(cost, 8)
