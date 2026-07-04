"""Bearer-token authentication for the v1 API.

Every route except ``/health`` requires ``Authorization: Bearer <token>`` where
``<token>`` matches the auto-generated ``config_root()/api-token`` (created on the
first ``mad serve``). The comparison is constant-time. A missing or wrong token is
a 401; a server with no token file configured is a 503.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mad_cli.core.usecases import service

_bearer = HTTPBearer(auto_error=False, description="The token from config_root()/api-token.")


def require_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """FastAPI dependency: enforce a valid bearer token or raise 401/503."""
    expected = service.read_api_token()
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API token is not configured on the server.",
        )
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
