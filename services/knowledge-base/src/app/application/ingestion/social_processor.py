"""
Social Media Processor
======================
Extracts content from social media platforms for knowledge base ingestion.

Strategy per platform:

  Reddit    - Playwright (old.reddit.com for cleaner HTML)
  Twitter   - Playwright (tweet text + replies)
  LinkedIn  - Playwright (post / article)
  Instagram - yt-dlp + Gemini File API
                /reel/  - full video (visual) + audio transcript + caption
                /p/     - video post or photo; video gets full analysis,
                          photo gets thumbnail description
                /tv/    - IGTV, same as reel
              All local and remote files deleted immediately after processing.
  YouTube   - youtube-transcript-api -> yt-dlp VTT -> Gemini URL context (fallback)
                /watch  - regular video (transcript only, no download)
                /shorts/- same transcript pipeline + full visual analysis via Gemini
                          video ID extracted from /shorts/ path

Playwright is reused from the existing WebProcessor._render_dynamic logic.
Gemini calls use the shared ResilientGeminiClient for key rotation and
error handling. Local temp files are auto-deleted via TemporaryDirectory;
remote Gemini files are deleted in finally blocks via _gemini_upload_and_delete.
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
from app.application.ingestion.models import (
    ContentClass,
    DocumentFormat,
    ExtractionStrategy,
    SourceType,
    StructuredDocument,
)
from app.application.ingestion.normalizer import normalize_text
from app.application.ingestion.processors import ProcessorInput, _base_metadata
from google import genai
from google.genai import types

from shared.gemini.client import ResilientGeminiClient
from shared.gemini.config import GeminiModelType
from shared.utils.logger import get_logger

logger = get_logger(__name__)


# -- Platform detection --------------------------------------------------------

PLATFORM_PATTERNS: dict[str, re.Pattern[str]] = {
    "reddit": re.compile(r"reddit\.com", re.I),
    "twitter": re.compile(r"(twitter\.com|x\.com)", re.I),
    "linkedin": re.compile(r"linkedin\.com", re.I),
    # /reel/ -> Reels  |  /p/ -> photo/video posts  |  /tv/ -> IGTV
    "instagram": re.compile(r"instagram\.com/(reel|p|tv)/", re.I),
    # /watch -> regular  |  youtu.be -> short link  |  /shorts/ -> YouTube Shorts
    "youtube": re.compile(r"(youtube\.com/(watch|shorts)|youtu\.be)", re.I),
}


def _instagram_content_type(url: str) -> str:
    """Return 'reel', 'post', or 'igtv' based on URL path."""
    if "/reel/" in url.lower():
        return "reel"
    if "/tv/" in url.lower():
        return "igtv"
    return "post"  # /p/ -- could be photo or video post


def _is_youtube_short(url: str) -> bool:
    """Return True if the URL points to a YouTube Short."""
    return "/shorts/" in url.lower()


def detect_platform(url: str) -> str | None:
    """Return the platform key if *url* matches a known social site, else None."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


# -- Shared Playwright helper --------------------------------------------------


