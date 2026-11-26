"""
API Key authentication (tiêu chí 6).
"""
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — kiểm tra header X-API-Key khớp AGENT_API_KEY."""
    if not api_key or not settings.agent_api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key",
        )
    return api_key
