"""
PLOS User Repository
Database operations for user management
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class UserRepository:
    """Repository for user database operations"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_user(
        self,
        email: str,
        username: str,
        password_hash: str,
        full_name: Optional[str] = None,
        timezone_str: str = "UTC",
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new user

        Args:
            email: User email
            username: Unique username
            password_hash: Hashed password
            full_name: Optional full name
            timezone_str: User timezone

        Returns:
            Created user dict or None if failed
        """
        query = text("""
            INSERT INTO users (email, username, password_hash, full_name, timezone)
            VALUES (:email, :username, :password_hash, :full_name, :timezone)
            RETURNING id, email, username, full_name, timezone, is_active,
                      is_verified, created_at, updated_at, last_login
        """)

        try:
            result = await self.db.execute(
                query,
                {
                    "email": email.lower(),
                    "username": username,
                    "password_hash": password_hash,
                    "full_name": full_name,
                    "timezone": timezone_str,
                },
            )
            await self.db.commit()

            row = result.fetchone()
            if row:
                return {
                    "id": row[0],
                    "email": row[1],
                    "username": row[2],
                    "full_name": row[3],
                    "timezone": row[4],
                    "is_active": row[5],
                    "is_verified": row[6],
                    "created_at": row[7],
                    "updated_at": row[8],
                    "last_login": row[9],
                }
            return None

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating user: {e}")
            raise

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get user by email address

        Args:
            email: User email

        Returns:
            User dict with password_hash or None
        """
        query = text("""
            SELECT id, email, username, password_hash, full_name, timezone,
                   is_active, is_verified, created_at, updated_at, last_login
            FROM users
            WHERE email = :email
        """)

        result = await self.db.execute(query, {"email": email.lower()})
        row = result.fetchone()

        if row:
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "password_hash": row[3],
                "full_name": row[4],
                "timezone": row[5],
                "is_active": row[6],
                "is_verified": row[7],
                "created_at": row[8],
                "updated_at": row[9],
                "last_login": row[10],
            }
        return None

    async def get_user_by_id(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get user by UUID

        Args:
            user_id: User UUID

        Returns:
            User dict (no password) or None
        """
        query = text("""
            SELECT id, email, username, full_name, timezone,
                   is_active, is_verified, created_at, updated_at, last_login
            FROM users
            WHERE id = :user_id
        """)

        result = await self.db.execute(query, {"user_id": str(user_id)})
        row = result.fetchone()

        if row:
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "full_name": row[3],
                "timezone": row[4],
                "is_active": row[5],
                "is_verified": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "last_login": row[9],
            }
        return None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username

        Args:
            username: Username

        Returns:
            User dict or None
        """
        query = text("""
            SELECT id, email, username, full_name, timezone,
                   is_active, is_verified, created_at, updated_at, last_login
            FROM users
            WHERE username = :username
        """)

        result = await self.db.execute(query, {"username": username})
        row = result.fetchone()

        if row:
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "full_name": row[3],
                "timezone": row[4],
                "is_active": row[5],
                "is_verified": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "last_login": row[9],
            }
        return None

    async def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login timestamp"""
        query = text("""
            UPDATE users
            SET last_login = :now
            WHERE id = :user_id
        """)

        await self.db.execute(
            query,
            {
                "user_id": str(user_id),
                "now": datetime.now(timezone.utc),
            },
        )
        await self.db.commit()

    async def update_user(
        self,
        user_id: UUID,
        full_name: Optional[str] = None,
        timezone_str: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update user profile"""
        updates = []
        params: Dict[str, Any] = {"user_id": str(user_id)}

        if full_name is not None:
            updates.append("full_name = :full_name")
            params["full_name"] = full_name

        if timezone_str is not None:
            updates.append("timezone = :timezone")
            params["timezone"] = timezone_str

        if not updates:
            return await self.get_user_by_id(user_id)

        query = text(f"""
            UPDATE users
            SET {", ".join(updates)}, updated_at = NOW()
            WHERE id = :user_id
            RETURNING id, email, username, full_name, timezone,
                      is_active, is_verified, created_at, updated_at, last_login
        """)

        result = await self.db.execute(query, params)
        await self.db.commit()

        row = result.fetchone()
        if row:
            return {
                "id": row[0],
                "email": row[1],
                "username": row[2],
                "full_name": row[3],
                "timezone": row[4],
                "is_active": row[5],
                "is_verified": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "last_login": row[9],
            }
        return None

    async def update_password(self, user_id: UUID, new_password_hash: str) -> bool:
        """Update user password"""
        query = text("""
            UPDATE users
            SET password_hash = :password_hash, updated_at = NOW()
            WHERE id = :user_id
        """)

        result = await self.db.execute(
            query,
            {
                "user_id": str(user_id),
                "password_hash": new_password_hash,
            },
        )
        await self.db.commit()

        return result.rowcount > 0

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered"""
        query = text("SELECT 1 FROM users WHERE email = :email")
        result = await self.db.execute(query, {"email": email.lower()})
        return result.fetchone() is not None

    async def username_exists(self, username: str) -> bool:
        """Check if username is already taken"""
        query = text("SELECT 1 FROM users WHERE username = :username")
        result = await self.db.execute(query, {"username": username})
        return result.fetchone() is not None

    async def create_default_buckets(self, user_id: UUID) -> None:
        root_buckets = [
            {
                "name": "Research and Reference",
                "description": "Academic papers, technical documentation, and reference resources for study and citation.",
                "icon": "book",
                "color": "#4F46E5",
                "is_default": True,
            },
            {
                "name": "Work and Projects",
                "description": "Work files, project documentation, meeting notes, reports, and professional materials.",
                "icon": "briefcase",
                "color": "#0EA5E9",
                "is_default": True,
            },
            {
                "name": "Web and Media Saves",
                "description": "Web pages, articles, social and media content, and online resources to revisit.",
                "icon": "globe",
                "color": "#10B981",
                "is_default": True,
            },
            {
                "name": "Needs Classification",
                "description": "Temporary inbox for documents that require manual bucket assignment.",
                "icon": "inbox",
                "color": "#F59E0B",
                "is_default": False,
            },
        ]

        insert_query = text("""
            INSERT INTO buckets (
                name,
                description,
                storage_backend,
                storage_bucket,
                is_active,
                created_by,
                updated_by,
                user_id,
                parent_bucket_id,
                depth,
                path,
                icon_emoji,
                color_hex,
                document_count,
                is_default,
                is_deleted
            )
            VALUES (
                :name,
                :description,
                'minio',
                'knowledge-base-documents',
                TRUE,
                :user_id,
                :user_id,
                :user_id,
                NULL,
                0,
                :path,
                :icon_emoji,
                :color_hex,
                0,
                :is_default,
                FALSE
            )
            ON CONFLICT DO NOTHING
            """)

        for bucket in root_buckets:
            slug = (
                bucket["name"].strip().lower().replace(" and ", "-").replace(" ", "-")
            )
            await self.db.execute(
                insert_query,
                {
                    "name": bucket["name"],
                    "description": bucket["description"],
                    "user_id": str(user_id),
                    "path": f"/root/{slug}",
                    "icon_emoji": bucket["icon"],
                    "color_hex": bucket["color"],
                    "is_default": bool(bucket["is_default"]),
                },
            )

        await self.db.commit()
