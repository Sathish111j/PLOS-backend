"""Tests for social media processor integration.

Covers:
- detect_platform() URL pattern matching
- _instagram_content_type() and _is_youtube_short() helpers
- Format detector classifying social URLs as DocumentFormat.SOCIAL
- Individual extractors with mocked Playwright / Gemini
- SocialMediaProcessor.process() end-to-end (mocked extractors)
- UnifiedDocumentProcessor routing to the social branch
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.application.ingestion.format_detector import detect_document_format
from app.application.ingestion.models import (
    DocumentFormat,
    ExtractionStrategy,
    SourceType,
    StructuredDocument,
)
from app.application.ingestion.processors import ProcessorInput
from app.application.ingestion.social_processor import (
    SocialMediaProcessor,
    _instagram_content_type,
    _is_youtube_short,
    detect_platform,
)

# --- detect_platform() ---


class TestDetectPlatform:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://www.reddit.com/r/python/comments/abc123", "reddit"),
            ("https://old.reddit.com/r/learnpython/comments/xyz", "reddit"),
            ("https://twitter.com/user/status/123456", "twitter"),
            ("https://x.com/user/status/789", "twitter"),
            ("https://www.linkedin.com/posts/user-abc123", "linkedin"),
            ("https://www.instagram.com/reel/Cabc123/", "instagram"),
            ("https://www.instagram.com/p/Bxyz789/", "instagram"),
            ("https://www.instagram.com/tv/Cdef456/", "instagram"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
            ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "youtube"),
        ],
    )
    def test_known_platforms(self, url: str, expected: str) -> None:
        assert detect_platform(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/page",
            "https://docs.google.com/doc/123",
            "ftp://files.example.com/data.csv",
            # Bare instagram.com without /reel/, /p/, or /tv/ should NOT match
            "https://www.instagram.com/username/",
            "",
        ],
    )
    def test_unknown_urls_return_none(self, url: str) -> None:
        assert detect_platform(url) is None

    def test_case_insensitive(self) -> None:
        assert detect_platform("https://WWW.REDDIT.COM/r/test") == "reddit"
        assert detect_platform("https://YOUTUBE.COM/watch?v=abc") == "youtube"
        assert detect_platform("https://YOUTUBE.COM/shorts/abc12345678") == "youtube"


# --- Helper functions ---


class TestInstagramContentType:
    def test_reel(self) -> None:
        assert _instagram_content_type("https://www.instagram.com/reel/Cabc123/") == "reel"

    def test_post(self) -> None:
        assert _instagram_content_type("https://www.instagram.com/p/Bxyz789/") == "post"

    def test_igtv(self) -> None:
        assert _instagram_content_type("https://www.instagram.com/tv/Cdef456/") == "igtv"

    def test_case_insensitive(self) -> None:
        assert _instagram_content_type("https://www.instagram.com/REEL/Cabc123/") == "reel"
        assert _instagram_content_type("https://www.instagram.com/TV/Cdef456/") == "igtv"


class TestIsYoutubeShort:
    def test_short_url(self) -> None:
        assert _is_youtube_short("https://www.youtube.com/shorts/dQw4w9WgXcQ") is True

    def test_regular_watch(self) -> None:
        assert _is_youtube_short("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False

    def test_short_link(self) -> None:
        assert _is_youtube_short("https://youtu.be/dQw4w9WgXcQ") is False

    def test_case_insensitive(self) -> None:
        assert _is_youtube_short("https://www.youtube.com/SHORTS/dQw4w9WgXcQ") is True


# --- Format detector integration ---


class TestFormatDetectorSocial:
    """Social URLs must be classified as SOCIAL, not WEB."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.reddit.com/r/python/comments/abc123",
            "https://twitter.com/user/status/123",
            "https://x.com/user/status/789",
            "https://www.linkedin.com/posts/user-abc",
            "https://www.instagram.com/reel/Cabc123/",
            "https://www.instagram.com/p/Bxyz789/",
            "https://www.instagram.com/tv/Cdef456/",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        ],
    )
    def test_social_url_detected_as_social(self, url: str) -> None:
        result = detect_document_format(
            filename="social_link",
            content_bytes=None,
            mime_type=None,
            source_url=url,
        )
        assert result.format == DocumentFormat.SOCIAL
        assert result.detector_confidence >= 0.85

    def test_regular_url_still_detected_as_web(self) -> None:
        result = detect_document_format(
            filename="web_link",
            content_bytes=None,
            mime_type=None,
            source_url="https://example.com/article",
        )
        assert result.format == DocumentFormat.WEB

    def test_non_url_not_affected(self) -> None:
        result = detect_document_format(
            filename="data.json",
            content_bytes=b'{"key": "value"}',
            mime_type="application/json",
            source_url=None,
        )
        assert result.format != DocumentFormat.SOCIAL


# --- SocialMediaProcessor.process() with mocked extractors ---

_MOCK_GEMINI = "app.application.ingestion.social_processor.ResilientGeminiClient"


def _make_payload(url: str) -> ProcessorInput:
    return ProcessorInput(
        filename="social_link",
        content_bytes=None,
        source_url=url,
        mime_type=None,
        text_encoding=None,
    )


