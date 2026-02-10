"""
PLOS Authentication Dependencies
FastAPI dependency injection for authentication
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.utils.logger import get_logger

from .models import TokenData
from .utils import decode_access_token

logger = get_logger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """
    FastAPI dependency to get current authenticated user from JWT token

    Usage:
    ```python
    @app.get("/protected")
    async def protected_endpoint(current_user: TokenData = Depends(get_current_user)):
        return {"user_id": current_user.user_id}
    ```

    Raises:
        HTTPException 401: If token is missing or invalid
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_data = TokenData(
            user_id=UUID(payload["sub"]),
            email=payload["email"],
            username=payload["username"],
        )
        return token_data

    except (KeyError, ValueError) as e:
        logger.warning(f"Invalid token payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """
    FastAPI dependency to optionally get current user

    Returns None if no token provided, raises 401 if token is invalid

    Usage:
    ```python
    @app.get("/public-or-private")
    async def endpoint(current_user: Optional[TokenData] = Depends(get_current_user_optional)):
        if current_user:
            return {"user_id": current_user.user_id}
        return {"message": "Public access"}
    ```
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return TokenData(
            user_id=UUID(payload["sub"]),
            email=payload["email"],
            username=payload["username"],
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_user_match(user_id_param: str = "user_id"):
    """
    Factory for dependency that verifies the authenticated user matches the requested user_id

    Usage:
    ```python
    @app.get("/users/{user_id}/data")
    async def get_user_data(
        user_id: UUID,
        _: None = Depends(require_user_match("user_id")),
        current_user: TokenData = Depends(get_current_user)
    ):
        # Only accessible if current_user.user_id == user_id
        ...
    ```
    """

    async def verify_user_match(
        current_user: TokenData = Depends(get_current_user),
        **kwargs,
    ) -> None:
        request_user_id = kwargs.get(user_id_param)

        if request_user_id is None:
            return  # No user_id in path, skip check

        if isinstance(request_user_id, str):
            request_user_id = UUID(request_user_id)

        if current_user.user_id != request_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own data",
            )

    return verify_user_match
