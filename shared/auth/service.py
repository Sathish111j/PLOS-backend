"""
PLOS Authentication Service
Business logic for user authentication and management
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.config import get_settings
from shared.utils.errors import AuthenticationError, ValidationError
from shared.utils.logger import get_logger

from .models import TokenResponse, UserCreate, UserResponse
from .repository import UserRepository
from .utils import create_access_token, get_password_hash, verify_password

logger = get_logger(__name__)
settings = get_settings()


class AuthService:
    """
    Authentication service handling user registration, login, and token operations
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.user_repo = UserRepository(db_session)

    async def register_user(self, user_data: UserCreate) -> TokenResponse:
        """
        Register a new user

        Args:
            user_data: User registration data

        Returns:
            TokenResponse with access token and user details

        Raises:
            ValidationError: If email/username already exists
        """
        # Check if email exists
        if await self.user_repo.email_exists(user_data.email):
            raise ValidationError(
                message="Email already registered",
                field="email",
            )

        # Check if username exists
        if await self.user_repo.username_exists(user_data.username):
            raise ValidationError(
                message="Username already taken",
                field="username",
            )

        # Hash password
        password_hash = get_password_hash(user_data.password)

        # Create user
        user = await self.user_repo.create_user(
            email=user_data.email,
            username=user_data.username,
            password_hash=password_hash,
            full_name=user_data.full_name,
            timezone_str=user_data.timezone,
        )

        if not user:
            raise ValidationError(message="Failed to create user")

        # Update last login
        await self.user_repo.update_last_login(user["id"])

        # Generate token
        access_token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            username=user["username"],
        )

        logger.info(f"User registered: {user['email']}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expiration,
            user=UserResponse(
                user_id=user["id"],
                email=user["email"],
                username=user["username"],
                full_name=user["full_name"],
                timezone=user["timezone"],
                is_active=user["is_active"],
                is_verified=user["is_verified"],
                created_at=user["created_at"],
                last_login=user["last_login"],
            ),
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        """
        Authenticate user and return token

        Args:
            email: User email
            password: Plain text password

        Returns:
            TokenResponse with access token and user details

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Get user with password hash
        user = await self.user_repo.get_user_by_email(email)

        if not user:
            logger.warning(f"Login attempt for non-existent email: {email}")
            raise AuthenticationError(message="Invalid email or password")

        # Verify password
        if not verify_password(password, user["password_hash"]):
            logger.warning(f"Invalid password attempt for: {email}")
            raise AuthenticationError(message="Invalid email or password")

        # Check if user is active
        if not user["is_active"]:
            logger.warning(f"Login attempt for inactive user: {email}")
            raise AuthenticationError(message="Account is deactivated")

        # Update last login
        await self.user_repo.update_last_login(user["id"])

        # Generate token
        access_token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            username=user["username"],
        )

        logger.info(f"User logged in: {user['email']}")

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_expiration,
            user=UserResponse(
                user_id=user["id"],
                email=user["email"],
                username=user["username"],
                full_name=user["full_name"],
                timezone=user["timezone"],
                is_active=user["is_active"],
                is_verified=user["is_verified"],
                created_at=user["created_at"],
                last_login=user["last_login"],
            ),
        )

    async def get_current_user(self, user_id: UUID) -> Optional[UserResponse]:
        """
        Get current user by ID

        Args:
            user_id: User UUID

        Returns:
            UserResponse or None
        """
        user = await self.user_repo.get_user_by_id(user_id)

        if not user:
            return None

        return UserResponse(
            user_id=user["id"],
            email=user["email"],
            username=user["username"],
            full_name=user["full_name"],
            timezone=user["timezone"],
            is_active=user["is_active"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user["last_login"],
        )

    async def update_profile(
        self,
        user_id: UUID,
        full_name: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Optional[UserResponse]:
        """Update user profile"""
        user = await self.user_repo.update_user(
            user_id=user_id,
            full_name=full_name,
            timezone_str=timezone,
        )

        if not user:
            return None

        return UserResponse(
            user_id=user["id"],
            email=user["email"],
            username=user["username"],
            full_name=user["full_name"],
            timezone=user["timezone"],
            is_active=user["is_active"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            last_login=user["last_login"],
        )

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Change user password

        Args:
            user_id: User UUID
            current_password: Current password for verification
            new_password: New password

        Returns:
            True if successful

        Raises:
            AuthenticationError: If current password is wrong
        """
        # Get user with password hash (need to fetch from email)
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError(message="User not found")

        # Get full user with password
        full_user = await self.user_repo.get_user_by_email(user["email"])
        if not full_user:
            raise AuthenticationError(message="User not found")

        # Verify current password
        if not verify_password(current_password, full_user["password_hash"]):
            raise AuthenticationError(message="Current password is incorrect")

        # Hash new password
        new_hash = get_password_hash(new_password)

        # Update password
        success = await self.user_repo.update_password(user_id, new_hash)

        if success:
            logger.info(f"Password changed for user: {user['email']}")

        return success
