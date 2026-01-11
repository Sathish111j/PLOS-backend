"""
Enhanced Web Scraper - CPU-First Escalation Strategy
Uses HTTP-first approach with browser escalation only when needed
"""

import re
from datetime import datetime
from typing import Any, Dict, Tuple

import httpx
import trafilatura
from bs4 import BeautifulSoup
from readability import Document

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class WebScraper:
    """
    CPU-optimized web scraper with escalation strategy.

    Flow (80-90% die in Step 1-3):
    1. HTTP Fetch (DrissionPage.SessionPage) - Pure HTTP, <100ms
    2. Trafilatura - Best boilerplate removal
    3. Readability - Fallback for blog-style content
    4. JS Detection - Heuristic (empty body / lazy load markers)
    5. Browser Escalation (DrissionPage.ChromiumPage) - ONLY if Step 4 triggers
    6. Network Intercept - Extract JSON/XHR before DOM paint
    7. Final Clean - Text normalization

    Sweet-spot: Chromium should feel rare, not normal
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self, timeout: int = 30):
        """
        Initialize optimized web scraper.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._http_client = None
        self._drission_page = None  # Lazy load

    async def extract(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract content with escalation strategy.

        Args:
            url: URL to extract

        Returns:
            Tuple of (content_text, metadata)
        """
        logger.info(f"Extracting: {url}")

        # Step 1: HTTP Fetch (always try this first)
        html, is_success = await self._http_fetch(url)

        if not is_success or not html:
            raise ValueError(f"Failed to fetch URL: {url}")

        # Step 2: Trafilatura (best for static content)
        content = trafilatura.extract(
            html, include_comments=False, include_tables=True, no_fallback=False
        )

        metadata = {"extraction_method": "trafilatura"}

        # Step 3: Readability fallback if trafilatura failed
        if not content or len(content) < 100:
            logger.info("Trafilatura failed, trying Readability...")
            content, metadata = self._extract_with_readability(html, url)

        # Step 4: JS Need Detection
        if self._needs_javascript(html, content):
            logger.info("JS detected, escalating to browser...")
            content, metadata = await self._extract_with_browser(url)

        # Step 7: Final clean
        content = self._normalize_text(content)

        # Add metadata
        metadata.update(self._extract_metadata(html, url))
        metadata["url"] = url
        metadata["extraction_timestamp"] = datetime.utcnow().isoformat()

        logger.info(
            f"Extracted {len(content)} chars via {metadata['extraction_method']}"
        )

        return content, metadata

    async def _http_fetch(self, url: str) -> Tuple[str, bool]:
        """
        Step 1: Pure HTTP fetch (< 100ms latency).

        Returns:
            Tuple of (html_content, success)
        """
        try:
            if not self._http_client:
                self._http_client = httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers={"User-Agent": self.USER_AGENTS[0]},
                )

            response = await self._http_client.get(url)
            response.raise_for_status()

            return response.text, True

        except Exception as e:
            logger.warning(f"HTTP fetch failed: {e}")
            return "", False

    def _extract_with_readability(self, html: str, url: str) -> Tuple[str, Dict]:
        """
        Step 3: Readability fallback for blog-style content.
        """
        try:
            doc = Document(html)
            content = doc.summary()

            # Convert HTML to text
            soup = BeautifulSoup(content, "lxml")
            text = soup.get_text(separator="\n", strip=True)

            return text, {"extraction_method": "readability", "title": doc.title()}

        except Exception as e:
            logger.warning(f"Readability failed: {e}")
            # Ultimate fallback: BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            return soup.get_text(separator="\n", strip=True), {
                "extraction_method": "beautifulsoup_fallback"
            }

    def _needs_javascript(self, html: str, extracted_content: str) -> bool:
        """
        Step 4: Heuristic JS detection.

        Triggers if:
        - Empty body
        - JS framework markers (React, Vue, Angular)
        - Lazy load tags
        - Very little extracted content vs HTML size
        """
        # Check content ratio
        content_ratio = len(extracted_content) / max(len(html), 1)
        if content_ratio < 0.01:  # Less than 1% useful content
            return True

        # Check for JS markers
        js_markers = [
            "ng-app",  # Angular
            "data-reactroot",  # React
            "v-app",  # Vue
            "__NEXT_DATA__",  # Next.js
            "gatsby",  # Gatsby
        ]

        html_lower = html.lower()
        for marker in js_markers:
            if marker.lower() in html_lower:
                return True

        # Check for lazy load
        lazy_markers = ["data-src=", "lazy", 'loading="lazy"']
        for marker in lazy_markers:
            if marker in html:
                return True

        return False

    async def _extract_with_browser(self, url: str) -> Tuple[str, Dict]:
        """
        Step 5-6: Browser escalation with DrissionPage.

        Uses DrissionPage instead of Playwright (lighter, no Node.js bridge).
        """
        try:
            # Lazy import (only load if needed)
            from DrissionPage import ChromiumOptions, ChromiumPage

            # Configure headless browser
            options = ChromiumOptions()
            options.headless(True)
            options.set_argument("--no-sandbox")
            options.set_argument("--disable-dev-shm-usage")

            if not self._drission_page:
                self._drission_page = ChromiumPage(options)

            # Navigate and wait for load
            self._drission_page.get(url)
            self._drission_page.wait.load_start()

            # Extract rendered content
            html = self._drission_page.html

            # Try trafilatura on rendered content first
            content = trafilatura.extract(html, no_fallback=False)

            if not content:
                # Fallback to page text
                content = self._drission_page.s_ele("body").text

            title = self._drission_page.title

            return content, {
                "extraction_method": "drission_browser",
                "title": title,
                "js_rendered": True,
            }

        except ImportError:
            logger.warning("DrissionPage not available, using basic extraction")
            return "", {"extraction_method": "browser_unavailable"}
        except Exception as e:
            logger.error(f"Browser extraction failed: {e}")
            return "", {"extraction_method": "browser_failed", "error": str(e)}

    def _extract_metadata(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract metadata from HTML.
        """
        soup = BeautifulSoup(html, "lxml")

        metadata = {}

        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text().strip()

        # Meta tags
        description_meta = soup.find("meta", attrs={"name": "description"})
        if description_meta:
            metadata["description"] = description_meta.get("content", "")

        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta:
            metadata["author"] = author_meta.get("content", "")

        # Open Graph
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title:
            metadata["og_title"] = og_title.get("content", "")

        return metadata

    def _normalize_text(self, text: str) -> str:
        """
        Step 7: Final text normalization for stable chunking.
        """
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text)

        # Remove special characters
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        return text.strip()

    async def close(self):
        """Close HTTP client and browser."""
        if self._http_client:
            await self._http_client.aclose()
        if self._drission_page:
            self._drission_page.quit()
