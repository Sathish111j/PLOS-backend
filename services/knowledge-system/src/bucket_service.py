import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from shared.gemini import ResilientGeminiClient
from shared.gemini.config import TaskType
from shared.utils.logger import get_logger
from .database import Database

logger = get_logger(__name__)

# Constants for System Buckets (Tier 1)
SYSTEM_BUCKETS = {
    "inbox": {"name": "Inbox", "color": "#4F46E5", "icon": "inbox", "type": "system"},
    "archive": {"name": "Archive", "color": "#9CA3AF", "icon": "archive", "type": "system"},
    "trash": {"name": "Trash", "color": "#EF4444", "icon": "trash", "type": "system"},
}

# Constants for Default Templates (Tier 2)
DEFAULT_TEMPLATES = {
    "content_type": [
        {"name": "Articles & Reading", "desc": "Web articles, blog posts", "icon": "newspaper", "color": "#3B82F6"},
        {"name": "Research & Papers", "desc": "Academic papers, studies", "icon": "book-open", "color": "#8B5CF6"},
        {"name": "Personal Notes", "desc": "Thoughts and ideas", "icon": "pencil", "color": "#EC4899"},
    ],
    "domain": [
        {"name": "Technology", "desc": "Tech, AI, code", "icon": "cpu", "color": "#06B6D4"},
        {"name": "Business & Finance", "desc": "Strategy, economics", "icon": "trending-up", "color": "#10B981"},
        {"name": "Learning & Skills", "desc": "Courses, tutorials", "icon": "graduation-cap", "color": "#F59E0B"},
    ],
    "purpose": [
        {"name": "Active Projects", "desc": "Current work", "icon": "zap", "color": "#F97316"},
        {"name": "Reference & Resources", "desc": "Tools, templates", "icon": "link", "color": "#14B8A6"},
        {"name": "Inspiration", "desc": "Ideas, future ref", "icon": "lightbulb", "color": "#FBBF24"},
    ]
}

