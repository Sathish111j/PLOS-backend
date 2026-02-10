"""
PLOS Authentication Module
JWT-based authentication for all services
"""

from .dependencies import get_current_user, get_current_user_optional
from .models import (
    PasswordChange,
    TokenData,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from .repository import UserRepository
from .router import create_auth_router
from .service import AuthService
from .utils import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)

__all__ = [
    # Service
    "AuthService",
    # Repository
    "UserRepository",
    # Router
    "create_auth_router",
    # Dependencies
    "get_current_user",
    "get_current_user_optional",
    # Utils
    "create_access_token",
    "decode_access_token",
    "verify_password",
    "get_password_hash",
    # Models
    "TokenData",
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "PasswordChange",
]
