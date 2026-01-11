import json
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from shared.utils.logger import get_logger
from .database import Database
from .bucket_service import BucketService

logger = get_logger(__name__)

class PersistenceService:
    def __init__(self, bucket_service: BucketService):
        self.bucket_service = bucket_service

    async def persist_ingestion_result(
        self, 
        user_id: str, 
        ingestion_result: Dict[str, Any],
        auto_create_bucket: bool = False
    ) -> Dict[str, Any]:
        """
        Orchestrate the saving of ingested content:
        1. Auto-assign bucket (Smart Organization)
        2. Insert into knowledge_items (Metadata + Content)
        3. Link files (MinIO)
        4. Return saved item details
        """
        try:
            # 1. Smart Bucket Assignment
            # Extract basic info for decision
            title = ingestion_result.get("title", "Untitled")
            content = ingestion_result.get("content", "")
            
            # Ensure system buckets exist first (lazy init)
            await self.bucket_service.ensure_system_buckets(user_id)
            
            bucket_plan = await self.bucket_service.smart_assign_bucket(
                user_id=user_id,
                document_text=content,
                document_title=title,
                auto_create=auto_create_bucket
            )
            
            bucket_id = bucket_plan.get("bucket_id")
            
            if not bucket_id:
                logger.warning("No bucket assigned, falling back to Inbox")
                # Fallback logic should be inside smart_assign, but double check
                inbox = await Database.fetch_one("SELECT id FROM knowledge_buckets WHERE user_id=$1 AND name='Inbox'", user_id)
                bucket_id = str(inbox['id']) if inbox else None

            # 2. Insert Item
            insert_query = """
                INSERT INTO knowledge_items 
                (user_id, bucket_id, title, content, content_preview, source_type, item_type, flags)
                VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8)
                RETURNING id, created_at
            """
            
            # content_preview
            preview = ingestion_result.get("content_preview", content[:500])
            source_type = ingestion_result.get("source_type", "text")
            item_type = ingestion_result.get("item_type", "document")
            
            # Calculate flags (e.g. if auto-tagged)
            flags = 0 
            if ingestion_result.get("auto_tagged"):
                flags = 1 # Example bit
            
            item_row = await Database.fetch_one(
                insert_query,
                user_id, 
                bucket_id, 
                title, 
                content, 
                preview, 
                source_type, 
                item_type,
                flags
            )
            item_id = str(item_row['id'])
            
            # 3. Link Files (MinIO)
            # ingestion_result['metadata']['files_uploaded'] is a list of paths "bucket/user/uuid/file"
            if "metadata" in ingestion_result and "files_uploaded" in ingestion_result["metadata"]:
                files = ingestion_result["metadata"]["files_uploaded"]
                for file_path in files: # e.g. "knowledge-files/user_id/..."
                    # We need just the name? 
                    file_name = file_path.split("/")[-1]
                    file_query = """
                        INSERT INTO knowledge_files (item_id, user_id, file_name, file_path)
                        VALUES ($1::uuid, $2, $3, $4)
                    """
                    await Database.execute(file_query, item_id, user_id, file_name, file_path)
            
            # 4. Save Blocks/Chunks (Optional - for vector search later)
            # chunks = ingestion_result.get("chunks", [])
            # For now we rely on content being in `knowledge_items`.
            
            # 5. Log & Return
            logger.info(f"Persisted item {item_id} to bucket {bucket_id} ({bucket_plan.get('bucket_name')})")
            
            return {
                "item_id": item_id,
                "bucket_id": bucket_id,
                "bucket_name": bucket_plan.get("bucket_name"),
                "bucket_confidence": bucket_plan.get("confidence"),
                "status": "saved",
                "title": title
            }

        except Exception as e:
            logger.error(f"Persistence failed: {e}")
            raise