class TestSocialMediaProcessor:
    """Test the main processor with mocked platform extractors."""

    @pytest.mark.asyncio
    async def test_reddit_routes_correctly(self) -> None:
        mock_extract = AsyncMock(
            return_value={"text": "Reddit discussion content", "source": "playwright"}
        )
        with patch(
            "app.application.ingestion.social_processor.RedditExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload("https://www.reddit.com/r/python/comments/abc")
            result = await processor.process(payload)

        assert isinstance(result, StructuredDocument)
        assert result.format == DocumentFormat.SOCIAL
        assert result.strategy_used == ExtractionStrategy.SOCIAL_MEDIA_EXTRACTION
        assert result.source_type == SourceType.SOCIAL_MEDIA
        assert "Reddit discussion content" in result.text
        assert result.metadata["platform"] == "reddit"
        assert result.confidence_score == pytest.approx(0.9)
        mock_extract.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_twitter_routes_correctly(self) -> None:
        mock_extract = AsyncMock(
            return_value={"text": "Tweet thread content", "source": "playwright"}
        )
        with patch(
            "app.application.ingestion.social_processor.TwitterExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload("https://x.com/user/status/123456")
            result = await processor.process(payload)

        assert result.format == DocumentFormat.SOCIAL
        assert result.metadata["platform"] == "twitter"
        assert "Tweet thread content" in result.text

    @pytest.mark.asyncio
    async def test_youtube_routes_correctly(self) -> None:
        mock_extract = AsyncMock(
            return_value={
                "text": "Video transcript here",
                "content_type": "video",
                "transcript": "Video transcript here",
                "transcript_method": "youtube_transcript_api",
                "visual_description": "",
                "title": "Test Video",
            }
        )
        with patch(
            "app.application.ingestion.social_processor.YouTubeExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            result = await processor.process(payload)

        assert result.format == DocumentFormat.SOCIAL
        assert result.metadata["platform"] == "youtube"
        assert "Video transcript here" in result.text

    @pytest.mark.asyncio
    async def test_youtube_short_routes_correctly(self) -> None:
        mock_extract = AsyncMock(
            return_value={
                "text": "Short content",
                "content_type": "short",
                "transcript": "Short transcript",
                "transcript_method": "youtube_transcript_api",
                "visual_description": "Person dancing in a park",
                "title": "Fun Short",
            }
        )
        with patch(
            "app.application.ingestion.social_processor.YouTubeExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload(
                "https://www.youtube.com/shorts/dQw4w9WgXcQ"
            )
            result = await processor.process(payload)

        assert result.format == DocumentFormat.SOCIAL
        assert result.metadata["platform"] == "youtube"
        assert "Short content" in result.text

    @pytest.mark.asyncio
    async def test_instagram_post_routes_correctly(self) -> None:
        mock_extract = AsyncMock(
            return_value={
                "text": "Instagram post content",
                "content_type": "post",
                "caption": "A cool photo",
                "audio_transcript": "",
                "visual_description": "A sunset",
            }
        )
        with patch(
            "app.application.ingestion.social_processor.InstagramExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload("https://www.instagram.com/p/Bxyz789/")
            result = await processor.process(payload)

        assert result.format == DocumentFormat.SOCIAL
        assert result.metadata["platform"] == "instagram"
        assert "Instagram post content" in result.text

    @pytest.mark.asyncio
    async def test_unsupported_url_raises(self) -> None:
        with patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
        payload = _make_payload("https://example.com/not-social")
        with pytest.raises(ValueError, match="Unsupported social media platform"):
            await processor.process(payload)

    @pytest.mark.asyncio
    async def test_extractor_failure_returns_low_confidence(self) -> None:
        mock_extract = AsyncMock(side_effect=RuntimeError("Network error"))
        with patch(
            "app.application.ingestion.social_processor.RedditExtractor.extract",
            mock_extract,
        ), patch(_MOCK_GEMINI):
            processor = SocialMediaProcessor()
            payload = _make_payload("https://www.reddit.com/r/test/comments/xyz")
            result = await processor.process(payload)

        assert result.format == DocumentFormat.SOCIAL
        assert result.confidence_score == pytest.approx(0.2)
        assert result.text == ""
        assert "error" in result.metadata["social_metadata"]


# --- UnifiedDocumentProcessor routing to social branch ---


class TestUnifiedProcessorSocialRouting:
    @pytest.mark.asyncio
    async def test_social_url_dispatches_to_social_processor(self) -> None:
        from app.application.ingestion.unified_processor import (
            UnifiedDocumentProcessor,
        )

        mock_social_result = StructuredDocument(
            source_type=SourceType.SOCIAL_MEDIA,
            raw_text="mocked social text",
            text="mocked social text",
            sections=[],
            metadata={"platform": "youtube"},
            confidence_scores={"text_extraction": 0.9},
            confidence_score=0.9,
            extraction_path="social_youtube",
            strategy_used=ExtractionStrategy.SOCIAL_MEDIA_EXTRACTION,
            format=DocumentFormat.SOCIAL,
        )

        with patch.object(
            SocialMediaProcessor,
            "process",
            new_callable=AsyncMock,
            return_value=mock_social_result,
        ) as mock_process, patch(_MOCK_GEMINI):
            processor = UnifiedDocumentProcessor()
            result = await processor.process(
                filename="yt_link",
                content_bytes=None,
                mime_type=None,
                source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            )

        mock_process.assert_awaited_once()
        assert result.format == DocumentFormat.SOCIAL
        assert result.source_type == SourceType.SOCIAL_MEDIA
        assert "mocked social text" in result.text
