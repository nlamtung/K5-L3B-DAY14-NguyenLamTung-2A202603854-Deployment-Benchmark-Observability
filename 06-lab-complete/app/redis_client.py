"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis

from app.config import settings


def _create_client() -> redis.Redis | None:
    if not settings.redis_url:
        return None
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


r: redis.Redis | None = _create_client()


def get_redis() -> redis.Redis | None:
    """Trả về Redis client hiện tại (tạo mới nếu chưa có và REDIS_URL đã cấu hình)."""
    global r
    if r is None and settings.redis_url:
        r = _create_client()
    return r


def redis_healthy() -> bool:
    """Kiểm tra kết nối Redis cho GET /ready."""
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False
