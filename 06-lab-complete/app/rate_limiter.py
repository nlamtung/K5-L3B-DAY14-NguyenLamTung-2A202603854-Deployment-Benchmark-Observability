"""
Rate limiting (tiêu chí 7) — Sliding window lưu trong Redis.
"""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import get_redis

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60s cho mỗi API key, lưu trong Redis."""
    client = get_redis()
    if client is None:
        return

    now = time.time()
    window_start = now - WINDOW_SECONDS
    redis_key = f"rate_limit:{key}"

    try:
        pipe = client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= settings.rate_limit_per_minute:
            oldest = client.zrange(redis_key, 0, 0, withscores=True)
            retry_after = (
                max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                if oldest
                else WINDOW_SECONDS
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

        member = f"{now}:{uuid.uuid4().hex}"
        pipe = client.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        # Không làm sập request nếu Redis tạm lỗi trong lúc kiểm tra không bắt buộc
        return
