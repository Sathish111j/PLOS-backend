"""
PLOS Authentication API Router
Endpoints for user registration, login, and profile management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth.dependencies import get_current_user
from shared.auth.models import (
    PasswordChange,
    TokenData,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from shared.auth.service import AuthService
from shared.utils.errors import AuthenticationError, ValidationError
from shared.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


def create_auth_router(get_db_session):
    """
    Factory function to create auth router with database dependency

    Args:
        get_db_session: FastAPI dependency function for database session

    Returns:
        Configured APIRouter with auth endpoints
    """

    auth_router = APIRouter(prefix="/auth", tags=["authentication"])

    @auth_router.post(
        "/register",
        response_model=TokenResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Register new user",
        description="Create a new user account and return authentication token",
    )
    async def register(
        user_data: UserCreate,
        db: AsyncSession = Depends(get_db_session),
    ) -> TokenResponse:
        """Register a new user"""
        try:
            auth_service = AuthService(db)
            return await auth_service.register_user(user_data)

        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e.message),
            )
        except Exception as e:
            logger.error(f"Registration error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register user",
            )

    @auth_router.post(
        "/login",
        response_model=TokenResponse,
        status_code=status.HTTP_200_OK,
        summary="User login",
        description="Authenticate user with email and password, return JWT token",
    )
    async def login(
        credentials: UserLogin,
        db: AsyncSession = Depends(get_db_session),
    ) -> TokenResponse:
        """Login with email and password"""
        try:
            auth_service = AuthService(db)
            return await auth_service.login(
                email=credentials.email,
                password=credentials.password,
            )

        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e.message),
            )
        except Exception as e:
            logger.error(f"Login error: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed",
            )

    @auth_router.get(
        "/me",
        response_model=UserResponse,
        status_code=status.HTTP_200_OK,
        summary="Get current user",
        description="Get the currently authenticated user's profile",
    )
    async def get_me(
        current_user: TokenData = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> UserResponse:
        """Get current user profile"""
        auth_service = AuthService(db)
        user = await auth_service.get_current_user(current_user.user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return user

    @auth_router.patch(
        "/me",
        response_model=UserResponse,
        status_code=status.HTTP_200_OK,
        summary="Update profile",
        description="Update the current user's profile information",
    )
    async def update_profile(
        update_data: UserUpdate,
        current_user: TokenData = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> UserResponse:
        """Update user profile"""
        auth_service = AuthService(db)
        user = await auth_service.update_profile(
            user_id=current_user.user_id,
            full_name=update_data.full_name,
            timezone=update_data.timezone,
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return user

    @auth_router.post(
        "/change-password",
        status_code=status.HTTP_200_OK,
        summary="Change password",
        description="Change the current user's password",
    )
    async def change_password(
        password_data: PasswordChange,
        current_user: TokenData = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ):
        """Change user password"""
        try:
            auth_service = AuthService(db)
            success = await auth_service.change_password(
                user_id=current_user.user_id,
                current_password=password_data.current_password,
                new_password=password_data.new_password,
            )

            if success:
                return {"message": "Password changed successfully"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to change password",
                )

        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e.message),
            )

    @auth_router.post(
        "/verify-token",
        status_code=status.HTTP_200_OK,
        summary="Verify token",
        description="Verify if the current token is valid",
    )
    async def verify_token(
        current_user: TokenData = Depends(get_current_user),
    ):
        """Verify the current token is valid"""
        return {
            "valid": True,
            "user_id": str(current_user.user_id),
            "email": current_user.email,
            "username": current_user.username,
        }

    return auth_router