class BucketService:
    def __init__(self, gemini_client: Optional[ResilientGeminiClient] = None):
        self.gemini_client = gemini_client or ResilientGeminiClient()

    async def ensure_system_buckets(self, user_id: str):
        """Ensure core system buckets and default templates exist."""
        # 1. Ensure Tier 1 System Buckets
        for key, config in SYSTEM_BUCKETS.items():
            existing = await Database.fetch_one(
                "SELECT id FROM knowledge_buckets WHERE user_id = $1 AND name = $2",
                user_id, config["name"]
            )
            if not existing:
                await self.create_bucket(
                    user_id=user_id,
                    name=config["name"],
                    description=f"System {config['name']} bucket",
                    category="system",
                    icon=config["icon"],
                    color=config["color"]
                )

        # 2. Ensure Tier 2 Templates (Idempotent check)
        # Check if user has ANY template buckets to avoid re-creating deleted ones if strict
        # But per design: "Created automatically, user can customize or delete"
        # We'll check a marker or just logic "if NO buckets exist, create all".
        # For safety/simplicity: Check individual template existence.
        
        for category, templates in DEFAULT_TEMPLATES.items():
            for tcl in templates:
                exists = await Database.fetch_one(
                    "SELECT id FROM knowledge_buckets WHERE user_id = $1 AND name = $2",
                    user_id, tcl["name"]
                )
                if not exists:
                    await self.create_bucket(
                        user_id=user_id,
                        name=tcl["name"],
                        description=tcl["desc"],
                        category=category,
                        icon=tcl["icon"],
                        color=tcl["color"],
                        bucket_type="template"
                    )

    async def create_bucket(
        self,
        user_id: str,
        name: str,
        description: str = None,
        parent_id: str = None,
        category: str = "custom",
        icon: str = "folder",
        color: str = None,
        bucket_type: str = "user"
    ) -> Dict[str, Any]:
        """Create a new bucket."""
        try:
            # Check duplicates at same level
            check_query = """
                SELECT id FROM knowledge_buckets 
                WHERE user_id = $1 AND name = $2 
                AND ((parent_id IS NULL AND $3::uuid IS NULL) OR parent_id = $3::uuid)
            """
            exists = await Database.fetch_one(check_query, user_id, name, parent_id)
            if exists:
                # If template/system, maybe return existing? For now, error or log.
                logger.info(f"Bucket {name} already exists, skipping creation.")
                return dict(exists)

            query = """
                INSERT INTO knowledge_buckets 
                (user_id, name, description, parent_id, category, icon, color, bucket_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, name, path
            """
            row = await Database.fetch_one(
                query, user_id, name, description, parent_id, category, icon, color, bucket_type
            )
            logger.info(f"Created bucket: {name} ({row['id']})")
            return dict(row)
        except Exception as e:
            logger.error(f"Failed to create bucket: {e}")
            raise

    async def get_bucket_tree(self, user_id: str) -> List[Dict[str, Any]]:
        """Get full bucket hierarchy as nested JSON tree."""
        # Optimized query using materialized path sorting
        query = """
            SELECT id, name, parent_id, path, path_depth, icon, color, item_count 
            FROM knowledge_buckets 
            WHERE user_id = $1 AND flags & 2 = 0 -- Not archived
            ORDER BY path ASC
        """
        rows = await Database.fetch_all(query, user_id)
        
        # Build tree in O(N) using dictionary reference
        tree = []
        lookup = {}
        
        for row in rows:
            bucket = dict(row)
            bucket["id"] = str(bucket["id"])
            bucket["parent_id"] = str(bucket["parent_id"]) if bucket["parent_id"] else None
            bucket["children"] = []
            
            lookup[bucket["id"]] = bucket
            
            if bucket["parent_id"] and bucket["parent_id"] in lookup:
                lookup[bucket["parent_id"]]["children"].append(bucket)
            else:
                tree.append(bucket)
                
        return tree

    async def smart_assign_bucket(
        self, 
        user_id: str, 
        document_text: str,
        document_title: str,
        auto_create: bool = False
    ) -> Dict[str, Any]:
        """
        Smartly assign a bucket using Gemini Decision Tree.
        """
        # 1. Fetch user buckets
        buckets = await Database.fetch_all(
            "SELECT id, name, description FROM knowledge_buckets WHERE user_id = $1",
            user_id
        )
        bucket_list_str = "\n".join([f"- {b['name']} (ID: {b['id']}): {b['description'] or ''}" for b in buckets])

        # 2. Construct Prompt
        prompt = f"""Analyze this document and determine the best bucket for it.

DOCUMENT:
Title: {document_title}
Preview: {document_text[:500]}...

EXISTING BUCKETS:
{bucket_list_str}

CRITERIA:
1. auto_create_bucket = {'ON' if auto_create else 'OFF'}
2. If match found (>60% confidence), use existing.
3. If NO match and auto_create=ON, suggest NEW bucket.
4. If NO match and auto_create=OFF, use 'Inbox'.

RESPOND JSON ONLY:
{{
  "action": "use_existing" | "create_new" | "fallback_inbox",
  "bucket_id": "uuid (if existing)",
  "bucket_name": "string (if new)",
  "confidence": 0-100,
  "reasoning": "string"
}}
"""
        # 3. Call Gemini
        try:
            response_text = await self.gemini_client.generate_for_task(
                task=TaskType.GENERAL, # Or classification task if available
                prompt=prompt,
                max_output_tokens=300
            )
            
            # Parse JSON safely
            import re
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group(0))
            else:
                raise ValueError("No JSON found in response")

            # 4. Execute Action
            if plan.get("action") == "create_new" and auto_create:
                new_bucket = await self.create_bucket(
                    user_id=user_id,
                    name=plan.get("bucket_name", "New Bucket"),
                    description=plan.get("reasoning", "Auto-created by AI"),
                    category="custom"
                )
                return {
                    "bucket_id": str(new_bucket["id"]),
                    "bucket_name": new_bucket["name"],
                    "action": "created",
                    "confidence": plan.get("confidence")
                }
            
            elif plan.get("action") == "use_existing":
                # Validate ID exists
                b_id = plan.get("bucket_id")
                # Look up name
                b_name = next((b['name'] for b in buckets if str(b['id']) == b_id), "Unknown")
                return {
                    "bucket_id": b_id,
                    "bucket_name": b_name,
                    "action": "assigned",
                    "confidence": plan.get("confidence")
                }
            
            else:
                # Fallback
                inbox = next((b for b in buckets if b['name'] == "Inbox"), None)
                return {
                    "bucket_id": str(inbox['id']) if inbox else None,
                    "bucket_name": "Inbox",
                    "action": "fallback",
                    "confidence": 0
                }

        except Exception as e:
            logger.error(f"Smart assign failed: {e}")
            # Fallback
            return {"bucket_name": "Inbox", "action": "error_fallback"}
