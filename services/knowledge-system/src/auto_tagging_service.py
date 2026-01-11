"""
Auto-Tagging Service for PLOS Knowledge System
Automatically generates tags based on content analysis using keyword extraction and AI
"""

import re
from collections import Counter
from typing import List

from shared.gemini import ResilientGeminiClient
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class AutoTaggingService:
    """
    Intelligent auto-tagging using keyword extraction and AI analysis.

    Methods:
    1. TF-IDF-like keyword extraction (fast, local)
    2. Gemini AI analysis (optional, for better quality)
    """

    # Common stop words to filter out
    STOP_WORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "can",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
    }

    def __init__(
        self, gemini_client: ResilientGeminiClient = None, use_ai: bool = False
    ):
        """
        Initialize auto-tagging service.

        Args:
            gemini_client: Gemini client for AI-based tagging
            use_ai: Whether to use AI for tag generation (slower but better)
        """
        self.gemini_client = gemini_client
        self.use_ai = use_ai

    async def generate_tags(
        self, title: str, content: str, max_tags: int = 5, min_word_length: int = 3
    ) -> List[str]:
        """
        Generate tags using keyword extraction or AI.

        Args:
            title: Document title
            content: Document content
            max_tags: Maximum number of tags to generate
            min_word_length: Minimum length of tag words

        Returns:
            List of generated tags
        """
        # Try AI tagging if enabled and client available
        if self.use_ai and self.gemini_client:
            try:
                tags = await self._generate_tags_with_ai(title, content, max_tags)
                if tags:
                    logger.info(f"Generated {len(tags)} tags using AI")
                    return tags
            except Exception as e:
                logger.warning(
                    f"AI tagging failed, falling back to keyword extraction: {e}"
                )

        # Fallback to keyword extraction
        tags = self._generate_tags_with_keywords(
            title, content, max_tags, min_word_length
        )
        logger.info(f"Generated {len(tags)} tags using keyword extraction")
        return tags

    def _generate_tags_with_keywords(
        self, title: str, content: str, max_tags: int, min_word_length: int
    ) -> List[str]:
        """
        Generate tags using TF-IDF-like keyword extraction.

        Strategy:
        1. Extract words from title (2x weight) and content
        2. Filter stop words and short words
        3. Count frequency
        4. Return top N
        """
        # Combine title and content (title has 2x weight)
        text = (title + " " + title + " " + content).lower()

        # Extract words (alphanumeric only)
        words = re.findall(r"\b[a-z0-9]+\b", text)

        # Filter stop words and short words
        filtered_words = [
            word
            for word in words
            if word not in self.STOP_WORDS and len(word) >= min_word_length
        ]

        # Count frequency
        word_counts = Counter(filtered_words)

        # Get top N most common
        top_words = word_counts.most_common(max_tags)

        # Return only the words (not counts)
        tags = [word for word, count in top_words]

        return tags

    async def _generate_tags_with_ai(
        self, title: str, content: str, max_tags: int
    ) -> List[str]:
        """
        Generate tags using Gemini AI analysis.

        Args:
            title: Document title
            content: Document content (first 2000 chars)
            max_tags: Maximum number of tags

        Returns:
            List of AI-generated tags
        """
        # Limit content to first 2000 chars for efficiency
        content_sample = content[:2000]

        prompt = f"""Analyze this document and generate {max_tags} relevant tags/keywords.

Title: {title}

Content: {content_sample}

Generate exactly {max_tags} single-word or short-phrase tags that best describe this content.
Return only the tags, separated by commas, lowercase, no explanations.

Tags:"""

        response_text = await self.gemini_client.generate_content(
            prompt=prompt, max_output_tokens=100
        )

        # Parse response
        tags_text = response_text.strip()

        # Split by comma and clean
        tags = [tag.strip().lower() for tag in tags_text.split(",") if tag.strip()]

        # Limit to max_tags
        return tags[:max_tags]

    async def suggest_tags(
        self,
        existing_tags: List[str],
        title: str,
        content: str,
        max_suggestions: int = 3,
    ) -> List[str]:
        """
        Suggest additional tags based on existing content.

        Args:
            existing_tags: Tags already assigned
            title: Document title
            content: Document content
            max_suggestions: Maximum suggestions

        Returns:
            List of suggested tags (excluding existing ones)
        """
        # Generate potential tags
        potential_tags = await self.generate_tags(title, content, max_tags=10)

        # Filter out existing tags
        existing_set = set(tag.lower() for tag in existing_tags)
        suggestions = [tag for tag in potential_tags if tag.lower() not in existing_set]

        return suggestions[:max_suggestions]