async def _playwright_get_text(
    url: str,
    *,
    wait_ms: int = 3000,
    scroll: bool = False,
    selectors: list[str] | None = None,
) -> str:
    """
    Launch headless Chromium, optionally scroll to trigger lazy content,
    then read specific CSS selectors or fall back to full-page innerText.

    Mirrors WebProcessor._render_dynamic but returns plain text directly
    instead of raw HTML.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        async def _block_media(route):
            if route.request.resource_type in {"image", "font", "media"}:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", _block_media)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(wait_ms)

        if scroll:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        text = ""

        if selectors:
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                parts = [await el.inner_text() for el in elements if el]
                text = "\n\n".join(p.strip() for p in parts if p.strip())
                if text:
                    break

        if not text:
            text = await page.inner_text("body")

        await context.close()
        await browser.close()

    return normalize_text(text)


# -- Shared Gemini upload helper -----------------------------------------------


async def _gemini_upload_and_delete(
    client: genai.Client,
    file_path: str,
    prompt_parts: list,
    model: str,
) -> str:
    """
    Upload a local file to Gemini File API, wait for it to become ACTIVE,
    run inference, then ALWAYS delete the remote file -- even on error.
    Local file deletion is handled by the caller's TemporaryDirectory.
    """
    uploaded = None
    try:
        uploaded = await asyncio.to_thread(client.files.upload, file=file_path)

        # Poll until ACTIVE (video processing can take a few seconds)
        for _ in range(30):
            info = await asyncio.to_thread(client.files.get, name=uploaded.name)
            if info.state.name == "ACTIVE":
                break
            if info.state.name == "FAILED":
                return ""
            await asyncio.sleep(1)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=[*prompt_parts, uploaded],
        )
        return (response.text or "").strip()

    except Exception:
        return ""

    finally:
        # Always delete from Gemini -- regardless of success or failure
        if uploaded is not None:
            try:
                await asyncio.to_thread(client.files.delete, name=uploaded.name)
            except Exception:
                pass


# -- 1. Reddit -----------------------------------------------------------------


class RedditExtractor:
    """Playwright against old.reddit.com for cleaner DOM structure."""

    async def extract(self, url: str) -> dict[str, Any]:
        old_url = re.sub(r"www\.reddit\.com", "old.reddit.com", url)
        text = await _playwright_get_text(
            old_url,
            wait_ms=2000,
            scroll=True,
            selectors=[
                # old Reddit
                ".usertext-body",
                ".entry .md",
                # new Reddit fallback
                "shreddit-post",
                "[data-testid='post-container']",
            ],
        )
        return {"text": text, "source": "playwright_old_reddit"}


# -- 2. Twitter / X ------------------------------------------------------------


class TwitterExtractor:
    """Playwright with extended wait for JS hydration."""

    async def extract(self, url: str) -> dict[str, Any]:
        text = await _playwright_get_text(
            url,
            wait_ms=4000,
            scroll=True,
            selectors=[
                "[data-testid='tweetText']",
                "article",
            ],
        )
        return {"text": text, "source": "playwright_twitter"}


# -- 3. LinkedIn ----------------------------------------------------------------


class LinkedInExtractor:
    """Playwright targeting post and article selectors."""

    async def extract(self, url: str) -> dict[str, Any]:
        text = await _playwright_get_text(
            url,
            wait_ms=3000,
            scroll=False,
            selectors=[
                ".feed-shared-update-v2__description",
                ".attributed-text-segment-list__content",
                ".article-content",
                ".reader-article-content",
            ],
        )
        return {"text": text, "source": "playwright_linkedin"}


# -- 4. Instagram -- handles Reels, Posts, IGTV --------------------------------
#
#    caption   - Gemini URL context (no download needed)
#    audio     - yt-dlp audio-only download -> Gemini File API -> deleted
#    visual    - yt-dlp video download -> Gemini File API -> deleted
#                (photo posts: thumbnail only since no video exists)
#
#    LOCAL files:  auto-deleted when tempfile.TemporaryDirectory() exits
#    GEMINI files: explicitly deleted via _gemini_upload_and_delete() after use
# ------------------------------------------------------------------------------


class InstagramExtractor:
    """
    yt-dlp + Gemini approach because Playwright cannot bypass IG login walls.

    Handles /reel/, /p/, and /tv/ URL types. For video content, downloads
    the full video at lowest quality for scene-by-scene Gemini analysis.
    For photo posts, falls back to thumbnail description.
    """

    def __init__(self, gemini_client: ResilientGeminiClient) -> None:
        self._gemini = gemini_client

    async def _get_caption(self, url: str) -> str:
        """Gemini URL context -- no download, reads public IG page directly."""
        client = await self._gemini.raw_client
        content_type = _instagram_content_type(url)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GeminiModelType.FLASH_LITE.value,
            contents=(
                f"From this Instagram {content_type} URL, extract: "
                f"the caption text, author username, hashtags, and like/view "
                f"count if visible. Return plain text only.\n\nURL: {url}"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(url_context=types.UrlContext())],
                temperature=0.1,
            ),
        )
        return (response.text or "").strip()

    async def _transcribe_audio(self, url: str) -> str:
        """
        Download audio-only stream (no video bytes wasted), send to Gemini
        File API for transcription, then delete both local file (via tempdir)
        and remote Gemini file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "audio.mp3"
            proc = subprocess.run(
                [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "--audio-quality",
                    "5",
                    "-o",
                    str(audio_path),
                    "--quiet",
                    url,
                ],
                capture_output=True,
                timeout=90,
            )
            if proc.returncode != 0 or not audio_path.exists():
                return ""

            client = await self._gemini.raw_client
            return await _gemini_upload_and_delete(
                client,
                str(audio_path),
                [
                    types.Part.from_text(
                        "Transcribe all spoken words from this audio accurately. "
                        "Return plain text only, no timestamps or speaker labels."
                    )
                ],
                model=GeminiModelType.FLASH_LITE.value,
            )
        # tmpdir (and audio.mp3) auto-deleted here

    async def _describe_visual(self, url: str) -> str:
        """
        For video content (Reels, video posts, IGTV):
            Download lowest-quality mp4, send full video to Gemini,
            delete both local file and remote Gemini file after processing.

        For photo posts:
            Fall back to thumbnail description (no video to download).
        """
        content_type = _instagram_content_type(url)

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "media.mp4"
            proc = subprocess.run(
                [
                    "yt-dlp",
                    "-f",
                    "worst[ext=mp4]/worst",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    str(video_path),
                    "--quiet",
                    url,
                ],
                capture_output=True,
                timeout=120,
            )

            if proc.returncode != 0 or not video_path.exists():
                # Photo post or download failed -- describe thumbnail instead
                return await self._describe_thumbnail(url)

            prompt = (
                f"Analyze this full Instagram {content_type} video and describe:\n"
                "1. What is happening scene by scene throughout the video\n"
                "2. People present -- appearance, expressions, actions\n"
                "3. Setting, background, location\n"
                "4. Any text overlays, stickers, or graphics on screen\n"
                "5. Products, brands, or objects featured\n"
                "6. Overall mood, tone, and style\n"
                "Return as plain descriptive text."
            )

            client = await self._gemini.raw_client
            return await _gemini_upload_and_delete(
                client,
                str(video_path),
                [types.Part.from_text(prompt)],
                model=GeminiModelType.FLASH.value,
            )
        # tmpdir (and media.mp4) auto-deleted here

    async def _describe_thumbnail(self, url: str) -> str:
        """Photo post fallback -- describes the image thumbnail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                [
                    "yt-dlp",
                    "--skip-download",
                    "--write-thumbnail",
                    "--convert-thumbnails",
                    "jpg",
                    "-o",
                    str(Path(tmpdir) / "thumb"),
                    "--quiet",
                    url,
                ],
                capture_output=True,
                timeout=30,
            )
            jpgs = list(Path(tmpdir).glob("*.jpg"))
            if not jpgs:
                return ""
            image_bytes = jpgs[0].read_bytes()
        # tmpdir auto-deleted here

        client = await self._gemini.raw_client
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GeminiModelType.FLASH.value,
            contents=[
                types.Part.from_text(
                    "Describe this Instagram photo in detail. "
                    "Include: people, setting, objects, text, mood, colours, "
                    "and any brands visible."
                ),
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
        )
        return (response.text or "").strip()

    async def extract(self, url: str) -> dict[str, Any]:
        content_type = _instagram_content_type(url)

        # All three run in parallel -- total time = slowest of the three
        caption, audio_transcript, visual_description = await asyncio.gather(
            self._get_caption(url),
            self._transcribe_audio(url),
            self._describe_visual(url),
        )

        text = "\n\n".join(
            filter(
                None,
                [
                    f"Caption:\n{caption}" if caption else "",
                    (
                        f"Audio Transcript:\n{audio_transcript}"
                        if audio_transcript
                        else ""
                    ),
                    (
                        f"Visual Description:\n{visual_description}"
                        if visual_description
                        else ""
                    ),
                ],
            )
        )

        return {
            "text": normalize_text(text),
            "content_type": content_type,  # "reel" | "post" | "igtv"
            "caption": caption,
            "audio_transcript": audio_transcript,
            "visual_description": visual_description,
        }


# -- 5. YouTube ----------------------------------------------------------------
#    Regular videos (/watch, youtu.be) - transcript only, no download needed
#    Shorts (/shorts/)                 - transcript + full visual analysis
#                                        (same pipeline as Instagram Reels)
# ------------------------------------------------------------------------------


class YouTubeExtractor:
    """
    Three-tier transcript extraction:
    1. youtube-transcript-api (fastest, no download)
    2. yt-dlp auto-subtitle VTT (fallback)
    3. Gemini URL context (last resort)

    YouTube Shorts additionally get full video visual analysis via Gemini,
    running in parallel with the transcript pipeline.
    """

    def __init__(self, gemini_client: ResilientGeminiClient) -> None:
        self._gemini = gemini_client

    def _video_id(self, url: str) -> str | None:
        for pattern in [
            r"v=([A-Za-z0-9_-]{11})",
            r"youtu\.be/([A-Za-z0-9_-]{11})",
            r"/shorts/([A-Za-z0-9_-]{11})",
        ]:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    # -- Transcript methods (all zero-download) --------------------------------

    def _native_transcript(self, video_id: str) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            entries = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["en", "en-US", "en-GB"]
            )
            return " ".join(e["text"] for e in entries)
        except Exception:
            return ""

    def _ytdlp_subtitle(self, video_id: str) -> str:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                subprocess.run(
                    [
                        "yt-dlp",
                        "--skip-download",
                        "--write-auto-sub",
                        "--sub-lang",
                        "en",
                        "--sub-format",
                        "vtt",
                        "-o",
                        str(Path(tmpdir) / "%(id)s"),
                        "--quiet",
                        f"https://www.youtube.com/watch?v={video_id}",
                    ],
                    capture_output=True,
                    timeout=30,
                )
                vtts = list(Path(tmpdir).glob("*.vtt"))
                if not vtts:
                    return ""
                raw = vtts[0].read_text(encoding="utf-8")
                lines = [
                    line
                    for line in raw.splitlines()
                    if line.strip()
                    and "-->" not in line
                    and not re.match(r"^\d{2}:\d{2}", line)
                    and line.strip() != "WEBVTT"
                ]
                return " ".join(lines)
        except Exception:
            return ""

    async def _gemini_transcript_fallback(self, url: str) -> str:
        client = await self._gemini.raw_client
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=GeminiModelType.FLASH_LITE.value,
            contents=(
                f"From this YouTube video URL, extract the video title, channel "
                f"name, and full transcript or auto-generated captions. "
                f"Plain text only, no timestamps.\n\nURL: {url}"
            ),
            config=types.GenerateContentConfig(
                tools=[types.Tool(url_context=types.UrlContext())],
                temperature=0.1,
            ),
        )
        return (response.text or "").strip()

    async def _get_transcript(self, video_id: str, url: str) -> tuple[str, str]:
        """Return (transcript_text, method_used)."""
        transcript = self._native_transcript(video_id)
        if transcript:
            return transcript, "youtube_transcript_api"

        transcript = self._ytdlp_subtitle(video_id)
        if transcript:
            return transcript, "yt_dlp_vtt"

        transcript = await self._gemini_transcript_fallback(url)
        return transcript, "gemini_url_context"

    # -- Visual analysis for Shorts (same pattern as InstagramExtractor) -------

    async def _describe_short_visual(self, url: str, video_id: str) -> str:
        """
        Download the Short at lowest quality, send full video to Gemini,
        then delete both local file (via tempdir) and remote Gemini file.
        """
        full_url = f"https://www.youtube.com/shorts/{video_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "short.mp4"
            proc = subprocess.run(
                [
                    "yt-dlp",
                    "-f",
                    "worst[ext=mp4]/worst",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    str(video_path),
                    "--quiet",
                    full_url,
                ],
                capture_output=True,
                timeout=120,
            )
            if proc.returncode != 0 or not video_path.exists():
                return ""

            client = await self._gemini.raw_client
            return await _gemini_upload_and_delete(
                client,
                str(video_path),
                [
                    types.Part.from_text(
                        "Analyze this full YouTube Short video and describe:\n"
                        "1. What is happening scene by scene throughout the video\n"
                        "2. People present -- appearance, expressions, actions\n"
                        "3. Setting, background, location\n"
                        "4. Any text overlays, captions, or graphics on screen\n"
                        "5. Products, brands, or objects featured\n"
                        "6. Overall mood, tone, and style\n"
                        "Return as plain descriptive text."
                    )
                ],
                model=GeminiModelType.FLASH.value,
            )
        # tmpdir (and short.mp4) auto-deleted here

    # -- Title metadata --------------------------------------------------------

    def _get_title(self, video_id: str) -> dict[str, str]:
        try:
            resp = httpx.get(
                f"https://www.youtube.com/oembed"
                f"?url=https://www.youtube.com/watch?v={video_id}&format=json",
                timeout=10,
            )
            data = resp.json()
            return {
                "title": data.get("title", ""),
                "author": data.get("author_name", ""),
            }
        except Exception:
            return {}

    # -- Main entry point ------------------------------------------------------

    async def extract(self, url: str) -> dict[str, Any]:
        video_id = self._video_id(url)
        is_short = _is_youtube_short(url)
        meta = self._get_title(video_id) if video_id else {}

        if is_short and video_id:
            # Shorts: transcript + full visual analysis in parallel
            (transcript, method), visual_description = await asyncio.gather(
                self._get_transcript(video_id, url),
                self._describe_short_visual(url, video_id),
            )
        elif video_id:
            # Regular video: transcript only, no download
            transcript, method = await self._get_transcript(video_id, url)
            visual_description = ""
        else:
            transcript, method, visual_description = "", "none", ""

        parts = [
            f"Title: {meta.get('title', '')}" if meta.get("title") else "",
            f"Channel: {meta.get('author', '')}" if meta.get("author") else "",
            f"Transcript:\n{transcript}" if transcript else "",
            (
                f"Visual Description:\n{visual_description}"
                if visual_description
                else ""
            ),
        ]
        text = "\n\n".join(p for p in parts if p)

        return {
            "text": normalize_text(text),
            "content_type": "short" if is_short else "video",
            "transcript": transcript,
            "transcript_method": method,
            "visual_description": visual_description,
            **meta,
        }


# -- Main processor -------------------------------------------------------------


class SocialMediaProcessor:
    """
    Dispatches to platform-specific extractors and returns a StructuredDocument.

    Usage in UnifiedDocumentProcessor:
        if detected.format == DocumentFormat.SOCIAL:
            result = await self._social_processor.process(payload)
    """

    _playwright_extractors: dict[str, type] = {
        "reddit": RedditExtractor,
        "twitter": TwitterExtractor,
        "linkedin": LinkedInExtractor,
    }

    _source_type_map: dict[str, SourceType] = {
        "reddit": SourceType.SOCIAL_MEDIA,
        "twitter": SourceType.SOCIAL_MEDIA,
        "linkedin": SourceType.SOCIAL_MEDIA,
        "instagram": SourceType.SOCIAL_MEDIA,
        "youtube": SourceType.SOCIAL_MEDIA,
    }

    def __init__(self) -> None:
        self._gemini = ResilientGeminiClient()

    def _get_extractor(self, platform: str) -> Any:
        """Return the appropriate extractor instance for the platform."""
        if platform in self._playwright_extractors:
            return self._playwright_extractors[platform]()
        if platform == "instagram":
            return InstagramExtractor(self._gemini)
        if platform == "youtube":
            return YouTubeExtractor(self._gemini)
        raise ValueError(f"No extractor for platform: {platform}")

    async def process(self, payload: ProcessorInput) -> StructuredDocument:
        url = payload.source_url or ""
        platform = detect_platform(url)
        if not platform:
            raise ValueError(f"Unsupported social media platform: {url}")

        extractor = self._get_extractor(platform)
        try:
            result = await extractor.extract(url)
        except Exception as exc:
            logger.warning(
                "Social media extraction failed",
                extra={"platform": platform, "url": url, "error": str(exc)},
            )
            result = {"text": "", "error": str(exc)}

        text = result.pop("text", "")
        metadata = _base_metadata(payload)
        metadata.update({"platform": platform, "social_metadata": result})
        confidence = 0.9 if text else 0.2

        return StructuredDocument(
            source_type=self._source_type_map.get(platform, SourceType.SOCIAL_MEDIA),
            raw_text=text,
            text=text,
            sections=[],
            metadata=metadata,
            confidence_scores={"text_extraction": confidence},
            confidence_score=confidence,
            extraction_path=f"social_{platform}",
            strategy_used=ExtractionStrategy.SOCIAL_MEDIA_EXTRACTION,
            format=DocumentFormat.SOCIAL,
            content_class=ContentClass.TEXT_BASED,
        )
